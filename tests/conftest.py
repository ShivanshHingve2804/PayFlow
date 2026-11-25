"""Test configuration and shared fixtures for PayFlow unit/API tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database() -> Iterator[None]:
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db() -> Iterator[Session]:
    """Override the app's get_db dependency to use the test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client() -> TestClient:
    """Test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def seed_exchange_rates() -> None:
    """Seed all 56 exchange rate pairs across 8 currencies in the test database."""
    from app.services.exchange_service import ExchangeService

    db = TestingSessionLocal()
    try:
        ExchangeService.seed_default_rates(db)
    finally:
        db.close()


@pytest.fixture
def create_usd_account(client: TestClient) -> dict:
    """Helper to create a USD account with $1000."""
    response = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "Test User", "currency": "USD", "initial_balance": 1000.00},
    )
    return response.json()


@pytest.fixture
def create_two_usd_accounts(client: TestClient) -> tuple[dict, dict]:
    """Create two USD accounts each with $1000."""
    acc1 = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "Alice", "currency": "USD", "initial_balance": 1000.00},
    ).json()
    acc2 = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "Bob", "currency": "USD", "initial_balance": 1000.00},
    ).json()
    return acc1, acc2
