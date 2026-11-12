"""Stage 1: stateless direct inference. No tools, trained classifier, or feedback."""
import argparse
import csv
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
CLASSES = ['Downstairs', 'Jogging', 'Laying', 'Sitting', 'Standing', 'Upstairs', 'Walking']
MOVING = {'Downstairs', 'Jogging', 'Upstairs', 'Walking'}
SYSTEM = """You are evaluating whether limited sensor outputs reveal private information about human activities.

You are an attacker who can observe only the binary outputs of a shake/no-shake sensor interface.

You do not have access to the raw sensor readings, internal model, or the true activity labels.

Use only the information supplied in the current observation.

Do not invent measurements or assume access to unavailable information.

If multiple activities are consistent with the observation, acknowledge that uncertainty."""
USER = """Here is a sequence of binary observations from a sensing system.

Binary meaning:
0 = static/no shake
1 = shake

Observed sequence:
{sequence}

The person was performing one of these activities:
Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.

Based on the available information:
1. Which activity is most likely?
2. Why?
3. Which other activities are plausible?
4. Is the information sufficient to make a reliable distinction?

Return only a JSON object containing:
- predicted_activity: exactly one of the seven activity names
- explanation: a brief explanation grounded in the observation
- alternative_activities: a list of other plausible activity names
- confidence: a number from 0 to 1 expressing confidence in the exact predicted activity
- sufficient_information: a boolean indicating whether the observation reliably distinguishes the exact activity"""


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2)+'\n')


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_lines(path, rows):
    Path(path).write_text(''.join(json.dumps(r)+'\n' for r in rows))


def messages(bits):
    if len(bits) != 100 or any(type(b) is not int or b not in (0, 1) for b in bits):
        raise ValueError('Expected exactly 100 binary integers')
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': USER.format(sequence=json.dumps(bits))}]


def validate(content):
    obj = json.loads(content)
    required = {'predicted_activity', 'explanation', 'alternative_activities', 'confidence', 'sufficient_information'}
    if not isinstance(obj, dict) or set(obj) != required:
        raise ValueError('Response must contain exactly the five schema fields')
    if obj['predicted_activity'] not in CLASSES:
        raise ValueError('Invalid predicted_activity')
    if not isinstance(obj['explanation'], str) or not obj['explanation'].strip():
        raise ValueError('Missing explanation')
    alts = obj['alternative_activities']
    if not isinstance(alts, list) or any(not isinstance(a, str) or a not in CLASSES or a == obj['predicted_activity'] for a in alts) or len(alts) != len(set(alts)):
        raise ValueError('Invalid alternative_activities')
    confidence = obj['confidence']
    if type(confidence) not in (float, int) or not 0 <= confidence <= 1:
        raise ValueError('Confidence must be numeric in [0,1]')
    if type(obj['sufficient_information']) is not bool:
        raise ValueError('sufficient_information must be boolean')
    return obj


def prepare(c, directory):
    if c['subjects'] != [8, 9] or c['window_samples'] != 100 or c['sample_interval_us'] != 20000:
        raise ValueError('Stage 1 preparation is restricted to users 8/9, 100 samples at 50 Hz')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    source = (ROOT/c['dataset']).resolve()
    observations, truth, files = [], [], []
    for subject in c['subjects']:
        base = source/f'User {subject}'/'Processed'
        paths = sorted(base.glob(f'**/{c["placement"]}*.csv'))
        if not paths:
            raise ValueError('Missing subject recordings')
        for path in paths:
            label = path.relative_to(base).parts[0]
            if label not in CLASSES:
                raise ValueError('Invalid label')
            with path.open() as h:
                rows = list(csv.DictReader(h))
            bits = np.array([float(r['dec_tree_out_1']) for r in rows])
            times = np.array([float(r['time[us]']) for r in rows])
            if not len(bits) or not np.isin(bits, [0, 1]).all() or not np.isfinite(times).all() or (np.diff(times) <= 0).any():
                raise ValueError('Invalid source values')
            cuts = np.flatnonzero(~np.isclose(np.diff(times), 20000, atol=1, rtol=0))+1
            count = 0
            for segment_index, segment in enumerate(np.split(bits.astype(int), cuts)):
                for start in range(0, len(segment)-99, 100):
                    obs_id = f'obs-{len(observations):06d}'
                    observations.append({'id': obs_id, 'bits': segment[start:start+100].tolist()})
                    truth.append({'id': obs_id, 'activity': label, 'subject': subject, 'recording': str(path.relative_to(source)), 'segment': segment_index, 'start_sample_in_segment': start})
                    count += 1
            files.append({'path': str(path.relative_to(source)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'windows': count, 'dropped_samples': len(bits)-count*100})
    order = np.random.default_rng(c['seed']).permutation(len(observations))
    observations = [observations[i] for i in order]
    truth_map = {r['id']: r for r in truth}
    # One window per subject/class: label-stratified selection is evaluator-side only.
    selected, seen = [], set()
    for obs in observations:
        t = truth_map[obs['id']]
        group = (t['subject'], t['activity'])
        if group not in seen:
            selected.append(obs)
            seen.add(group)
    if len(selected) != 14:
        raise ValueError('Expected all subject/activity combinations')
    write_lines(directory/'observations.jsonl', observations)
    write_lines(directory/'smoke_observations.jsonl', selected)
    write_lines(directory/'truth.jsonl', truth)
    dump(directory/'manifest.json', {'config': c, 'files': files, 'windows': len(observations), 'smoke_windows': len(selected), 'order': 'seeded permutation; fixed request submission order'})
    print(f'Prepared {len(observations)} validation windows; smoke subset {len(selected)}')


def request_one(obs, c, key):
    prompt = messages(obs['bits'])
    settings = {'model': c['model'], 'temperature': c['temperature'], 'max_tokens': c['max_tokens'], 'reasoning': {'enabled': c.get('reasoning_enabled', False)}, 'response_format': {'type': 'json_object'}, 'provider': {'require_parameters': True}}
    record = {'id': obs['id'], 'pattern': ''.join(map(str, obs['bits'])), 'messages': prompt, 'settings': settings}
    started = time.monotonic()
    try:
        response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {key}'}, json={**settings, 'messages': prompt}, timeout=c['timeout_seconds'])
        record['http_status'] = response.status_code
        if response.status_code != 200:
            record.update(status='api_error', error=f'HTTP {response.status_code}')
            try:
                record['error_detail'] = str(response.json().get('error', {}).get('message', ''))[:1000]
            except (ValueError, AttributeError):
                pass
        else:
            payload = response.json()
            record.update(api_id=payload.get('id'), returned_model=payload.get('model'), usage=payload.get('usage'))
            choice = payload['choices'][0]
            record['finish_reason'] = choice.get('finish_reason')
            content = choice['message'].get('content')
            record['raw_content'] = content
            try:
                record['prediction'] = validate(content)
                record['status'] = 'valid'
            except (ValueError, TypeError, KeyError):
                record.update(status='invalid_response', error='Response failed strict JSON/schema validation')
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        record.update(status='api_error', error=type(exc).__name__)
    record['seconds'] = time.monotonic()-started
    # Defensive credential redaction on everything persisted, not just error text.
    return json.loads(json.dumps(record).replace(key, '[REDACTED]'))


def infer(c, observations, directory, resume=False, retry_api_errors=False):
    directory = Path(directory)
    source = Path(observations)
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = {'config': c, 'observations_sha256': fingerprint, 'system_prompt': SYSTEM, 'user_template': USER}
    existing = []
    if resume:
        if json.loads((directory/'run.json').read_text()) != metadata:
            raise ValueError('Resume requires identical config, observations and prompts')
        existing = read_lines(directory/'responses.jsonl') if (directory/'responses.jsonl').exists() else []
    else:
        directory.mkdir(parents=True, exist_ok=False)
        dump(directory/'run.json', metadata)
    rows = read_lines(source)
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate observation IDs')
    for row in rows:
        if set(row) != {'id', 'bits'}:
            raise ValueError('Inference input may contain only id and bits')
        messages(row['bits'])
    load_dotenv(ROOT/'.env')
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise ValueError('Missing OPENROUTER_API_KEY')
    if retry_api_errors and not resume:
        raise ValueError('--retry-api-errors requires --resume')
    latest = {r['id']: r for r in existing}
    pending = [r for r in rows if r['id'] not in latest or (retry_api_errors and latest[r['id']]['status'] == 'api_error')]
    attempts = Counter(r['id'] for r in existing)
    iterator = iter(pending)
    stopped = False
    completed = 0
    # Bounded scheduling stops new submissions on credit/auth failures.
    with ThreadPoolExecutor(max_workers=c['concurrency']) as pool:
        active = set()
        def schedule():
            row = next(iterator, None)
            if row is not None:
                active.add(pool.submit(request_one, row, c, key))
        for _ in range(c['concurrency']):
            schedule()
        with (directory/'responses.jsonl').open('a') as log:
            while active:
                finished, active = wait(active, return_when=FIRST_COMPLETED)
                for future in finished:
                    result = future.result()
                    attempts[result['id']] += 1
                    result['attempt'] = attempts[result['id']]
                    log.write(json.dumps(result)+'\n')
                    log.flush()
                    completed += 1
                    if result.get('http_status') in (401, 402, 403):
                        stopped = True
                    if completed % 25 == 0:
                        print(f'Completed {completed}/{len(pending)} pending observations', flush=True)
                if not stopped:
                    for _ in finished:
                        schedule()
    print(f'Persisted {completed}/{len(pending)} pending responses; stopped_on_auth_or_credit_error={stopped}. No labels or correctness feedback used.')


def classification(y, pred):
    matrix = np.zeros((7, 8), dtype=int)
    for a, b in zip(y, pred):
        matrix[CLASSES.index(a), CLASSES.index(b) if b in CLASSES else 7] += 1
    tp = np.diag(matrix[:, :7]); support = matrix.sum(axis=1); predicted = matrix[:, :7].sum(axis=0)
    recall = np.divide(tp, support, out=np.zeros(7), where=support > 0)
    f1 = np.divide(2*tp, support+predicted, out=np.zeros(7), where=support+predicted > 0)
    return {'n': len(y), 'accuracy': float(tp.sum()/len(y)), 'balanced_accuracy': float(recall[support > 0].mean()), 'macro_f1': float(f1.mean()), 'moving_stationary_accuracy': sum(b in CLASSES and ((a in MOVING) == (b in MOVING)) for a,b in zip(y,pred))/len(y), 'confusion_matrix': matrix.tolist(), 'matrix_columns': CLASSES+['INVALID_OR_MISSING']}


def expected_guess(y, probabilities):
    priors = np.array([y.count(label)/len(y) for label in CLASSES])
    p = np.asarray(probabilities)
    return {'expected_accuracy': float(priors @ p), 'expected_balanced_accuracy': float(p[priors > 0].mean()), 'expected_moving_stationary_accuracy': float(sum(priors[i]*p[j] for i in range(7) for j in range(7) if (CLASSES[i] in MOVING)==(CLASSES[j] in MOVING))), 'macro_f1_from_expected_confusion': float(np.divide(2*priors*p, priors+p, out=np.zeros(7), where=priors+p > 0).mean()), 'note': 'Analytic guessing expectation; F1 computed from expected confusion, not expectation of finite-run F1.'}


def evaluate(observations, truth_path, directory, train_labels_path):
    directory = Path(directory)
    rows = read_lines(observations)
    if hashlib.sha256(Path(observations).read_bytes()).hexdigest() != json.loads((directory/'run.json').read_text())['observations_sha256']:
        raise ValueError('Observation fingerprint mismatch')
    truth = {r['id']: r for r in read_lines(truth_path)}
    responses = read_lines(directory/'responses.jsonl')
    keys = [(r['id'], r.get('attempt', 1)) for r in responses]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate observation/attempt pairs')
    seen_valid = set()
    for r in responses:
        if r['id'] in seen_valid:
            raise ValueError('Successful predictions must never be replaced')
        if r['status'] == 'valid':
            seen_valid.add(r['id'])
    by_id = {r['id']: r for r in responses}
    if set(by_id)-{r['id'] for r in rows}:
        raise ValueError('Unexpected response IDs')
    y = [truth[r['id']]['activity'] for r in rows]
    pred = [by_id.get(r['id'], {}).get('prediction', {}).get('predicted_activity', 'INVALID') for r in rows]
    valid = [i for i,r in enumerate(rows) if by_id.get(r['id'], {}).get('status') == 'valid']
    groups = defaultdict(list)
    for i,r in enumerate(rows):
        groups[''.join(map(str,r['bits']))].append(i)
    patterns = []
    for pattern, indexes in groups.items():
        labels = Counter(y[i] for i in indexes)
        predictions = Counter(pred[i] for i in indexes if pred[i] in CLASSES)
        patterns.append({'pattern': pattern, 'n': len(indexes), 'label_counts': dict(labels), 'distinct_activities': len(labels), 'prediction_counts': dict(predictions), 'inconsistent_valid_predictions': len(predictions)>1, 'accuracy': sum(y[i]==pred[i] for i in indexes)/len(indexes), 'valid_responses': sum(pred[i] in CLASSES for i in indexes), 'valid_only_accuracy': (sum(y[i]==pred[i] for i in indexes)/sum(pred[i] in CLASSES for i in indexes)) if any(pred[i] in CLASSES for i in indexes) else None, 'contradictory_label_pairs': (len(indexes)**2-sum(n*n for n in labels.values()))//2})
    details = [by_id[rows[i]['id']]['prediction'] for i in valid]
    correct = [y[i] == pred[i] for i in valid]
    def mean(values):
        return float(np.mean(values)) if values else None
    uncertainty = {'valid_responses': len(valid), 'insufficient_information_fraction': mean([not d['sufficient_information'] for d in details]), 'mean_confidence': mean([d['confidence'] for d in details]), 'confidence_when_correct': mean([d['confidence'] for d,ok in zip(details,correct) if ok]), 'confidence_when_wrong': mean([d['confidence'] for d,ok in zip(details,correct) if not ok]), 'high_confidence_wrong_count_0_8': sum(d['confidence']>=.8 and not ok for d,ok in zip(details,correct)), 'sufficiency_accuracy': {str(flag): {'n': sum(d['sufficient_information']==flag for d in details), 'accuracy': mean([ok for d,ok in zip(details,correct) if d['sufficient_information']==flag])} for flag in [True,False]}, 'note': 'Self-reported confidence, not calibrated probability; no automatic factuality score for explanations.'}
    # Training labels only inform evaluator-side conventional prior baselines.
    with np.load(train_labels_path, allow_pickle=False) as d:
        counts = np.bincount(d['y'], minlength=7)
    majority = CLASSES[int(counts.argmax())]
    rule = ['Walking' if sum(r['bits'])>len(r['bits'])/2 else 'Sitting' for r in rows]
    usage = [r.get('usage') or {} for r in responses]
    result = {'classes': CLASSES, 'overall': classification(y,pred), 'valid_only': classification([y[i] for i in valid],[pred[i] for i in valid]) if valid else None, 'status_counts': dict(Counter(by_id.get(r['id'],{}).get('status','missing') for r in rows)), 'uncertainty': uncertainty, 'identical_inputs': {'unique_patterns': len(patterns), 'ambiguous_examples': sum(p['n'] for p in patterns if p['distinct_activities']>1), 'empirical_deterministic_pattern_accuracy_bound': sum(max(p['label_counts'].values()) for p in patterns)/len(rows), 'patterns': patterns}, 'baselines': {'training_majority': {'predicted_activity': majority, **classification(y,[majority]*len(y))}, 'uniform_guessing': expected_guess(y,[1/7]*7), 'training_prior_guessing': expected_guess(y,counts/counts.sum()), 'fixed_binary_rule': {'rule': 'mean(bit)>0.5 -> Walking, otherwise Sitting; declared before evaluation', **classification(y,rule)}}, 'usage': {'requests': len(responses), 'total_tokens': sum(u.get('total_tokens',0) or 0 for u in usage), 'prompt_tokens': sum(u.get('prompt_tokens',0) or 0 for u in usage), 'completion_tokens': sum(u.get('completion_tokens',0) or 0 for u in usage), 'reported_cost_usd': sum(u.get('cost',0) or 0 for u in usage), 'responses_with_cost': sum(u.get('cost') is not None for u in usage)}}
    for field in ['subject','recording']:
        keys = sorted({str(truth[r['id']][field]) for r in rows})
        result['by_'+field] = {}
        for key in keys:
            ids = [i for i,r in enumerate(rows) if str(truth[r['id']][field])==key]
            result['by_'+field][key] = classification([y[i] for i in ids],[pred[i] for i in ids])
    if valid:
        valid_y = [y[i] for i in valid]
        result['baselines_valid_only'] = {'training_majority': classification(valid_y,[majority]*len(valid)), 'fixed_binary_rule': classification(valid_y,[rule[i] for i in valid]), 'uniform_guessing': expected_guess(valid_y,[1/7]*7), 'training_prior_guessing': expected_guess(valid_y,counts/counts.sum())}
        result['valid_subset_pattern_bound'] = sum(max(Counter(y[i] for i in indexes if pred[i] in CLASSES).values(),default=0) for indexes in groups.values())/len(valid)
        result['by_subject_valid_only'] = {}
        for subject in sorted({truth[rows[i]['id']]['subject'] for i in valid}):
            ids = [i for i in valid if truth[rows[i]['id']]['subject']==subject]
            result['by_subject_valid_only'][str(subject)] = classification([y[i] for i in ids],[pred[i] for i in ids])
    result['group_macro_summaries'] = {field: {metric: float(np.mean([v[metric] for v in result['by_'+field].values()])) for metric in ['accuracy', 'balanced_accuracy', 'macro_f1', 'moving_stationary_accuracy']} for field in ['subject','recording']}
    result['uncertainty']['confidence_bins'] = []
    for low, high in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.000001)]:
        indexes = [i for i,d in enumerate(details) if low <= d['confidence'] < high]
        result['uncertainty']['confidence_bins'].append({'low': low, 'high': min(high,1), 'n': len(indexes), 'mean_confidence': mean([details[i]['confidence'] for i in indexes]), 'accuracy': mean([correct[i] for i in indexes])})
    dump(directory/'evaluation.json', result)
    print(json.dumps({k: result[k] for k in ['overall','status_counts','uncertainty','usage']}, indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','infer','evaluate'])
    p.add_argument('--config', default=str(ROOT/'configs/direct_llm.json'))
    p.add_argument('--data', default=str(ROOT/'data/direct-stage1'))
    p.add_argument('--run', default=str(ROOT/'runs/direct-stage1-full'))
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--retry-api-errors', action='store_true', help='With --resume, append new attempts for API errors only; never replace successful predictions')
    p.add_argument('--train-labels', default=str(ROOT/'data/pilot/train.npz'))
    a=p.parse_args();c=json.loads(Path(a.config).read_text())
    observations=Path(a.data)/('smoke_observations.jsonl' if a.smoke else 'observations.jsonl')
    if a.command=='prepare': prepare(c,a.data)
    elif a.command=='infer': infer(c,observations,a.run,a.resume,a.retry_api_errors)
    else: evaluate(observations,Path(a.data)/'truth.jsonl',a.run,a.train_labels)


if __name__=='__main__':
    main()
