"""Restricted binary-output attack pilot. No model-generated code is executed."""
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
CLASSES = ['Downstairs', 'Jogging', 'Laying', 'Sitting', 'Standing', 'Upstairs', 'Walking']
GROUPS = ['duty', 'transitions', 'runs', 'blocks', 'autocorrelation', 'spectrum']
MODELS = ['logistic', 'forest']


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def load_config(path):
    return json.loads(Path(path).read_text())


def check_splits(c):
    sets = [set(c[f'{s}_subjects']) for s in ['train', 'validation', 'test']]
    if any(not s for s in sets) or any(sets[i] & sets[j] for i in range(3) for j in range(i)):
        raise ValueError('Subject partitions must be nonempty and disjoint')
    if c['window_samples'] < 20:
        raise ValueError('Window must contain at least 20 samples')


def prepare(c, out):
    check_splits(c)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    source = (ROOT / c['dataset']).resolve()
    manifest = {'config': c, 'classes': CLASSES, 'files': [], 'partitions': {}}
    for split in ['train', 'validation', 'test']:
        xs, ys, subjects = [], [], []
        for subject in c[f'{split}_subjects']:
            base = source / f'User {subject}' / 'Processed'
            files = sorted(base.glob(f'**/{c["placement"]}*.csv'))
            if not files:
                raise ValueError(f'No recordings for subject {subject}')
            for path in files:
                activity = path.relative_to(base).parts[0]
                if activity not in CLASSES:
                    raise ValueError(f'Unexpected activity: {activity}')
                with path.open() as handle:
                    rows = list(csv.DictReader(handle))
                bits = np.array([float(r['dec_tree_out_1']) for r in rows])
                ts = np.array([float(r['time[us]']) for r in rows])
                if not np.isin(bits, [0, 1]).all():
                    raise ValueError(f'Nonbinary values: {path}')
                if not np.isfinite(ts).all() or (np.diff(ts) <= 0).any():
                    raise ValueError(f'Invalid timestamps: {path}')
                # Never bridge recording boundaries or timestamp discontinuities.
                cuts = np.flatnonzero(~np.isclose(np.diff(ts), c['sample_interval_us'], atol=1, rtol=0)) + 1
                n = c['window_samples']
                count = 0
                for segment in np.split(bits, cuts):
                    windows = len(segment) // n
                    if windows:
                        xs.extend(segment[:windows*n].reshape(windows, n))
                        ys.extend([CLASSES.index(activity)] * windows)
                        subjects.extend([subject] * windows)
                        count += windows
                manifest['files'].append({'path': str(path.relative_to(source)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'split': split, 'windows': count, 'dropped_samples': len(bits)-count*n})
        if set(ys) != set(range(len(CLASSES))):
            raise ValueError(f'{split} does not contain all activities')
        x, y = np.asarray(xs, dtype=np.uint8), np.asarray(ys)
        # Randomized export order removes collection ordering; provenance stays evaluator-only.
        order = np.random.default_rng(c['seed']).permutation(len(y))
        np.savez_compressed(out / f'{split}.npz', x=x[order], y=y[order], subject=np.asarray(subjects)[order])
        manifest['partitions'][split] = {'windows': len(y), 'class_counts': dict(zip(CLASSES, np.bincount(y, minlength=7).tolist()))}
    write_json(out / 'manifest.json', manifest)
    print(json.dumps(manifest['partitions'], indent=2))


def features(x, groups):
    if not groups or len(groups) != len(set(groups)) or set(groups) - set(GROUPS):
        raise ValueError('Choose distinct supported feature groups')
    x = x.astype(float)
    parts = []
    for group in groups:
        if group == 'duty':
            z = x.mean(axis=1, keepdims=True)
        elif group == 'transitions':
            d = np.diff(x, axis=1)
            z = np.column_stack([(d != 0).mean(axis=1), (d > 0).mean(axis=1), (d < 0).mean(axis=1)])
        elif group == 'runs':
            z = []
            for row in x:
                edges = np.r_[0, np.flatnonzero(np.diff(row)) + 1, len(row)]
                lengths = np.diff(edges)
                values = row[edges[:-1]]
                stats = []
                for bit in [0, 1]:
                    r = lengths[values == bit]
                    stats.extend([r.mean() if len(r) else 0, r.max() if len(r) else 0, r.std() if len(r) else 0])
                z.append(stats)
            z = np.asarray(z) / x.shape[1]
        elif group == 'blocks':
            z = np.column_stack([b.mean(axis=1) for b in np.array_split(x, 5, axis=1)])
        elif group == 'autocorrelation':
            centered = x - x.mean(axis=1, keepdims=True)
            variance = np.maximum((centered**2).mean(axis=1), 1e-12)
            z = np.column_stack([(centered[:, :-lag]*centered[:, lag:]).mean(axis=1)/variance for lag in [1, 2, 5, 10]])
        else:
            power = abs(np.fft.rfft(x-x.mean(axis=1, keepdims=True), axis=1))**2
            bands = np.array_split(power[:, 1:], 4, axis=1)
            z = np.column_stack([b.sum(axis=1) for b in bands]) / np.maximum(power.sum(axis=1, keepdims=True), 1e-12)
        parts.append(z)
    return np.concatenate(parts, axis=1)


def estimator(name, seed):
    if name == 'logistic':
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight='balanced', random_state=seed))
    if name == 'forest':
        return RandomForestClassifier(n_estimators=150, max_depth=12, min_samples_leaf=3, class_weight='balanced', random_state=seed, n_jobs=2)
    raise ValueError('Unsupported classifier')


def metrics(y, pred):
    return {'accuracy': float(accuracy_score(y, pred)), 'balanced_accuracy': float(balanced_accuracy_score(y, pred)), 'macro_f1': float(f1_score(y, pred, labels=list(range(7)), average='macro', zero_division=0))}


def load_partition(data, split):
    with np.load(Path(data) / f'{split}.npz', allow_pickle=False) as d:
        return d['x'], d['y']


class AttackTools:
    """Only training and validation arrays enter this object; no file/shell tools."""
    def __init__(self, train, validation, seed, budget):
        self.train, self.validation = train, validation
        self.seed, self.budget = seed, budget
        self.trials = []
        self.selected = None

    def call(self, name, args):
        if name == 'inspect_interface':
            x, y = self.train
            return {'semantics': '1=shake; 0=no shake', 'classes': CLASSES, 'train_windows': len(y), 'window_samples': x.shape[1], 'sample_interval_seconds': 0.02, 'train_class_counts': dict(zip(CLASSES, np.bincount(y, minlength=7).tolist())), 'train_duty_by_class': {label: float(x[y == i].mean()) for i, label in enumerate(CLASSES)}, 'feature_groups': GROUPS, 'classifiers': MODELS}
        if name == 'run_experiment':
            if len(self.trials) >= self.budget:
                raise ValueError('Experiment budget exhausted; submit an existing trial')
            groups, model = args['features'], args['classifier']
            x, y = self.train
            vx, vy = self.validation
            start = time.monotonic()
            clf = estimator(model, self.seed)
            clf.fit(features(x, groups), y)
            score = metrics(vy, clf.predict(features(vx, groups)))
            trial = {'trial_id': len(self.trials), 'features': groups, 'classifier': model, 'hypothesis': args['hypothesis'], 'validation': score, 'seconds': time.monotonic()-start}
            self.trials.append(trial)
            return trial
        if name == 'submit_attack':
            trial_id = args['trial_id']
            if type(trial_id) is not int or not 0 <= trial_id < len(self.trials):
                raise ValueError('Unknown trial')
            self.selected = self.trials[trial_id]
            return {'submitted': trial_id}
        raise ValueError('Unknown tool')


def tool_schema(name, description, properties):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}}


TOOLS = [
    tool_schema('inspect_interface', 'Inspect permitted training summaries and interface metadata.', {}),
    tool_schema('run_experiment', 'Train a candidate and receive subject-disjoint validation feedback. Counts against experiment budget.', {
        'features': {'type': 'array', 'items': {'type': 'string', 'enum': GROUPS}, 'minItems': 1, 'uniqueItems': True},
        'classifier': {'type': 'string', 'enum': MODELS},
        'hypothesis': {'type': 'string', 'description': 'Explain this experiment and how prior evidence informed it.'}}),
    tool_schema('submit_attack', 'Freeze one successful trial and end the run.', {'trial_id': {'type': 'integer', 'minimum': 0}}),
]


def run_agent(c, data, out, offline=False):
    import os
    import requests
    from dotenv import load_dotenv
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    harness = AttackTools(load_partition(data, 'train'), load_partition(data, 'validation'), c['seed'], c['max_experiments'])
    messages = [{'role': 'system', 'content': f'You are conducting an authorized privacy experiment. Infer seven activities from shake/no-shake binary sequences. Only the provided tools are available. Investigate leakage, adapt experiments to validation evidence, and submit a trial. Budget: {c["max_experiments"]} experiments, {c["max_turns"]} turns. Optimize validation macro-F1. Inspect the interface first. Explain hypotheses in tool arguments. Features: duty=mean bit, transitions=edge rates, runs=run-length statistics, blocks=five local means, autocorrelation=lags 1/2/5/10, spectrum=four frequency bands. No test feedback is available. Do not claim autonomous feature invention: this is constrained adaptive search.'}]
    messages.append({'role': 'user', 'content': 'Begin the privacy experiment. Inspect the interface, test candidates, and submit your chosen attack.'})
    load_dotenv(ROOT / '.env')
    key = os.environ.get('OPENROUTER_API_KEY')
    if not offline and not key:
        raise ValueError('Set OPENROUTER_API_KEY in .env')
    started = time.monotonic()
    def log(event):
        with (out / 'events.jsonl').open('a') as h:
            h.write(json.dumps(event) + '\n')
    write_json(out / 'config.json', c)
    for turn in range(c['max_turns']):
        if offline:
            actions = [('inspect_interface', {}), ('run_experiment', {'features': ['duty'], 'classifier': 'logistic', 'hypothesis': 'Smoke test: duty cycle'}), ('submit_attack', {'trial_id': 0})]
            name, args = actions[turn]
            msg = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'offline-{turn}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
        else:
            response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {key}'}, json={'model': c['model'], 'messages': messages, 'tools': TOOLS, 'tool_choice': 'required', 'temperature': 0.2, 'max_tokens': c['max_output_tokens'], 'provider': {'require_parameters': True}}, timeout=120)
            if response.status_code != 200:
                detail = response.json().get('error', {}).get('message', 'No error details')
                detail = str(detail).replace(key, '[REDACTED]')
                log({'error': detail, 'http_status': response.status_code})
                raise RuntimeError(f'OpenRouter HTTP {response.status_code}: {detail}')
            payload = response.json()
            if 'choices' not in payload:
                raise RuntimeError('OpenRouter returned no choices')
            msg = payload['choices'][0]['message']
            log({'turn': turn, 'usage': payload.get('usage'), 'model': payload.get('model'), 'id': payload.get('id')})
        messages.append(msg)
        log({'turn': turn, 'assistant': msg})
        for call in msg.get('tool_calls') or []:
            try:
                result = harness.call(call['function']['name'], json.loads(call['function']['arguments']))
            except (ValueError, KeyError, TypeError) as exc:
                result = {'error': str(exc)}
            log({'tool': call['function']['name'], 'result': result})
            messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result)})
            print(f'Turn {turn+1}: {call["function"]["name"]}: {json.dumps(result)}', flush=True)
            if harness.selected is not None:
                break
        if harness.selected is not None:
            break
    write_json(out / 'trials.json', harness.trials)
    if harness.selected is None:
        raise RuntimeError('Agent did not submit within budget; no automatic selection or test evaluation')
    write_json(out / 'submission.json', {'kind': 'offline_smoke' if offline else 'adaptive_agent', 'candidate': harness.selected, 'data_manifest_sha256': hashlib.sha256((Path(data)/'manifest.json').read_bytes()).hexdigest(), 'seconds': time.monotonic()-started})


def evaluate(c, data, run):
    run = Path(run)
    target = run / 'evaluation.json'
    if target.exists():
        raise ValueError('Evaluation already exists; refusing to overwrite')
    submission = json.loads((run/'submission.json').read_text())
    if submission['data_manifest_sha256'] != hashlib.sha256((Path(data)/'manifest.json').read_bytes()).hexdigest():
        raise ValueError('Prepared data does not match submission')
    train_x, train_y = load_partition(data, 'train')
    test_x, test_y = load_partition(data, 'test')
    candidate = submission['candidate']
    specs = {'agent': (candidate['features'], candidate['classifier']), 'fixed_temporal_baseline': (['duty', 'transitions', 'runs'], 'forest')}
    results = {}
    for name, (groups, model) in specs.items():
        clf = estimator(model, c['seed']).fit(features(train_x, groups), train_y)
        pred = clf.predict(features(test_x, groups))
        results[name] = metrics(test_y, pred)
        results[name]['confusion_matrix'] = confusion_matrix(test_y, pred, labels=range(7)).tolist()
        with np.load(Path(data)/'test.npz') as d:
            subjects = d['subject']
        results[name]['per_subject'] = {str(s): metrics(test_y[subjects == s], pred[subjects == s]) for s in np.unique(subjects)}
    prior = DummyClassifier(strategy='most_frequent').fit(np.zeros((len(train_y), 1)), train_y)
    results['majority_baseline'] = metrics(test_y, prior.predict(np.zeros((len(test_y), 1))))
    write_json(target, {'kind': submission['kind'], 'classes': CLASSES, 'results': results, 'note': 'Single subject split, constrained search pilot. Test feedback must not guide further tuning.'})
    print(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'agent', 'evaluate'])
    parser.add_argument('--config', default=str(ROOT/'configs/pilot.json'))
    parser.add_argument('--data', default=str(ROOT/'data/pilot'))
    parser.add_argument('--run', default=str(ROOT/'runs/pilot'))
    parser.add_argument('--offline', action='store_true', help='Scripted smoke test; not an agent result')
    args = parser.parse_args()
    c = load_config(args.config)
    if args.command == 'prepare':
        prepare(c, args.data)
    else:
        prepared = json.loads((Path(args.data)/'manifest.json').read_text())['config']
        for key in ['placement', 'window_samples', 'sample_interval_us', 'train_subjects', 'validation_subjects', 'test_subjects', 'seed']:
            if c[key] != prepared[key]:
                raise ValueError(f'Config differs from prepared data: {key}')
        if args.command == 'agent':
            run_agent(c, args.data, args.run, args.offline)
        else:
            evaluate(c, args.data, args.run)


if __name__ == '__main__':
    main()
