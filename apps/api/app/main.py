from __future__ import annotations

import logging
from collections import defaultdict, deque
from time import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.routes import chat, documents, health, retrieval
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.schemas.common import ErrorBody, ErrorResponse

configure_logging(get_settings())
logger = logging.getLogger("ned.api")

app = FastAPI(
    title="NED Prospectus Assistant API",
    version="1.0.0",
    description="Grounded RAG over ingested NED University prospectus PDFs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(ip: str, limit: int) -> bool:
    now = time()
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        return True
    window.append(now)
    return False


@app.middleware("http")
async def limits_and_safety(request: Request, call_next) -> Response:
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_upload_bytes + 1024 * 1024:
                return JSONResponse(
                    status_code=413,
                    content=_error("PAYLOAD_TOO_LARGE", "Request body is too large."),
                )
        except ValueError:
            pass

    client = request.client.host if request.client else "unknown"
    if request.url.path.endswith("/chat") and _rate_limited(f"chat:{client}", settings.chat_rate_limit_per_minute):
        return JSONResponse(
            status_code=429,
            content=_error("RATE_LIMITED", "Too many chat requests. Please wait and try again."),
        )
    if request.url.path.endswith("/ingest") and _rate_limited(f"ingest:{client}", 10):
        return JSONResponse(
            status_code=429,
            content=_error("RATE_LIMITED", "Too many ingest requests. Please wait and try again."),
        )

    try:
        return await call_next(request)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error(exc.code, exc.message, exc.details),
        )
    except Exception:
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content=_error("INTERNAL_ERROR", "An unexpected server error occurred."),
        )


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error(
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": _jsonable_validation_errors(exc)},
        ),
    )


def _jsonable_validation_errors(exc: RequestValidationError) -> list[dict]:
    cleaned: list[dict] = []
    for item in exc.errors():
        row: dict = {}
        for key, value in item.items():
            if key == "ctx" and isinstance(value, dict):
                row[key] = {
                    inner_key: inner if isinstance(inner, (str, int, float, bool, type(None))) else str(inner)
                    for inner_key, inner in value.items()
                }
            elif isinstance(value, (str, int, float, bool, type(None), list, dict)):
                row[key] = value
            else:
                row[key] = str(value)
        cleaned.append(row)
    return cleaned


def _error(code: str, message: str, details: dict | None = None) -> dict:
    return ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {})).model_dump()


app.include_router(health.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(retrieval.router, prefix="/api/v1")
