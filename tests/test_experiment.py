import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiment import AttackTools, GROUPS, check_splits, features, prepare


def test_constant_and_alternating_features():
    x = np.array([[0]*100, [1]*100, [0, 1]*50])
    assert np.allclose(features(x, ['duty']).ravel(), [0, 1, .5])
    assert np.allclose(features(x, ['transitions'])[:, 0], [0, 0, 1])
    assert np.isfinite(features(x, GROUPS)).all()
    assert np.allclose(features(x, ['runs'])[0], [1, 1, 0, 0, 0, 0])


def test_split_overlap_rejected():
    with pytest.raises(ValueError, match='disjoint'):
        check_splits({'train_subjects': [1], 'validation_subjects': [1], 'test_subjects': [2]})


def test_tools_budget_and_no_filesystem_access():
    x = np.random.default_rng(0).integers(0, 2, (70, 100))
    y = np.tile(np.arange(7), 10)
    h = AttackTools((x, y), (x, y), 42, 1)
    args = {'features': ['duty'], 'classifier': 'logistic', 'hypothesis': 'test'}
    assert h.call('run_experiment', args)['trial_id'] == 0
    with pytest.raises(ValueError, match='budget'):
        h.call('run_experiment', args)
    with pytest.raises(ValueError, match='Unknown tool'):
        h.call('read_file', {'path': '.env'})
    with pytest.raises(ValueError, match='Unknown trial'):
        h.call('submit_attack', {'trial_id': -1})
    assert h.call('submit_attack', {'trial_id': 0}) == {'submitted': 0}


def test_prepare_preserves_subject_boundary_and_drops_tails(tmp_path):
    from experiment import CLASSES
    dataset = tmp_path/'source'
    for subject in [1, 2, 3]:
        for activity in CLASSES:
            p = dataset/f'User {subject}'/'Processed'/activity/'right-pocket.csv'
            p.parent.mkdir(parents=True)
            p.write_text('time[us],dec_tree_out_1\n' + '\n'.join(f'{i*20000},{i%2}' for i in range(45)))
    c = {'dataset': str(dataset), 'placement': 'right-pocket', 'window_samples': 20, 'sample_interval_us': 20000, 'train_subjects': [1], 'validation_subjects': [2], 'test_subjects': [3], 'seed': 42}
    out = tmp_path/'prepared'
    prepare(c, out)
    for split, subject in [('train', 1), ('validation', 2), ('test', 3)]:
        with np.load(out/f'{split}.npz') as d:
            assert d['x'].shape == (14, 20)
            assert set(d['subject']) == {subject}
    assert all(f['dropped_samples'] == 5 for f in json.loads((out/'manifest.json').read_text())['files'])


def test_agent_loop_without_test_partition(tmp_path, monkeypatch):
    import requests
    from experiment import run_agent
    x = np.random.default_rng(0).integers(0, 2, (70, 100))
    y = np.tile(np.arange(7), 10)
    data = tmp_path/'data'
    data.mkdir()
    for split in ['train', 'validation']:
        np.savez(data/f'{split}.npz', x=x, y=y)
    (data/'manifest.json').write_text('{}')
    actions = [('inspect_interface', {}), ('run_experiment', {'features': ['duty'], 'classifier': 'logistic', 'hypothesis': 'Use observed duty statistics'}), ('submit_attack', {'trial_id': 0})]
    requests_seen = []
    def post(url, headers, json, timeout):
        requests_seen.append(json)
        name, args = actions[len(requests_seen)-1]
        class Response:
            status_code = 200
            def json(self):
                return {'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{'id': name, 'type': 'function', 'function': {'name': name, 'arguments': __import__('json').dumps(args)}}]}}], 'usage': {'total_tokens': 100}}
        return Response()
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-secret')
    out = tmp_path/'run'
    run_agent({'seed': 42, 'max_experiments': 1, 'max_turns': 3, 'model': 'mock', 'max_output_tokens': 100}, data, out)
    assert json.loads((out/'submission.json').read_text())['kind'] == 'adaptive_agent'
    log = (out/'events.jsonl').read_text()
    assert 'test-secret' not in log
    assert len(requests_seen) == 3
    assert 'validation' in log
