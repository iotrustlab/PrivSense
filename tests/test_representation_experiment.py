import json
from representation_experiment import represent,shuffled,messages,DATA

def test_features_and_lossless_encoding():
    b=[0]*100+[1]*200+[0]*200
    assert list(map(int,represent(b,'R')['binary_sequence']))==b
    assert represent(b,'D')=={'fraction_ones':.4}
    assert represent(b,'T')=={'fraction_ones':.4,'transition_count':2,'max_zero_run_fraction':.4,'max_one_run_fraction':.4}

def test_disruption_and_constant_invariance():
    b=[0]*100+[1]*400
    a,seed,permutation=shuffled(b,'source',0)
    assert a!=b and sum(a)==sum(b) and len(a)==len(b)
    assert a==shuffled(b,'source',0)[0]
    assert shuffled([0]*500,'source',0)[0]==[0]*500

def test_target_payload_has_no_label_or_provenance():
    m=messages([{'activity':'Walking',**represent([1]*500,'D')}],represent([0]*500,'D'),'right-pocket')
    target=json.JSONDecoder().raw_decode(m[1]['content'].split('Unlabeled target observation:\n')[1])[0]
    assert target=={'fraction_ones':0.0}

def test_frozen_panel_has_matched_references_and_no_hidden_target_fields():
    from direct_llm import read_lines
    from representation_experiment import ROOT
    if not (DATA/'manifest.json').exists():
        import pytest
        pytest.skip('Frozen local experiment not present')
    jobs=read_lines(DATA/'requests.jsonl')
    truth={r['id']:r for r in json.loads((DATA/'truth.json').read_text())}
    refs=json.loads((DATA/'references.json').read_text())
    assert len(jobs)==50 and len(truth)==15
    for j in jobs:
        t=truth[j['target_id']];text=j['messages'][1]['content']
        exported=json.JSONDecoder().raw_decode(text.split('Labeled references from other participants:\n')[1])[0]
        target=json.JSONDecoder().raw_decode(text.split('Unlabeled target observation:\n')[1])[0]
        c='T' if j['condition']=='T-order' else j['condition']
        b=t['disrupted_bits'] if j['condition']=='T-order' else t['bits']
        assert target==represent(b,c)
        expected=[{'activity':r['activity'],**represent(r['bits'],c)} for r in refs if r['placement']==t['placement']]
        assert exported==expected and len(exported)==9
        assert 'activity' not in target and 'source' not in target
        assert all(len(r['bits'])==500 and r['subject']<8 for r in refs)
        assert t['subject'] in [8,9]
        assert 'User ' not in text and '.csv' not in text
