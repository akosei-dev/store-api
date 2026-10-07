"""Pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "stores.json"


@pytest.fixture
def client(data_file):
    application = create_app(Settings(data_file=str(data_file)))
    with TestClient(application) as test_client:
        yield test_client
