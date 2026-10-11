"""Runtime settings, read once from the environment.

Model endpoints and their keys are not here: see `config/engines.yaml` (keys are read from
files in SECRETS_DIR, generated on first `docker compose up` by the secrets-init service).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # --- Model engines ---------------------------------------------------------------------
    # Which models exist (URLs, keys, limits, batching): one file. Which model a task uses: the
    # module's own YAML (`engine: <name>`). Secrets: files in SECRETS_DIR named in engines.yaml.
    engines_path: str = "/config/engines.yaml"

    # --- App ------------------------------------------------------------------------------
    modules_dir: str = "/config/modules"     # one <module>.yaml per module
    samples_dir: str = "/samples"           # sample CSVs (+ manifest.json) offered in the UI
    max_upload_mb: int = 512
    max_rows: int = 200_000
    max_text_chars: int = 60_000
    max_parallel_jobs: int = 1        # one GPU: a second job would only steal its time
    job_ttl_s: int = 6 * 3600
    csv_formula_escape: bool = True
    cors_origins: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
