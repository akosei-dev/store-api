"""Runtime configuration loaded from the environment and .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings.

    Constructor arguments override environment variables, which override
    the .env file, which override the defaults below.
    """

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="Store API", max_length=80)
    app_version: str = Field(default="1.0.0", max_length=32)
    app_env: str = Field(default="development", max_length=32)
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    data_file: str = "stores.json"
    cors_origins: str = "*"
    log_level: str = Field(default="info", pattern=r"^(debug|info|warning|error|critical)$")

    @property
    def data_path(self) -> Path:
        """Resolve DATA_FILE against the project root when it is relative."""
        path = Path(self.data_file).expanduser()
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path.resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
