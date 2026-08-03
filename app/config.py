from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2:///agent_platform"
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    openai_api_key: str = ""
    openai_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "deepseek/deepseek-v4-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
