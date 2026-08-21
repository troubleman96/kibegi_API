from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import boto3
import redis
from botocore.config import Config as BotoConfig
from openai import OpenAI

from .config import Settings
from .db import Database
from .extract import chunk_text, extract_text, should_process

logger = logging.getLogger(__name__)


class Indexer:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None
        self.s3 = self._build_s3()
        self.embedding_client = self._build_embedding_client()

    def _build_s3(self):
        if not (self.settings.minio_endpoint and self.settings.minio_access_key and self.settings.minio_secret_key and self.settings.minio_bucket):
            return None
        endpoint = self.settings.minio_endpoint.strip()
        if not endpoint.startswith(("http://", "https://")):
            endpoint = ("https://" if self.settings.minio_secure else "http://") + endpoint
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name=self.settings.minio_region,
            config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
            verify=True,
        )

    def _build_embedding_client(self):
        if not self.settings.ngamia_api_key:
            return None
        return OpenAI(
            base_url=self.settings.ngamia_base_url,
            api_key=self.settings.ngamia_api_key,
            timeout=self.settings.embedding_timeout_seconds,
        )

    def _lock(self, upload_id: UUID):
        if not self.redis:
            return None
        return self.redis.lock(
            self.settings.redis_lock_prefix + str(upload_id),
            timeout=max(60, self.settings.job_stale_minutes * 60),
            blocking_timeout=0,
        )

    def _download(self, object_name: str) -> bytes:
        if not self.s3:
            raise RuntimeError("MinIO/S3 storage is not configured")
        response = self.s3.get_object(Bucket=self.settings.minio_bucket, Key=object_name)
        body = response["Body"]
        try:
            data = body.read(self.settings.max_download_bytes + 1)
        finally:
            body.close()
            body.release_conn() if hasattr(body, "release_conn") else None
        if len(data) > self.settings.max_download_bytes:
            raise ValueError(f"upload exceeds {self.settings.max_download_bytes} byte indexing limit")
        return data

    def _embed(self, texts: list[str]) -> list[list[float]]:
        zeros = [0.0] * self.settings.embedding_dimensions
        if not texts or not self.embedding_client:
            return [zeros[:] for _ in texts]
        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), self.settings.embedding_batch_size):
            batch = [text.replace("\n", " ").strip() for text in texts[offset : offset + self.settings.embedding_batch_size]]
            try:
                response = self.embedding_client.embeddings.create(model=self.settings.embedding_model, input=batch)
                values = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
                embeddings.extend(values if len(values) == len(batch) else [zeros[:] for _ in batch])
            except Exception as exc:
                logger.warning("embedding batch failed at offset %d: %s", offset, exc)
                embeddings.extend([zeros[:] for _ in batch])
        return embeddings

    def index_upload(self, upload_id: UUID, force: bool = False) -> dict[str, Any]:
        lock = self._lock(upload_id)
        if lock is not None:
            try:
                if not lock.acquire():
                    return {"upload_id": str(upload_id), "status": "already_processing"}
            except redis.RedisError as exc:
                logger.warning("Redis lock unavailable; continuing without lock: %s", exc)
                lock = None
        try:
            upload = self.database.get_upload(upload_id)
            if not upload:
                return {"upload_id": str(upload_id), "status": "not_found"}
            if upload["is_deleted"]:
                return {"upload_id": str(upload_id), "status": "skipped", "reason": "upload is deleted"}
            if not should_process(upload["file_name"], upload["file_type"]):
                return {"upload_id": str(upload_id), "status": "skipped", "reason": "unsupported file type"}
            current = self.database.get_job(upload_id)
            if current and current["status"] == "done" and current["chunks_created"] > 0 and not force:
                return {"upload_id": str(upload_id), "status": "done", "chunks_created": current["chunks_created"]}
            if current and current["status"] == "processing" and current["updated_at"]:
                stale_after = datetime.now(timezone.utc) - timedelta(minutes=self.settings.job_stale_minutes)
                updated_at = current["updated_at"].astimezone(timezone.utc)
                if updated_at > stale_after and not force:
                    return {"upload_id": str(upload_id), "status": "already_processing"}
            self.database.begin_job(upload_id)
            try:
                data = self._download(upload["file"])
                text = extract_text(data, upload["file_name"])
                if not text.strip():
                    self.database.replace_chunks(upload_id, [])
                    self.database.finish_job(upload_id, "done", 0, "No extractable text found (possibly scanned image or unsupported format)")
                    return {"upload_id": str(upload_id), "status": "done", "chunks_created": 0}
                chunks = chunk_text(text, self.settings.chunk_size, self.settings.chunk_overlap)
                if not chunks:
                    self.database.replace_chunks(upload_id, [])
                    self.database.finish_job(upload_id, "done", 0, "Text was extracted but no chunks were generated")
                    return {"upload_id": str(upload_id), "status": "done", "chunks_created": 0}
                embeddings = self._embed(chunks)
                rows = [(index, content, max(1, len(content) // 4), embeddings[index]) for index, content in enumerate(chunks)]
                self.database.replace_chunks(upload_id, rows)
                self.database.finish_job(upload_id, "done", len(rows), "")
                return {"upload_id": str(upload_id), "status": "done", "chunks_created": len(rows)}
            except Exception as exc:
                logger.exception("AI indexing failed for %s", upload_id)
                self.database.finish_job(upload_id, "failed", 0, str(exc))
                return {"upload_id": str(upload_id), "status": "failed", "error": str(exc)[:500]}
        finally:
            if lock is not None:
                try:
                    lock.release()
                except redis.RedisError:
                    pass

    def process_due(self, limit: int | None = None, include_done: bool = False) -> dict[str, Any]:
        selected = self.database.list_candidate_uploads(
            limit=limit or self.settings.default_batch_limit,
            stale_minutes=self.settings.job_stale_minutes,
            include_done=include_done,
        )
        results = [self.index_upload(row["id"], force=include_done) for row in selected]
        return {
            "selected": len(results),
            "done": sum(item.get("status") == "done" for item in results),
            "failed": sum(item.get("status") == "failed" for item in results),
            "skipped": sum(item.get("status") in {"skipped", "already_processing"} for item in results),
            "results": results,
        }
