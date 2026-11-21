import pytest
import json
from pathlib import Path
from scripts.audit_full_recording_prompts import DATA,OUT,SOURCE,read_binary,prompt,serialize

@pytest.mark.skipif(not SOURCE.is_dir(), reason="Private historical experiment fixtures are not included in the public repository")
def test_full_recording_encodings_and_extents():
    selection=json.loads((OUT/'proposed_selections.json').read_text())
    refs=[r|{'bits':read_binary(SOURCE/r['source'])[0][:,1].astype(int).tolist()} for r in selection['references']]
    r=selection['targets'][0];bits=read_binary(SOURCE/r['source'])[0][:,1].astype(int).tolist()
    target={'bits':bits,'short':bits[r['short_start']:r['short_start']+100]}
    for encoding in ['array','string']:
        text=prompt(target,refs,True,True,encoding)[1]['content']
        exported=json.JSONDecoder().raw_decode(text.split('Unlabeled target observation:\n')[1])[0]
        assert list(map(int,exported['binary_sequence']))==bits
        examples=json.JSONDecoder().raw_decode(text.split('Labeled references from other participants:\n')[1])[0]
        assert [list(map(int,x['binary_sequence'])) for x in examples]==[x['bits'] for x in refs]
        assert all(set(x)=={'activity','observation_extent','binary_sequence'} for x in examples)
        assert set(exported)=={'observation_extent','binary_sequence'}
        assert '.csv' not in text and 'User 9' not in text
    assert list(map(int,serialize(bits,'string')))==serialize(bits,'array')

@pytest.mark.skipif(not (DATA/'proposed_controls.jsonl').is_file(), reason="Private historical experiment fixtures are not included in the public repository")
def test_fixed_duration_control_is_marked_as_excerpt():
    controls=[json.loads(l) for l in (DATA/'proposed_controls.jsonl').read_text().splitlines()]
    assert len(controls)==14
    for row in controls:
        target=json.JSONDecoder().raw_decode(row['messages'][1]['content'].split('Unlabeled target observation:\n')[1])[0]
        assert target['observation_extent']=='contiguous excerpt'
        assert len(target['binary_sequence'])==500
