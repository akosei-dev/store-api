"""Liveness information for the API process."""

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_app_settings, get_repository
from app.repository import StoreRepository

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health(
    settings: Settings = Depends(get_app_settings),
    repository: StoreRepository = Depends(get_repository),
) -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "store_count": repository.count(),
    }
