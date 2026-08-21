from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import Settings


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: ConnectionPool | None = None
        if settings.database_url:
            self.pool = ConnectionPool(
                conninfo=settings.database_url,
                min_size=settings.db_min_size,
                max_size=settings.db_max_size,
                kwargs={"row_factory": dict_row},
                open=False,
            )

    def open(self) -> None:
        if self.pool:
            self.pool.open(wait=True)

    def close(self) -> None:
        if self.pool:
            self.pool.close()

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        if not self.pool:
            raise RuntimeError("DATABASE_URL is not configured")
        with self.pool.connection() as connection:
            yield connection

    def ping(self) -> bool:
        try:
            with self.connection() as connection:
                connection.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_upload(self, upload_id: UUID) -> dict[str, Any] | None:
        with self.connection() as connection:
            return connection.execute(
                """
                SELECT id, file, file_name, file_type, file_size, is_deleted
                FROM uploads_upload WHERE id = %s
                """,
                (upload_id,),
            ).fetchone()

    def get_job(self, upload_id: UUID) -> dict[str, Any] | None:
        with self.connection() as connection:
            return connection.execute(
                """
                SELECT id, upload_id, status, chunks_created, error_message, created_at, updated_at
                FROM ai_aiprocessingjob WHERE upload_id = %s
                """,
                (upload_id,),
            ).fetchone()

    def list_candidate_uploads(self, limit: int, stale_minutes: int, include_done: bool = False) -> list[dict[str, Any]]:
        done_clause = "" if include_done else "AND (j.id IS NULL OR j.status IN ('pending', 'failed') OR (j.status = 'processing' AND j.updated_at <= NOW() - (%s * INTERVAL '1 minute')))"
        args: list[Any] = [limit]
        if not include_done:
            args = [stale_minutes, limit]
        with self.connection() as connection:
            return list(connection.execute(
                f"""
                SELECT u.id, u.file, u.file_name, u.file_type, u.file_size, u.is_deleted,
                       j.status AS job_status, j.updated_at AS job_updated_at
                FROM uploads_upload u
                LEFT JOIN ai_aiprocessingjob j ON j.upload_id = u.id
                WHERE u.is_deleted = false
                  AND (u.file_type IN ('document', 'spreadsheet', 'presentation')
                       OR LOWER(u.file_name) ~ '\\.(pdf|docx?|txt|md|rtf|csv|pptx?|xlsx?)$')
                  {done_clause}
                ORDER BY u.created_at ASC
                LIMIT %s
                """,
                args,
            ).fetchall())

    def begin_job(self, upload_id: UUID) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO ai_aiprocessingjob
                    (id, status, chunks_created, error_message, created_at, updated_at, upload_id)
                VALUES (%s, 'processing', 0, '', NOW(), NOW(), %s)
                ON CONFLICT (upload_id) DO UPDATE SET
                    status = 'processing', error_message = '', updated_at = NOW()
                RETURNING id, upload_id, status, chunks_created, error_message, created_at, updated_at
                """,
                (uuid4(), upload_id),
            ).fetchone()
            connection.commit()
            return row

    def replace_chunks(self, upload_id: UUID, chunks: list[tuple[int, str, int, list[float]]]) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM ai_documentchunk WHERE upload_id = %s", (upload_id,))
            for index, content, token_count, embedding in chunks:
                connection.execute(
                    """
                    INSERT INTO ai_documentchunk
                        (id, chunk_index, content, embedding, token_count, created_at, upload_id)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                    """,
                    (uuid4(), index, content, Jsonb(embedding), token_count, upload_id),
                )
            connection.execute(
                "UPDATE ai_aiprocessingjob SET chunks_created = %s, updated_at = NOW() WHERE upload_id = %s",
                (len(chunks), upload_id),
            )
            connection.commit()

    def finish_job(self, upload_id: UUID, status: str, chunks_created: int, error_message: str = "") -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE ai_aiprocessingjob
                SET status = %s, chunks_created = %s, error_message = %s, updated_at = NOW()
                WHERE upload_id = %s
                """,
                (status, chunks_created, error_message[:500], upload_id),
            )
            connection.commit()
