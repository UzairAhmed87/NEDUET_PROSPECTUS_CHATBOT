import hmac

from fastapi import Header, Request

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


def require_admin_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    settings = get_settings()
    provided = x_admin_key or ""
    expected = settings.admin_api_key
    if not expected or expected == "change-me-to-a-long-random-string":
        raise UnauthorizedError("ADMIN_API_KEY is not configured on the server.")
    if not provided or not hmac.compare_digest(provided, expected):
        raise UnauthorizedError()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
