"""FastAPI application factory for the local web UI.

The web layer is a third presentation surface over ``filter_lib.design``: forms are
parsed into the shared request and render options, calculations run on a bounded
pool, and every text the page shows or downloads is the CLI's own output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..shared.eseries import SUB_PF_OPTION_LABEL
from . import routes_design, routes_export, routes_pages
from .build_form_parsing import Q_FREQUENCY_LABEL
from .execution import CalculationRunner
from .option_states import OPTION_STATES_JSON
from .request_guard import refusal
from .responses import failure_message, failure_status, json_error
from .settings import WebSettings

PACKAGE_DIR = Path(__file__).resolve().parent
# Everything the page loads is served from this app; nothing is fetched elsewhere.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(settings: WebSettings | None = None) -> FastAPI:
    """Return a configured app; the calculation pool lives for the app's lifespan."""
    settings = settings or WebSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runner = CalculationRunner(settings)
        try:
            yield
        finally:
            app.state.runner.shutdown()

    app = FastAPI(
        title="RF Filter Calculator",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.globals["version"] = __version__
    # Labels whose text error messages repeat; one definition keeps them identical.
    templates.env.globals["labels"] = {
        "allow_sub_pf": SUB_PF_OPTION_LABEL,
        "q_frequency": Q_FREQUENCY_LABEL,
    }
    # Which options apply to each Format/E-series/Raw/build/toroid combination.
    templates.env.globals["option_states"] = OPTION_STATES_JSON
    app.state.templates = templates
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    for module in (routes_pages, routes_design, routes_export):
        app.include_router(module.router)

    async def handle_expected_failure(_request: Request, exc: Exception) -> Response:
        status = failure_status(exc)
        if status is None:  # pragma: no cover - only expected failures are registered
            raise exc
        return json_error(failure_message(exc), status)

    from ..shared.build_types import BuildAnalysisCancelled
    from .execution import CalculationTimeout

    for exc_type in (ValueError, CalculationTimeout, BuildAnalysisCancelled):
        app.add_exception_handler(exc_type, handle_expected_failure)

    # Unexpected errors are answered by Starlette's outermost error middleware, outside
    # the header middleware below, so this response carries the headers itself.
    async def handle_unexpected_failure(_request: Request, _exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500, headers=SECURITY_HEADERS)

    app.add_exception_handler(Exception, handle_unexpected_failure)

    @app.middleware("http")
    async def guard_and_secure(request: Request, call_next) -> Response:
        reason = refusal(request.method, request.headers, allowed_hosts=settings.allowed_hosts)
        if reason is not None:
            response = json_error(reason, 403)
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    return app
