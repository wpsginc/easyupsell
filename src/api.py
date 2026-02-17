from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.db import RecommendationDB


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": "api",
            "event": getattr(record, "event", "log"),
            "request_id": getattr(record, "request_id", None),
            "details": getattr(record, "details", {}),
        }
        return json.dumps(payload, separators=(",", ":"))


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("pre.api")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


LOGGER = _build_logger()


def open_readonly_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    RecommendationDB._apply_pragmas(conn)
    return conn


def _error_response(request_id: str, status_code: int, code: str, message: str, details: dict | None = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "request_id": request_id,
        },
    )


def _serialize_recommendation(row: dict[str, Any], include_enrichment: bool) -> dict[str, Any]:
    payload = {
        "target_sku": row["target_sku"],
        "target_netsuite_id": row["target_netsuite_id"],
        "target_name": row["target_name"],
        "target_price": row["target_price"],
        "score": row["score"],
        "reasoning": row["reasoning"],
        "relationship_type": row["relationship_type"],
    }
    if include_enrichment:
        payload["enrichment"] = {
            "copurchase_count": row["copurchase_count"],
            "margin": row["margin"],
            "velocity": row["velocity"],
        }
    return payload


def create_app() -> FastAPI:
    db_path = Path(os.getenv("PRE_DB_PATH", "data/recommendations.db"))
    raw_keys = os.getenv("PRE_API_KEYS", "")
    api_keys = {k.strip() for k in raw_keys.split(",") if k.strip()}
    api_key_required = os.getenv("PRE_API_KEY_REQUIRED", "true").strip().lower() != "false"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup verification: DB reachable and read-only connection contract works.
        conn = open_readonly_connection(db_path)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        yield

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            "api_request",
            extra={
                "event": "api_request",
                "request_id": request_id,
                "details": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            },
        )
        return response

    async def require_api_key(request: Request, x_api_key: str | None = Header(None)):
        if not api_key_required:
            return
        if x_api_key and x_api_key in api_keys:
            return
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        if exc.status_code == 401:
            return _error_response(request_id, 401, "unauthorized", "Missing or invalid X-API-Key")
        if exc.status_code == 404:
            return _error_response(request_id, 404, "not_found", str(exc.detail))
        return _error_response(request_id, exc.status_code, "internal_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _error_response(
            request_id,
            422,
            "validation_error",
            "Invalid request parameters",
            {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        LOGGER.error(
            "api_error",
            extra={"event": "api_error", "request_id": request_id, "details": {"error": str(exc)}},
        )
        return _error_response(request_id, 500, "internal_error", "Unexpected server error")

    @app.get("/v1/health")
    async def health(request: Request):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        try:
            db = RecommendationDB(db_path)
            stats = db.get_stats()
            return {
                "status": "ok",
                "db_path": str(db_path),
                "counts": {
                    "total": stats["total"],
                    "active": stats["active"],
                    "pending_review": stats["pending_review"],
                    "rejected": stats["rejected"],
                },
                "request_id": request_id,
            }
        except Exception as exc:  # pragma: no cover
            return {
                "status": "degraded",
                "db_path": str(db_path),
                "error": str(exc),
                "counts": {"total": 0, "active": 0, "pending_review": 0, "rejected": 0},
                "request_id": request_id,
            }

    @app.get("/v1/recommendations/category/{category_name}")
    async def by_category(
        request: Request,
        category_name: str,
        min_score: float = Query(0.7, ge=0.0, le=1.0),
        limit: int = Query(20, ge=1, le=100),
        include_enrichment: bool = Query(True),
    ):
        await require_api_key(request, request.headers.get("X-API-Key"))
        db = RecommendationDB(db_path)
        rows = db.get_active_by_category(category_name, min_score=min_score, limit=limit)
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No active recommendations for category '{category_name}'",
            )
        request_id = request.state.request_id
        return {
            "request_id": request_id,
            "source_category": category_name,
            "count": len(rows),
            "recommendations": [_serialize_recommendation(row, include_enrichment) for row in rows],
        }

    @app.get("/v1/recommendations/sku/{sku}")
    async def by_sku(
        request: Request,
        sku: str,
        include_enrichment: bool = Query(True),
    ):
        await require_api_key(request, request.headers.get("X-API-Key"))
        db = RecommendationDB(db_path)
        rows = db.get_active_by_sku(sku)
        if not rows:
            raise HTTPException(status_code=404, detail=f"No active recommendations for sku '{sku}'")
        request_id = request.state.request_id
        return {
            "request_id": request_id,
            "target_sku": sku,
            "count": len(rows),
            "recommendations": [_serialize_recommendation(row, include_enrichment) for row in rows],
        }

    @app.get("/v1/recommendations/netsuite/{netsuite_id}")
    async def by_netsuite(
        request: Request,
        netsuite_id: str,
        include_enrichment: bool = Query(True),
    ):
        await require_api_key(request, request.headers.get("X-API-Key"))
        db = RecommendationDB(db_path)
        rows = db.get_active_by_netsuite_id(netsuite_id)
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No active recommendations for netsuite id '{netsuite_id}'",
            )
        request_id = request.state.request_id
        return {
            "request_id": request_id,
            "target_netsuite_id": netsuite_id,
            "count": len(rows),
            "recommendations": [_serialize_recommendation(row, include_enrichment) for row in rows],
        }

    return app


app = create_app()
