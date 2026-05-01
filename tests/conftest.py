import pytest
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient
from app.main import fastapi_app
from app.database import get_session
from app.models import User, Pet
import os

from sqlalchemy.pool import StaticPool

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    fastapi_app.dependency_overrides[get_session] = get_session_override
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()

@pytest.fixture
def mock_google_auth(mocker):
    return mocker.patch("app.api.v1.routes.google_auth")

@pytest.fixture
def test_user(session: Session):
    user = User(sub="test_sub", email="test@example.com", name="Test User")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture
def test_pet(session: Session, test_user: User):
    pet = Pet(
        name="Buddy",
        chip_id="985000000000001",
        manufacturer="Datamars / HomeAgain",
        breed="Labrador",
        owner_id=test_user.id,
        identity_status="VERIFIED"
    )
    session.add(pet)
    session.commit()
    session.refresh(pet)
    return pet
