"""Development-only binary diversity audit and conventional duration sweep."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.metrics import confusion_matrix, recall_score

from experiment import ROOT, CLASSES, GROUPS, estimator, features, metrics, write_json


def load_recordings(c):
    train, validation = set(c['train_subjects']), set(c['validation_subjects'])
    if not train or not validation or train & validation:
        raise ValueError('Development subject partitions must be nonempty and disjoint')
    source = (ROOT / c['dataset']).resolve()
    records, provenance = [], []
    for split, subjects in [('train', train), ('validation', validation)]:
        for subject in sorted(subjects):
            base = source / f'User {subject}' / 'Processed'
            paths = sorted(base.glob(f'**/{c["placement"]}*.csv'))
            if not paths:
                raise ValueError(f'Missing subject {subject}')
            for path in paths:
                label = CLASSES.index(path.relative_to(base).parts[0])
                with path.open() as h:
                    rows = list(csv.DictReader(h))
                bits = np.array([float(r['dec_tree_out_1']) for r in rows])
                ts = np.array([float(r['time[us]']) for r in rows])
                if not len(bits) or not np.isin(bits, [0, 1]).all() or not np.isfinite(ts).all() or np.any(np.diff(ts) <= 0):
                    raise ValueError(f'Invalid trace {path}')
                cuts = np.flatnonzero(~np.isclose(np.diff(ts), c['sample_interval_us'], atol=1, rtol=0)) + 1
                segments = np.split(bits.astype(np.uint8), cuts)
                rid = str(path.relative_to(source))
                records.append({'id': rid, 'subject': subject, 'split': split, 'label': label, 'segments': segments})
                provenance.append({'path': rid, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'split': split, 'samples': len(bits), 'segments': len(segments), 'ones': int(bits.sum()), 'transitions': sum(int(np.count_nonzero(np.diff(s))) for s in segments), 'constant_recording': bool(np.all(bits == bits[0]))})
    return records, provenance


def make_windows(records, split, n, common_block=None):
    xs, ys, subjects = [], [], []
    source_samples = included_samples = eligible_recordings = 0
    for record in records:
        if record['split'] != split:
            continue
        count = 0
        for segment in record['segments']:
            source_samples += len(segment)
            # Same time support at every duration: only full largest-duration blocks.
            usable = len(segment) // (common_block or n) * (common_block or n)
            if usable:
                xs.extend(segment[:usable].reshape(-1, n))
                ys.extend([record['label']] * (usable // n))
                subjects.extend([record['subject']] * (usable // n))
                count += usable
        included_samples += count
        eligible_recordings += count > 0
    if not xs:
        raise ValueError(f'No eligible windows: {split}, {n}')
    return np.asarray(xs), np.asarray(ys), np.asarray(subjects), {'source_samples': source_samples, 'included_samples': included_samples, 'coverage': included_samples/source_samples, 'eligible_recordings': eligible_recordings}


def diversity(x, y):
    out = {}
    for i, label in enumerate(CLASSES):
        rows = x[y == i]
        if not len(rows):
            out[label] = {'windows': 0}
            continue
        out[label] = {'windows': len(rows), 'constant_fraction': float(np.mean(np.all(rows == rows[:, :1], axis=1))), 'mean_bit': float(rows.mean()), 'mean_transitions': float(np.count_nonzero(np.diff(rows, axis=1), axis=1).mean()), 'distinct_patterns': len(np.unique(rows, axis=0))}
    # Descriptive label-aware ceiling for exact patterns on this finite partition.
    # Not a generalization estimate, and never used to fit or select the predictor.
    counts = {}
    for row, label in zip(x, y):
        counts.setdefault(row.tobytes(), Counter())[int(label)] += 1
    ceiling = sum(max(v.values()) for v in counts.values()) / len(y)
    return {'by_class': out, 'distinct_patterns': len(counts), 'empirical_pattern_accuracy_ceiling': ceiling}


def score(y, pred, subjects):
    return {**metrics(y, pred), 'confusion_matrix': confusion_matrix(y, pred, labels=range(7)).tolist(), 'per_class_recall': dict(zip(CLASSES, recall_score(y, pred, labels=range(7), average=None, zero_division=0).tolist())), 'present_classes': [CLASSES[i] for i in np.unique(y)], 'per_subject': {str(s): metrics(y[subjects == s], pred[subjects == s]) for s in np.unique(subjects)}}


def run(c, out):
    out = Path(out)
    if out.exists():
        raise ValueError('Output directory already exists')
    durations = c['durations_seconds']
    ns = [round(d * 1e6 / c['sample_interval_us']) for d in durations]
    if any(n < 20 or max(ns) % n for n in ns):
        raise ValueError('Durations must divide the largest duration and contain at least 20 samples')
    records, provenance = load_recordings(c)
    out.mkdir(parents=True)
    write_json(out/'manifest.json', {'config': c, 'files': provenance})
    results = []
    for support in ['all_eligible', 'common_time_support']:
        for duration, n in zip(durations, ns):
            block = max(ns) if support == 'common_time_support' else None
            x, y, _, train_coverage = make_windows(records, 'train', n, block)
            vx, vy, vs, val_coverage = make_windows(records, 'validation', n, block)
            result = {'support': support, 'seconds': duration, 'train_coverage': train_coverage, 'validation_coverage': val_coverage, 'train_diversity': diversity(x, y), 'validation_diversity': diversity(vx, vy), 'models': {}}
            for name, groups, model in [('duty_logistic', ['duty'], 'logistic'), ('temporal_forest', GROUPS, 'forest')]:
                clf = estimator(model, c['seed']).fit(features(x, groups), y)
                result['models'][name] = score(vy, clf.predict(features(vx, groups)), vs)
            clf = DummyClassifier(strategy='most_frequent').fit(np.zeros((len(y), 1)), y)
            result['models']['majority'] = score(vy, clf.predict(np.zeros((len(vy), 1))), vs)
            results.append(result)
            print(support, duration, {k: round(v['macro_f1'], 4) for k, v in result['models'].items()}, flush=True)
    write_json(out/'results.json', {'config': c, 'classes': CLASSES, 'results': results})
    lines = ['# Development-only duration experiment', '', 'No test subjects were read. No LLM calls were made. Fixed baselines diagnose available binary signal before changing the agent.', '', '| Support | Seconds | Validation windows | Coverage | Duty F1 | Temporal F1 | Temporal accuracy |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        windows = sum(v['windows'] for v in r['validation_diversity']['by_class'].values())
        m = r['models']
        lines.append(f"| {r['support']} | {r['seconds']} | {windows} | {r['validation_coverage']['coverage']:.1%} | {m['duty_logistic']['macro_f1']:.3f} | {m['temporal_forest']['macro_f1']:.3f} | {m['temporal_forest']['accuracy']:.1%} |")
    lines += ['', 'Common time support retains exactly the same complete 20-second spans at every duration, preventing duration-dependent recording coverage from driving the comparison. It can exclude short stair segments; inspect present_classes and per-class coverage before interpreting seven-class results.', '', 'Macro-F1 uses all seven labels. Balanced accuracy averages recall over labels present in the evaluated subset. Windows from the same recording are correlated; this is a single development split, not an independent-window significance test.', '', 'The empirical pattern accuracy ceiling uses labels only to describe collisions among identical patterns in each partition. It is an in-sample bound, not an achievable held-out performance estimate.', '', 'Source hashes establish local provenance only. Firmware, detector-training provenance, and correspondence to the paper remain unverified.']
    lines += ['', '## Recording audit', '']
    for split in ['train', 'validation']:
        files = [f for f in provenance if f['split'] == split]
        lines.append(f"- {split}: {len(files)} recordings; {sum(f['constant_recording'] for f in files)} constant recordings; {sum(f['transitions'] for f in files)} within-segment transitions.")
    lines += ['', '## Validation binary diversity at the shortest duration', '', '| Activity | Mean bit | Constant windows | Distinct patterns |', '|---|---:|---:|---:|']
    for label, stats in results[0]['validation_diversity']['by_class'].items():
        if stats['windows']:
            lines.append(f"| {label} | {stats['mean_bit']:.4f} | {stats['constant_fraction']:.1%} | {stats['distinct_patterns']} |")
    (out/'report.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default=str(ROOT/'configs/duration_sweep.json'))
    p.add_argument('--out', default=str(ROOT/'runs/duration-sweep-001'))
    a = p.parse_args()
    run(json.loads(Path(a.config).read_text()), a.out)
