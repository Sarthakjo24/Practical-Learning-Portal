from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "Practical Learning Portal API"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    openai_api_key: str = "sk-placeholder"
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 45

    auth0_domain: str = "example.us.auth0.com"
    auth0_audience: str = "https://plp.api"
    auth0_client_id: str = "auth0-client-id"
    auth0_client_secret: str = "auth0-client-secret"
    auth0_admin_role: str = "plp_admin"

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "password"
    db_name: str = "practical_learning_portal"

    redis_url: str = "redis://localhost:6379/0"
    storage_path: str | None = None
    question_audio_path: str | None = None
    prompt_template_path: str | None = None

    allowed_audio_extensions: list[str] = Field(
        default_factory=lambda: [".wav", ".mp3", ".m4a", ".webm", ".ogg"]
    )
    max_audio_upload_bytes: int = 15 * 1024 * 1024
    candidate_question_count: int = 5
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:4173"]
    )
    api_rate_limit: str = "100/minute"
    sql_echo: bool = False

    faster_whisper_model: str = "small"
    faster_whisper_device: str = "auto"
    faster_whisper_compute_type: str = "int8"

    @field_validator("allowed_audio_extensions", mode="before")
    @classmethod
    def split_extensions(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, list):
            return value
        return [part.strip().lower() for part in value.split(",") if part.strip()]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, list):
            return value
        return [part.strip() for part in value.split(",") if part.strip()]

    @property
    def auth0_issuer(self) -> str:
        return f"https://{self.auth0_domain}/"

    @property
    def auth0_jwks_url(self) -> str:
        return f"{self.auth0_issuer}.well-known/jwks.json"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def storage_dir(self) -> Path:
        if self.storage_path:
            return Path(self.storage_path).expanduser().resolve()
        return (PROJECT_ROOT / "storage").resolve()

    @property
    def candidate_audio_dir(self) -> Path:
        return self.storage_dir / "candidate_recordings"

    @property
    def question_audio_dir(self) -> Path:
        if self.question_audio_path:
            return Path(self.question_audio_path).expanduser().resolve()
        return (PROJECT_ROOT / "question_audios").resolve()

    @property
    def default_prompt_template_path(self) -> Path:
        if self.prompt_template_path:
            return Path(self.prompt_template_path).expanduser().resolve()
        return (PROJECT_ROOT / "templates" / "evaluation_prompt.txt").resolve()

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_audio_dir.mkdir(parents=True, exist_ok=True)
        self.question_audio_dir.mkdir(parents=True, exist_ok=True)
        self.default_prompt_template_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
