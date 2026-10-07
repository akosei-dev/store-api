"""Store collection and item routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_repository
from app.repository import StoreRepository
from app.schemas import Category, Store, StoreCreate, StoreId, StoreList, StoreUpdate

router = APIRouter(prefix="/stores", tags=["Stores"])


def _or_404(repository: StoreRepository, store_id: str) -> dict:
    store = repository.get(store_id)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store '{store_id}' was not found.",
        )
    return store


@router.get("", response_model=StoreList, summary="List stores")
def list_stores(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Case-insensitive match against name, description, or city.",
    ),
    city: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Exact city name. Matching ignores case.",
    ),
    category: Category | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    sort: Literal["name", "-name", "created_at", "-created_at"] = Query(
        default="-created_at",
        description="Sort field. Prefix with - for descending order.",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    repository: StoreRepository = Depends(get_repository),
) -> dict:
    items, total = repository.list_stores(
        q=q,
        city=city,
        category=category.value if category else None,
        is_active=is_active,
        sort=sort,
        skip=skip,
        limit=limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post(
    "",
    response_model=Store,
    status_code=status.HTTP_201_CREATED,
    summary="Create a store",
)
def create_store(
    payload: StoreCreate,
    response: Response,
    repository: StoreRepository = Depends(get_repository),
) -> dict:
    record = repository.create(payload.model_dump(mode="json"))
    response.headers["Location"] = f"/api/v1/stores/{record['id']}"
    return record


@router.get("/{store_id}", response_model=Store, summary="Get a store")
def get_store(
    store_id: StoreId,
    repository: StoreRepository = Depends(get_repository),
) -> dict:
    return _or_404(repository, store_id)


@router.put("/{store_id}", response_model=Store, summary="Replace a store")
def replace_store(
    store_id: StoreId,
    payload: StoreCreate,
    repository: StoreRepository = Depends(get_repository),
) -> dict:
    record = repository.replace(store_id, payload.model_dump(mode="json"))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store '{store_id}' was not found.",
        )
    return record


@router.patch("/{store_id}", response_model=Store, summary="Update a store")
def update_store(
    store_id: StoreId,
    payload: StoreUpdate,
    repository: StoreRepository = Depends(get_repository),
) -> dict:
    changes = payload.model_dump(mode="json", exclude_unset=True)
    if not changes:
        return _or_404(repository, store_id)
    record = repository.update(store_id, changes)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store '{store_id}' was not found.",
        )
    return record


@router.delete(
    "/{store_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a store",
)
def delete_store(
    store_id: StoreId,
    repository: StoreRepository = Depends(get_repository),
) -> Response:
    if not repository.delete(store_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store '{store_id}' was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


from typing import Literal
from sqlalchemy import or_, func, select
from sqlalchemy.orm import Session

from app.models import Store  # adjust to your actual model import


class StoreRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_stores(
        self,
        q: str | None = None,
        city: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        sort: Literal["name", "-name", "created_at", "-created_at"] = "-created_at",
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Store], int]:
        query = select(Store)

        # --- Filters ---
        if q:
            pattern = f"%{q}%"
            query = query.where(
                or_(
                    Store.name.ilike(pattern),
                    Store.description.ilike(pattern),
                    Store.city.ilike(pattern),
                )
            )

        if city:
            query = query.where(func.lower(Store.city) == city.lower())

        if category:
            query = query.where(Store.category == category)

        if is_active is not None:
            query = query.where(Store.is_active == is_active)

        # --- Total count (before pagination) ---
        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.execute(count_query).scalar_one()

        # --- Sorting ---
        sort_map = {
            "name": Store.name.asc(),
            "-name": Store.name.desc(),
            "created_at": Store.created_at.asc(),
            "-created_at": Store.created_at.desc(),
        }
        query = query.order_by(sort_map[sort])

        # --- Pagination ---
        query = query.offset(skip).limit(limit)

        items = self.db.execute(query).scalars().all()

        return list(items), total