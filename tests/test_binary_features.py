import numpy as np
import pytest
from scripts.discover_binary_features import features,disrupt,GROUPS

def test_constant_trace_is_censored_not_periodic():
    f,d=features(np.zeros(500,dtype=int))
    assert f['fraction_ones']==0 and f['transition_count']==0
    assert f['duration_seconds']==10 and f['timestamp_span_seconds']==9.98
    assert d['runs']['zero']['samples']==[500] and d['runs']['zero']['boundary_censored']==[True]
    assert d['runs']['one']['samples']==[] and d['candidate_period_seconds'] is None

def test_known_bouts_and_chronology():
    b=np.r_[np.zeros(50),np.ones(100),np.zeros(50)].astype(int)
    f,d=features(b)
    assert d['transition_indices']==[50,150]
    assert d['runs']['one']['seconds']==[2] and d['runs']['one']['boundary_censored']==[False]
    assert f['fraction_ones']==.5 and f['transition_rate_hz']==pytest.approx(2/3.98)
    assert f['mean_one_run_fraction']==.5

def test_disruption_preserves_observed_values_and_partial_tail():
    b=np.r_[np.tile(np.r_[np.zeros(50),np.ones(50)],10),np.zeros(13)].astype(int)
    c=disrupt(b,7)
    assert len(c)==len(b) and c.sum()==b.sum()
    assert np.array_equal(c[-13:],b[-13:])
    assert not np.array_equal(c,b)
    f,d=features(b)
    assert d['candidate_period_seconds']==2 and f['candidate_period_score']==pytest.approx(1)

def test_no_explicit_duration_family_excludes_duration_proxies():
    fields=GROUPS['temporal_no_explicit_duration']
    assert 'duration_seconds' not in fields and 'transition_count' not in fields
    assert not any('run_seconds' in f for f in fields)

def test_rejects_nonbinary_instead_of_rounding():
    with pytest.raises(ValueError):features([0.5]*100)
