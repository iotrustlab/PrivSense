import json

from project_paths import DEFAULT_DATASET, ROOT, dataset_path, public_path
from scripts.check_repo_privacy import findings, sensitive_filename


def test_dataset_location_is_portable_and_environment_overridable(monkeypatch, tmp_path):
    monkeypatch.setattr('project_paths.load_dotenv', lambda *args: None)
    monkeypatch.delenv('PRIVSENSE_DATASET', raising=False)
    assert dataset_path() == ROOT / DEFAULT_DATASET
    assert dataset_path('data/example') == ROOT / 'data/example'
    monkeypatch.setenv('PRIVSENSE_DATASET', str(tmp_path))
    assert dataset_path('data/example') == tmp_path


def test_published_paths_do_not_expose_local_parent_directories(tmp_path):
    assert public_path(ROOT / 'runs/example') == 'runs/example'
    assert public_path(tmp_path / 'experiment') == '<local>/experiment'


def test_privacy_check_detects_credentials_and_machine_paths_without_values():
    secret = 'sk-' + 'or-v1-' + 'a' * 64
    private_path = '/' + 'home/' + 'researcher/' + 'data'
    matches = list(findings('example\n' + secret + '\n' + private_path))
    assert matches == [('credential', 2), ('machine_path', 3)]
    assert secret not in json.dumps(matches)
    assert not list(findings('https://openrouter.ai/api/v1/chat/completions'))
    assert sensitive_filename('.env') and sensitive_filename('secrets/provider.json')
    assert not sensitive_filename('.env.example')
