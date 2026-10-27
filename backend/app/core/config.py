from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "VeriSight Document Intelligence"
    environment: str = "development"
    secret_key: str = "change-this-development-secret-before-production"
    database_url: str = "sqlite:///./verisight.db"
    access_token_expire_minutes: int = 480
    upload_dir: Path = PROJECT_ROOT / "uploads"
    report_dir: Path = PROJECT_ROOT / "reports"
    max_upload_mb: int = 15
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    ocr_languages: str = "en"
    enable_transformers: bool = False
    hf_document_model: str = "facebook/bart-large-mnli"
    hf_explanation_model: str = "google/flan-t5-small"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("upload_dir", "report_dir", mode="after")
    @classmethod
    def resolve_storage_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    return settings
