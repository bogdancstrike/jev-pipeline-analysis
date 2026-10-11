import importlib.util
from pathlib import Path

import pytest

from app.core.engines import EngineRegistry, load_engine_config
from tests.conftest import make_settings


def test_remote_engine_urls_override_addresses_without_changing_keys_or_local_config():
    settings = make_settings(engine_urls={'laya':'http://10.20.0.10:18881/', 'gliner':'https://models.internal/gliner'})
    original = load_engine_config(settings.engines_path)
    registry = EngineRegistry(settings, original)
    assert registry.configs['laya']['url'] == 'http://10.20.0.10:18881'
    assert registry.configs['gliner']['url'] == 'https://models.internal/gliner'
    assert registry.configs['laya']['api_key_secret'] == 'laya_api_key'
    assert registry.configs['laya']['batch'] == original['laya']['batch']
    assert original['laya']['url'] == 'http://laya:8000'
    assert EngineRegistry(make_settings(), original).configs == original


@pytest.mark.parametrize('overrides', [{'typo':'http://host'}, {'laya':'ftp://host'}, {'laya':'http://user:password@host'}, {'gliner':'http://host?key=secret'}, {'laya':'not-a-url'}])
def test_invalid_deployment_overrides_fail_early(overrides):
    settings = make_settings(engine_urls=overrides)
    with pytest.raises(ValueError, match='ENGINE_URLS'):
        EngineRegistry(settings, load_engine_config(settings.engines_path))


def test_secret_initialization_preserves_shared_keys_and_rejects_independent_app_keys(tmp_path):
    spec = importlib.util.spec_from_file_location('prod_secrets', Path(__file__).parents[2] / 'scripts/init_prod_secrets.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    with pytest.raises(ValueError, match='Copy the GPU host'):
        script.initialize(tmp_path / 'app', 'app')
    script.initialize(tmp_path / 'gpu', 'gpu')
    original = (tmp_path / 'gpu/laya_api_key').read_text()
    script.initialize(tmp_path / 'gpu', 'gpu')
    assert (tmp_path / 'gpu/laya_api_key').read_text() == original
    for key in script.MODEL_KEYS:
        (tmp_path / 'app' / key).write_bytes((tmp_path / 'gpu' / key).read_bytes())
    script.initialize(tmp_path / 'app', 'app')
    assert (tmp_path / 'app/postgres_password').read_text().strip()
    assert (tmp_path / 'app').stat().st_mode & 0o777 == 0o700
