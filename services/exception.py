import logging
from collections.abc import Awaitable
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception occurred")
            return JSONResponse(
                {"detail": "An error occurred. Please try again later."},
                status_code=500,
            )
