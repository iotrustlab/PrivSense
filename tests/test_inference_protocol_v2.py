import pytest
from inference_protocol_v2 import validate_v2

def test_valid_uncertain_prediction():
    assert validate_v2('{"predicted_activity":"Walking","confidence":0.25,"sufficient_information":false}')['confidence']==0.25

@pytest.mark.parametrize('text',[
 '{"predicted_activity":"Walking","confidence":true,"sufficient_information":false}',
 '{"predicted_activity":"Walking","confidence":NaN,"sufficient_information":false}',
 '{"predicted_activity":"Walking","confidence":1e999,"sufficient_information":false}',
 '{"predicted_activity":"Walking","confidence":1.1,"sufficient_information":false}',
 '{"predicted_activity":"Walking","confidence":0.5,"sufficient_information":"false"}',
 '{"predicted_activity":"Walking","confidence":0.5,"confidence":0.2,"sufficient_information":false}',
 '{"predicted_activity":"Running","confidence":0.5,"sufficient_information":false}',
 '{"predicted_activity":"Walking","confidence":0.5,"sufficient_information":false,"explanation":"x"}',
 '[]'])
def test_rejects_invalid_contract(text):
    with pytest.raises(ValueError):validate_v2(text)
