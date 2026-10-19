"""FastAPI application: middleware, error handling, and route wiring."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import ROOT, get_settings
from .errors import NotFoundError, RedirectError, ValidationError
from .routers import admin, carpool_groups, dashboard, receipts, sessions, trip_logs
from .templating import flash, render

PUBLIC_DIR = ROOT / "public"

# Served by Vercel's CDN in production (the filesystem is checked before the
# rewrite to the function); these routes exist so `uvicorn` serves them locally.
ROOT_STATIC_FILES = [
    ("/sw.js", "sw.js", "application/javascript"),
    ("/manifest.webmanifest", "manifest.webmanifest", "application/manifest+json"),
    ("/icon.png", "icon.png", "image/png"),
    ("/icon.svg", "icon.svg", "image/svg+xml"),
    ("/robots.txt", "robots.txt", "text/plain"),
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Commoter",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.resolved_session_secret(),
        session_cookie="commoter_session",
        same_site="lax",
        https_only=settings.is_production,
        max_age=60 * 60 * 24 * 30,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    # --- Error handling -----------------------------------------------------

    @app.exception_handler(RedirectError)
    async def on_redirect(request: Request, exc: RedirectError):
        if exc.alert:
            flash(request, "alert", exc.alert)
        return Response(status_code=303, headers={"Location": exc.location})

    @app.exception_handler(NotFoundError)
    async def on_not_found(request: Request, exc: NotFoundError):
        return _not_found(request)

    @app.exception_handler(ValidationError)
    async def on_validation_error(request: Request, exc: ValidationError):
        """Safety net — routers normally catch these and re-render the form."""
        if _wants_json(request):
            return JSONResponse({"errors": exc.messages}, status_code=422)
        return render(
            request, "errors/422.html", status_code=422, messages=exc.messages
        )

    @app.exception_handler(404)
    async def on_404(request: Request, exc):
        return _not_found(request)

    def _not_found(request: Request) -> Response:
        if _wants_json(request):
            return JSONResponse({"error": "Not found"}, status_code=404)
        return render(request, "errors/404.html", status_code=404)

    # --- Routes -------------------------------------------------------------

    @app.get("/up", include_in_schema=False)
    async def health():
        return JSONResponse({"status": "ok"})

    app.include_router(sessions.router)
    app.include_router(dashboard.router)
    app.include_router(carpool_groups.router)
    app.include_router(trip_logs.router)
    app.include_router(receipts.router)
    app.include_router(admin.router)

    if (PUBLIC_DIR / "assets").is_dir():
        app.mount(
            "/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets"
        )

    for url_path, filename, media_type in ROOT_STATIC_FILES:
        _register_root_file(app, url_path, filename, media_type)

    return app


def _register_root_file(
    app: FastAPI, url_path: str, filename: str, media_type: str
) -> None:
    target = PUBLIC_DIR / filename

    @app.get(url_path, include_in_schema=False, name=f"static_{filename}")
    async def serve() -> Response:
        if not target.is_file():
            raise NotFoundError(filename)
        return FileResponse(target, media_type=media_type)


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


app = create_app()
