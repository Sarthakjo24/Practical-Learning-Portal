from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


_CSV_ENV_FIELDS = {"allowed_audio_extensions", "cors_origins", "admin_emails"}


class CsvFriendlyEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field, value, value_is_complex: bool):
        if field_name in _CSV_ENV_FIELDS and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CsvFriendlyDotEnvSettingsSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name: str, field, value, value_is_complex: bool):
        if field_name in _CSV_ENV_FIELDS and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


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
    auth0_client_id: str = "auth0-client-id"
    auth0_client_secret: str = "auth0-client-secret"
    auth0_callback_url: str = "http://localhost:8000/api/v1/auth/callback"
    auth0_logout_url: str = "http://localhost:5173/login"
    auth0_google_connection: str = "google-oauth2"
    auth0_microsoft_connection: str = "windowslive"
    frontend_base_url: str = "http://localhost:5173"

    session_secret: str = "change-me-session-secret-please-use-a-long-random-value"
    session_algorithm: str = "HS256"
    session_ttl_minutes: int = 720
    session_cookie_name: str = "plp_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_domain: str | None = None

    admin_emails: list[str] = Field(default_factory=list)

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

    @field_validator("admin_emails", mode="before")
    @classmethod
    def split_admin_emails(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item.strip().lower() for item in value if str(item).strip()]
        return [part.strip().lower() for part in value.split(",") if part.strip()]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        config = settings_cls.model_config
        return (
            init_settings,
            CsvFriendlyEnvSettingsSource(
                settings_cls,
                case_sensitive=config.get("case_sensitive"),
                env_prefix=config.get("env_prefix"),
                env_nested_delimiter=config.get("env_nested_delimiter"),
                env_ignore_empty=config.get("env_ignore_empty"),
                env_parse_none_str=config.get("env_parse_none_str"),
                env_parse_enums=config.get("env_parse_enums"),
            ),
            CsvFriendlyDotEnvSettingsSource(
                settings_cls,
                env_file=config.get("env_file"),
                env_file_encoding=config.get("env_file_encoding"),
                case_sensitive=config.get("case_sensitive"),
                env_prefix=config.get("env_prefix"),
                env_nested_delimiter=config.get("env_nested_delimiter"),
                env_ignore_empty=config.get("env_ignore_empty"),
                env_parse_none_str=config.get("env_parse_none_str"),
                env_parse_enums=config.get("env_parse_enums"),
            ),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def validate_cookie_settings(self) -> "Settings":
        allowed = {"lax", "strict", "none"}
        samesite = str(self.session_cookie_samesite or "").strip().lower()
        if samesite not in allowed:
            raise ValueError("SESSION_COOKIE_SAMESITE must be one of: lax, strict, none.")
        if samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true.")
        self.session_cookie_samesite = samesite
        return self

    @property
    def auth0_issuer(self) -> str:
        return f"https://{self.auth0_domain}/"

    @property
    def database_url(self) -> str:
        encoded_user = quote_plus(self.db_user)
        encoded_password = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{encoded_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def storage_dir(self) -> Path:
        return self._resolve_project_path(self.storage_path, PROJECT_ROOT / "storage")

    @property
    def candidate_audio_dir(self) -> Path:
        return self.storage_dir / "candidate_recordings"

    @property
    def question_audio_dir(self) -> Path:
        return self._resolve_project_path(self.question_audio_path, PROJECT_ROOT / "question_audios")

    @property
    def default_prompt_template_path(self) -> Path:
        return self._resolve_project_path(
            self.prompt_template_path,
            PROJECT_ROOT / "templates" / "evaluation_prompt.txt",
        )

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_audio_dir.mkdir(parents=True, exist_ok=True)
        self.question_audio_dir.mkdir(parents=True, exist_ok=True)
        self.default_prompt_template_path.parent.mkdir(parents=True, exist_ok=True)

    def is_admin_email(self, email: str) -> bool:
        return email.strip().lower() in set(self.admin_emails)

    def _resolve_project_path(self, raw_path: str | None, default: Path) -> Path:
        if not raw_path:
            return default.resolve()

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
