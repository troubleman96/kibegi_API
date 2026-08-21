from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kibegi-agent"
    host: str = "0.0.0.0"
    port: int = 8091
    go_api_base_url: str = "http://127.0.0.1:8080"
    go_api_service_token: str = ""
    request_timeout_seconds: float = 30.0
    mcp_path: str = "/mcp"
    mcp_allowed_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
