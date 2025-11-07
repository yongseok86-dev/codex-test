from fastapi import FastAPI, Request
from time import perf_counter

from app.routers import health, query
from app.deps import setup_logging, get_logger


def create_app() -> FastAPI:
    # Initialize global logging so console logs also go to file if configured
    setup_logging()
    app = FastAPI(title="NL2SQL Agent", version="0.0.1")

    # Routers
    app.include_router(health.router)
    app.include_router(query.router)

    @app.middleware("http")
    async def access_log(request: Request, call_next):  # type: ignore[override]
        t0 = perf_counter()
        response = await call_next(request)
        dt = perf_counter() - t0
        # Minimal logging to keep dependencies light in scaffold
        try:
            logger = get_logger("app.http")
            logger.info(
                "access",
                extra={
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": int(dt * 1000),
                },
            )
        except Exception:
            pass
        return response

    return app


app = create_app()
