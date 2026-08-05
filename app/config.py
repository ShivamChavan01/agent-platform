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

    # Optional secondary provider: used automatically when the primary LLM
    # call fails (rate limit / connection / 5xx) before any token is yielded.
    # The fallback model id must exist on the fallback provider (e.g. the
    # OpenRouter-prefixed id when falling back from an unprefixed catalog).
    openai_fallback_api_key: str = ""
    openai_fallback_base_url: str = "https://openrouter.ai/api/v1"
    openai_fallback_model: str = "deepseek/deepseek-v4-flash"

    embed_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embed_dim: int = 768

    # Load the embedding model during FastAPI lifespan startup instead of
    # lazily on first request (first load ~2.5 min — makes the first real
    # request of a fresh container look broken). Tests set this to false.
    preload_embedder: bool = True

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "project-files"

    # Optional web search provider (Tavily). When empty, the web_search tool
    # is not offered to the model at all — same principle as any optional key.
    tavily_api_key: str = ""

    max_upload_bytes: int = 10 * 1024 * 1024

    usage_window_hours: int = 24
    usage_daily_token_limit: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
