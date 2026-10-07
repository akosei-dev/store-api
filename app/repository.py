"""JSON-file persistence for store records."""

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl
    fcntl = None  # type: ignore[assignment]


class StorageError(Exception):
    """The store data file cannot be read or written."""


class StoreRepository:
    """Read and write stores in a single JSON document.

    Writes go to a temporary file in the same directory and then replace the
    destination, so a reader never sees a half-written document. A lock file
    serializes writers across processes. A thread lock covers workers inside
    this process, because an OS file lock is held by the process as a whole.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._thread_lock = threading.Lock()

    def ensure_file(self) -> None:
        with self._exclusive():
            if not self.path.exists():
                self._write_unlocked({"stores": []})

    def count(self) -> int:
        with self._exclusive():
            return len(self._read_unlocked()["stores"])

    def list_stores(
        self,
        *,
        q: str | None,
        city: str | None,
        category: str | None,
        is_active: bool | None,
        sort: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._exclusive():
            stores = [dict(store) for store in self._read_unlocked()["stores"]]

        filtered = [store for store in stores if _matches(store, q, city, category, is_active)]
        reverse = sort.startswith("-")
        key_name = sort[1:] if reverse else sort

        def sort_key(store: dict[str, Any]) -> str:
            value = store.get(key_name) or ""
            return value.casefold() if isinstance(value, str) else str(value)

        filtered.sort(key=sort_key, reverse=reverse)
        return filtered[skip : skip + limit], len(filtered)

    def get(self, store_id: str) -> dict[str, Any] | None:
        with self._exclusive():
            for store in self._read_unlocked()["stores"]:
                if store.get("id") == store_id:
                    return dict(store)
        return None

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        store = {
            **payload,
            "id": str(uuid4()),
            "created_at": now,
            "updated_at": now,
        }
        with self._exclusive():
            data = self._read_unlocked()
            data["stores"].append(store)
            self._write_unlocked(data)
        return store

    def replace(self, store_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._exclusive():
            data = self._read_unlocked()
            for index, store in enumerate(data["stores"]):
                if store.get("id") != store_id:
                    continue
                updated = {
                    **payload,
                    "id": store_id,
                    "created_at": store.get("created_at") or _utc_now(),
                    "updated_at": _utc_now(),
                }
                data["stores"][index] = updated
                self._write_unlocked(data)
                return updated
        return None

    def update(self, store_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        with self._exclusive():
            data = self._read_unlocked()
            for index, store in enumerate(data["stores"]):
                if store.get("id") != store_id:
                    continue
                updated = {
                    **store,
                    **changes,
                    "id": store_id,
                    "created_at": store.get("created_at") or _utc_now(),
                    "updated_at": _utc_now(),
                }
                data["stores"][index] = updated
                self._write_unlocked(data)
                return updated
        return None

    def delete(self, store_id: str) -> bool:
        with self._exclusive():
            data = self._read_unlocked()
            kept = [store for store in data["stores"] if store.get("id") != store_id]
            if len(kept) == len(data["stores"]):
                return False
            data["stores"] = kept
            self._write_unlocked(data)
            return True

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(str(self.path) + ".lock")
        with self._thread_lock:
            with lock_path.open("a+", encoding="utf-8") as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            self._write_unlocked({"stores": []})
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StorageError("Store data file contains invalid JSON.") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("stores"), list):
            raise StorageError("Store data file must be an object with a stores array.")
        return raw

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            Path(tmp_name).unlink(missing_ok=True)
            raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches(
    store: dict[str, Any],
    q: str | None,
    city: str | None,
    category: str | None,
    is_active: bool | None,
) -> bool:
    if category is not None and store.get("category") != category:
        return False
    if is_active is not None and store.get("is_active") is not is_active:
        return False
    address = store.get("address") or {}
    if city is not None and str(address.get("city", "")).casefold() != city.casefold():
        return False
    if q:
        haystack = " ".join(
            [
                str(store.get("name") or ""),
                str(store.get("description") or ""),
                str(address.get("city") or ""),
            ]
        ).casefold()
        if q.casefold() not in haystack:
            return False
    return True
