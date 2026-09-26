import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# Use SQLite in-memory for tests
TEST_DATABASE_URL = 'sqlite://'

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def seed_exchange_rates():
    """Seed exchange rates in the test database."""
    from app.services.exchange_service import ExchangeService
    db = TestingSessionLocal()
    try:
        ExchangeService.seed_default_rates(db)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def create_usd_account(client):
    """Helper to create a USD account with $1000."""
    response = client.post('/api/v1/accounts/', json={
        'owner_name': 'Test User',
        'currency': 'USD',
        'initial_balance': 1000.00
    })
    return response.json()


@pytest.fixture
def create_two_usd_accounts(client):
    """Create two USD accounts each with $1000."""
    acc1 = client.post('/api/v1/accounts/', json={
        'owner_name': 'Alice',
        'currency': 'USD',
        'initial_balance': 1000.00
    }).json()
    acc2 = client.post('/api/v1/accounts/', json={
        'owner_name': 'Bob',
        'currency': 'USD',
        'initial_balance': 1000.00
    }).json()
    return acc1, acc2
