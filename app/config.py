from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Memory Bank MVP"
    app_env: str = "development"
    api_port: int = 8000
    database_url: str = "sqlite:///./memory_bank.db"
    auto_link_on_create: bool = False
    auto_link_min_similarity: float = 0.35
    auto_link_search_limit: int = 20
    auto_link_max_links: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
