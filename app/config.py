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
    # The fallback model id must exist on the fallback provider. Defaults to
    # OpenCode Zen free models (deepseek-v4-flash-free, big-pickle, ...) so
    # the demo keeps working for free when the paid primary is down/limited.
    openai_fallback_api_key: str = ""
    openai_fallback_base_url: str = "https://opencode.ai/zen/v1"
    openai_fallback_model: str = "deepseek-v4-flash-free"

    # Embeddings are produced by the hosted Gemini API (free tier) — no local
    # model. Key optional at boot; upload/search fail with a clear error when
    # it is missing.
    gemini_api_key: str = ""
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "project-files"

    # Optional web search provider (Tavily). When empty, the web_search tool
    # is not offered to the model at all — same principle as any optional key.
    tavily_api_key: str = ""

    max_upload_bytes: int = 10 * 1024 * 1024

    usage_window_hours: int = 24
    usage_daily_token_limit: int = 0

    # Rolling usage windows for the composer's session/weekly budget bars.
    # Self-imposed demo limits (UX purposes), not tied to any provider
    # billing quota. 0 disables the corresponding cap.
    session_token_limit: int = 50_000
    session_token_window_hours: int = 5
    weekly_token_limit: int = 500_000
    weekly_token_window_hours: int = 168


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
