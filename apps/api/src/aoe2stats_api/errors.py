"""The API's single error envelope, shared by every router.

`contracts/http-api.md`: "Errors use a single shape — `{"error": {"code": "...", "message":
"...", "detail": {...}}}` — with a stable machine-readable `code`. The front end branches on
`code`, never on `message`, so wording can change without breaking a client."

`APIError` is how a router raises that shape without building the JSON body itself; the handlers
registered in `app.py` are what make it true of *every* response an unhandled `HTTPException`, a
request-validation failure or an unexpected exception would otherwise render Starlette's or
FastAPI's own way.

This module holds no FastAPI `app` and imports nothing from `deps.py` or any router, on purpose:
every router this feature adds (`auth.py`, `profiles.py`, ...) needs to raise `APIError` without
importing `app.py` — which imports every router to register them — and a router importing back
from `app.py` is exactly the cycle that would create.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


class APIError(Exception):
    """A domain error carrying the envelope's three fields plus the status to answer with.

    A router raises this the way it would raise `HTTPException`; the difference is that the
    `code` here is the stable, product-meaningful string the front end is contracted to branch
    on (`no_aoe2_profile`, `not_allowlisted`, ...), never a restatement of `message`.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail if detail is not None else {}


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the envelope response body every error path answers with."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "detail": detail or {}}},
    )
