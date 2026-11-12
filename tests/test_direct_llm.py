import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import direct_llm as d


def response(**changes):
    obj={'predicted_activity':'Sitting','explanation':'Only zeros; posture is ambiguous.','alternative_activities':['Laying','Standing'],'confidence':.33,'sufficient_information':False}
    obj.update(changes)
    return json.dumps(obj)


def test_exact_observation_and_minimal_prompt():
    bits=[0,1]*50
    m=d.messages(bits)
    assert len(m)==2
    assert json.dumps(bits) in m[1]['content']
    for forbidden in ['50 Hz','pocket','User 8','train_duty','validation','filename']:
        assert forbidden not in json.dumps(m)
    with pytest.raises(ValueError):d.messages([0]*99)
    with pytest.raises(ValueError):d.messages([2]*100)


@pytest.mark.parametrize('change',[{'predicted_activity':'Running'},{'confidence':True},{'confidence':1.1},{'sufficient_information':'false'},{'alternative_activities':['Sitting']},{'extra':'data'}])
def test_schema_rejects_invalid(change):
    with pytest.raises(ValueError):d.validate(response(**change))


def test_stateless_request_has_no_tools_labels_or_credentials_in_log(monkeypatch):
    calls=[]
    class R:
        status_code=200
        def json(self):
            return {'choices':[{'message':{'content':response()},'finish_reason':'stop'}],'usage':{'total_tokens':100,'cost':.001},'model':'mock'}
    def post(url,headers,json,timeout):
        calls.append(json)
        return R()
    monkeypatch.setattr(d.requests,'post',post)
    c={'model':'mock','temperature':.1,'max_tokens':600,'timeout_seconds':60}
    for i in range(2):
        result=d.request_one({'id':str(i),'bits':[0]*100},c,'secret-key')
        assert result['status']=='valid'
        assert 'secret-key' not in json.dumps(result)
    assert calls[0]==calls[1]
    assert 'tools' not in calls[0]
    assert len(calls[1]['messages'])==2


def test_invalid_predictions_count_as_errors():
    m=d.classification(['Sitting','Walking'],['INVALID','Walking'])
    assert m['accuracy']==.5
    assert m['balanced_accuracy']==.5
    assert m['moving_stationary_accuracy']==.5
    assert m['confusion_matrix'][3][7]==1


def test_evaluator_identical_inputs_and_missing_response(tmp_path):
    import hashlib
    import numpy as np
    rows=[{'id':'a','bits':[0]*100},{'id':'b','bits':[0]*100},{'id':'c','bits':[1]*100}]
    observations=tmp_path/'observations.jsonl';d.write_lines(observations,rows)
    truth=tmp_path/'truth.jsonl'
    d.write_lines(truth,[{'id':r['id'],'activity':label,'subject':8,'recording':'r'+r['id']} for r,label in zip(rows,['Sitting','Standing','Walking'])])
    run=tmp_path/'run';run.mkdir()
    d.dump(run/'run.json',{'observations_sha256':hashlib.sha256(observations.read_bytes()).hexdigest()})
    d.write_lines(run/'responses.jsonl',[{'id':'a','status':'valid','prediction':json.loads(response())},{'id':'b','status':'valid','prediction':json.loads(response(predicted_activity='Standing',alternative_activities=['Sitting']))}])
    train=tmp_path/'train.npz';np.savez(train,y=np.arange(7))
    d.evaluate(observations,truth,run,train)
    result=json.loads((run/'evaluation.json').read_text())
    assert result['identical_inputs']['unique_patterns']==2
    assert result['identical_inputs']['ambiguous_examples']==2
    assert result['identical_inputs']['empirical_deterministic_pattern_accuracy_bound']==2/3
    assert result['identical_inputs']['patterns'][0]['inconsistent_valid_predictions']
    assert result['status_counts']['missing']==1
    assert result['overall']['accuracy']==2/3


def test_preparation_exports_only_bits_and_opaque_ids(tmp_path):
    dataset=tmp_path/'source'
    for subject in [8,9]:
        for label in d.CLASSES:
            path=dataset/f'User {subject}'/'Processed'/label/'right-pocket.csv'
            path.parent.mkdir(parents=True)
            path.write_text('time[us],dec_tree_out_1\n'+'\n'.join(f'{i*20000},{int(label in d.MOVING)}' for i in range(205)))
    c={'dataset':str(dataset),'subjects':[8,9],'placement':'right-pocket','window_samples':100,'sample_interval_us':20000,'seed':42}
    out=tmp_path/'prepared';d.prepare(c,out)
    obs=d.read_lines(out/'observations.jsonl')
    assert len(obs)==28
    assert len(d.read_lines(out/'smoke_observations.jsonl'))==14
    assert all(set(r)=={'id','bits'} for r in obs)
    assert all(len(r['bits'])==100 for r in obs)
    assert all(r['bits']==[r['bits'][0]]*100 for r in obs)
    assert {r['subject'] for r in d.read_lines(out/'truth.jsonl')}=={8,9}


def test_credit_failure_stops_and_explicit_recovery_preserves_success(tmp_path,monkeypatch):
    observations=tmp_path/'observations.jsonl'
    d.write_lines(observations,[{'id':str(i),'bits':[0]*100} for i in range(4)])
    c={'concurrency':1}
    monkeypatch.setenv('OPENROUTER_API_KEY','test-secret')
    called=[]
    def fail(obs,c,key):
        called.append(obs['id'])
        if obs['id']=='1':return {'id':'1','status':'api_error','http_status':402}
        return {'id':obs['id'],'status':'valid','prediction':json.loads(response())}
    monkeypatch.setattr(d,'request_one',fail)
    out=tmp_path/'run'
    d.infer(c,observations,out)
    assert called==['0','1']
    def success(obs,c,key):
        called.append(obs['id'])
        return {'id':obs['id'],'status':'valid','prediction':json.loads(response())}
    monkeypatch.setattr(d,'request_one',success)
    d.infer(c,observations,out,resume=True,retry_api_errors=True)
    assert called==['0','1','1','2','3']
    records=d.read_lines(out/'responses.jsonl')
    assert len(records)==5
    assert [r['attempt'] for r in records if r['id']=='1']==[1,2]
    assert len([r for r in records if r['id']=='0'])==1
