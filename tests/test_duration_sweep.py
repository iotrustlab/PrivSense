import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from duration_sweep import make_windows, diversity


def test_common_support_and_recording_boundaries():
    records = [{'split': 'train', 'label': 0, 'subject': 1, 'segments': [np.zeros(1050), np.ones(150)]}, {'split': 'validation', 'label': 1, 'subject': 8, 'segments': [np.ones(2000)]}]
    for n in [100, 250, 500, 1000]:
        x, y, s, coverage = make_windows(records, 'train', n, 1000)
        assert coverage['included_samples'] == 1000
        assert np.all(x == 0)
        assert set(s) == {1}
    x, _, _, coverage = make_windows(records, 'train', 100)
    assert coverage['included_samples'] == 1100
    assert np.all(x[-1] == 1)


def test_identical_pattern_collision_bound():
    x = np.array([[0]*100, [0]*100, [1]*100])
    r = diversity(x, np.array([0, 1, 2]))
    assert r['distinct_patterns'] == 2
    assert r['empirical_pattern_accuracy_ceiling'] == 2/3
    assert r['by_class']['Downstairs']['constant_fraction'] == 1
