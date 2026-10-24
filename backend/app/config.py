"""Application settings, loaded from environment variables or backend/.env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "SurakshaFD"
    # DEVELOPMENT ONLY default. Always set SECRET_KEY in .env for any shared deployment.
    secret_key: str = "dev-only-change-me-surakshafd-secret"
    access_token_minutes: int = 480

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'surakshafd.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "data" / "uploads"
    samples_dir: Path = BASE_DIR.parent / "sample_documents"
    max_upload_mb: int = 10

    # Leave empty to auto-detect (PATH, then C:\Program Files\Tesseract-OCR).
    tesseract_cmd: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Background alert job interval. 0 disables the scheduler (alerts can still be run manually).
    alert_interval_minutes: int = 60

    # Judge Demonstration Mode: live API/database evidence panel, request log and in-app demo reset.
    # Turn OFF for anything other than a local demonstration.
    demo_mode: bool = True
    log_dir: Path = BASE_DIR / "data" / "logs"

    # Which bank verification adapter to use. Only "simulated" exists in this prototype.
    bank_adapter: str = "simulated"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
