"""Proposed three-field protocol. Pure schema/validation; no API runner."""
import json,math
from direct_llm import CLASSES
VERSION='privsense-inference-v2.0'
SCHEMA={'type':'object','properties':{'predicted_activity':{'type':'string','enum':CLASSES},'confidence':{'type':'number','minimum':0,'maximum':1},'sufficient_information':{'type':'boolean'}},'required':['predicted_activity','confidence','sufficient_information'],'additionalProperties':False}
RESPONSE_FORMAT={'type':'json_schema','json_schema':{'name':'privsense_inference_v2','strict':True,'schema':SCHEMA}}

def validate_v2(text):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate key')
            d[k]=v
        return d
    def invalid_constant(value):raise ValueError('Nonfinite JSON number')
    p=json.loads(text,object_pairs_hook=pairs,parse_constant=invalid_constant)
    if not isinstance(p,dict) or set(p)!=set(SCHEMA['required']):raise ValueError('Exactly three fields required')
    if p['predicted_activity'] not in CLASSES:raise ValueError('Invalid candidate')
    c=p['confidence']
    if type(c) not in (int,float) or not math.isfinite(c) or not 0<=c<=1:raise ValueError('Invalid confidence')
    if type(p['sufficient_information']) is not bool:raise ValueError('Boolean required')
    return p
