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

    # --- Settings store -------------------------------------------------------------------
    # Admin overrides of module settings + run history. Either a full DATABASE_URL, or the
    # POSTGRES_* parts with the password read from a secret file. Neither = in memory.
    database_url: str = ""
    postgres_host: str = ""
    postgres_db: str = "triage"
    postgres_user: str = "triage"
    postgres_password_file: str = "/run/secrets/postgres_password"

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


    @property
    def store_url(self) -> str:
        if self.database_url or not self.postgres_host:
            return self.database_url
        from pathlib import Path
        from urllib.parse import quote
        password = Path(self.postgres_password_file).read_text().strip()
        return f"postgresql://{quote(self.postgres_user)}:{quote(password)}@{self.postgres_host}:5432/{self.postgres_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
