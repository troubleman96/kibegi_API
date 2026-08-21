from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kibegi-ai-indexer"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8090
    service_token: str = ""

    database_url: str = ""
    db_min_size: int = 1
    db_max_size: int = 8
    job_stale_minutes: int = 15
    default_batch_limit: int = 100

    redis_url: str = ""
    redis_queue_key: str = "kibegi:ai:indexing:queue"
    redis_lock_prefix: str = "kibegi:ai:indexing:lock:"

    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = ""
    minio_secure: bool = True
    minio_region: str = "us-east-1"

    ngamia_base_url: str = "https://api.ngamia.cc/v1"
    ngamia_api_key: str = ""
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 20
    embedding_timeout_seconds: float = 60.0

    max_download_bytes: int = 50 * 1024 * 1024
    chunk_size: int = 1200
    chunk_overlap: int = 150


@lru_cache
def get_settings() -> Settings:
    return Settings()
