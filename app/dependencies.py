"""FastAPI dependencies."""

from fastapi import Request

from app.config import Settings
from app.repository import StoreRepository


def get_repository(request: Request) -> StoreRepository:
    return request.app.state.repository


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
