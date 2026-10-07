"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.repository import StorageError, StoreRepository
from app.routers import health, stores

logger = logging.getLogger("store_api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    repository = StoreRepository(settings.data_path)
    repository.ensure_file()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Using store data file %s", repository.path)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "REST API for retail store locations. "
            "Records are stored in a JSON file on disk."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.debug,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health", "description": "Process status."},
            {"name": "Stores", "description": "Create, list, update, and delete stores."},
        ],
    )
    app.state.settings = settings
    app.state.repository = repository

    allow_any_origin = settings.cors_origin_list == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=not allow_any_origin,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["Health"], summary="API metadata")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health",
            "stores": "/api/v1/stores",
        }

    @app.exception_handler(StorageError)
    async def storage_error_handler(_request, exc: StorageError) -> JSONResponse:
        logger.exception("Store data file operation failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Unable to read or write the store data file."},
        )

    app.include_router(health.router)
    app.include_router(stores.router, prefix="/api/v1")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level,
    )
