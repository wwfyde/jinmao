from typing import Generator

import pytest
from starlette.testclient import TestClient

from jinmao_api.main import app


@pytest.fixture
def some_data():
    return 42


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client
