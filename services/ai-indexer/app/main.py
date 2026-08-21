from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .db import Database
from .worker import Indexer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
database = Database(settings)
indexer = Indexer(settings, database)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    yield
    database.close()


app = FastAPI(title="Kibegi AI Indexer", version="1.0.0", lifespan=lifespan)


class IndexRequest(BaseModel):
    force: bool = False


class BatchRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=1000)
    include_done: bool = False


def require_service_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.service_token:
        return
    expected = f"Bearer {settings.service_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid service token")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if database.ping() else "degraded",
        "service": settings.app_name,
        "database": database.ping(),
        "storage_configured": indexer.s3 is not None,
        "redis_configured": indexer.redis is not None,
    }


@app.get("/v1/index/jobs/{upload_id}", dependencies=[Depends(require_service_token)])
def job_status(upload_id: UUID) -> dict[str, Any]:
    job = database.get_job(upload_id)
    if not job:
        raise HTTPException(status_code=404, detail="AI processing job not found")
    return dict(job)


@app.post("/v1/index/uploads/{upload_id}", dependencies=[Depends(require_service_token)])
def index_one(upload_id: UUID, request: IndexRequest | None = None) -> dict[str, Any]:
    return indexer.index_upload(upload_id, force=request.force if request else False)


@app.post("/v1/index/process-due", dependencies=[Depends(require_service_token)])
def process_due(request: BatchRequest | None = None) -> dict[str, Any]:
    request = request or BatchRequest()
    return indexer.process_due(request.limit, request.include_done)
