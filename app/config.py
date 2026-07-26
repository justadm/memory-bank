from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


LOCAL_CURSOR_SIGNING_KEY = "memory-bank-local-cursor-secret"


class Settings(BaseSettings):
    app_name: str = "Memory Bank MVP"
    app_env: str = "development"
    api_port: int = 8000
    database_url: str = "sqlite:///./memory_bank.db"
    auth_enabled: bool = False
    auth_api_keys: str = ""
    auto_link_on_create: bool = False
    auto_link_min_similarity: float = 0.35
    auto_link_search_limit: int = 20
    auto_link_max_links: int = 5
    memory_change_cursor_signing_key: str = LOCAL_CURSOR_SIGNING_KEY

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_cursor_key(self) -> "Settings":
        if (
            self.app_env.lower() == "production"
            and (
                not self.memory_change_cursor_signing_key.strip()
                or self.memory_change_cursor_signing_key
                == LOCAL_CURSOR_SIGNING_KEY
            )
        ):
            raise ValueError(
                "MEMORY_CHANGE_CURSOR_SIGNING_KEY must be set to a non-default value in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
