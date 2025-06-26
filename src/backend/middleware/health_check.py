import logging
import inspect           # ← we'll use this for coroutine detection
from typing import Awaitable, Callable, Dict

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.encoders import jsonable_encoder
from starlette import status
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware


class HealthCheckResult(BaseModel):
    ok: bool = Field(..., description="True if the check passed")
    message: str


class HealthCheckSummary(BaseModel):
    ok: bool = True
    results: Dict[str, HealthCheckResult] = Field(default_factory=dict)

    def add(self, name: str, result: HealthCheckResult):
        self.results[name] = result
        self.ok &= result.ok

    def add_default(self):
        self.add("default", HealthCheckResult(ok=True, message="always true"))

    def add_exception(self, name: str, exc: Exception):
        self.add(name, HealthCheckResult(ok=False, message=str(exc)))


class HealthCheckMiddleware(BaseHTTPMiddleware):
    _path = "/healthz"

    def __init__(
        self,
        app,
        checks: Dict[str, Callable[[], Awaitable[HealthCheckResult]]],
        password: str | None = None,
    ):
        super().__init__(app)
        self.checks = checks
        self.password = password

    async def check(self) -> HealthCheckSummary:
        summary = HealthCheckSummary()
        summary.add_default()

        for name, coro in self.checks.items():
            if not name or not coro:
                continue
            try:
                if not (callable(coro) and inspect.iscoroutinefunction(coro)):
                    raise TypeError("check is not an async callable")
                summary.add(name, await coro())
            except Exception as exc:
                logging.exception("health-check %s failed", name, exc_info=exc)
                summary.add_exception(name, exc)
        return summary

    async def dispatch(self, request: Request, call_next):
        if request.url.path.rstrip("/") == self._path:
            report = await self.check()
            code = status.HTTP_200_OK if report.ok else status.HTTP_503_SERVICE_UNAVAILABLE
            text = "OK" if report.ok else "Service Unavailable"

            if (
                self.password is not None
                and request.query_params.get("code") == self.password
            ):
                return JSONResponse(
                    content=jsonable_encoder(report.dict()),
                    status_code=code,
                )
            return PlainTextResponse(text, status_code=code)

        return await call_next(request)
