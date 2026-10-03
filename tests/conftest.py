import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import BigInteger, create_engine, event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-12345678901234567890")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Safely mock LangGraph PostgreSQL checkpointer before any app modules import it
checkpoint_mock = MagicMock()
from langgraph.checkpoint.memory import MemorySaver
checkpoint_mock.checkpointer = MemorySaver()
sys.modules["app.services.checkpoint"] = checkpoint_mock

# Mock email sending service
email_mock = MagicMock()
email_mock.send_group_invitation = MagicMock(return_value=True)
sys.modules["app.services.email_service"] = email_mock

# SQLite compatibility: map BigInteger to INTEGER so autoincrement works
@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

from app import database, models
from app.auth import access_token, get_current_user
from app.main import app
from fastapi.testclient import TestClient

# Configure test database engine (defaults to SQLite in-memory, supports TEST_DATABASE_URL)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def configure_sqlite_connection(conn, rec):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())
else:
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_database():
    """Create all tables before each test and drop them after."""
    models.Base.metadata.create_all(bind=test_engine)
    yield
    models.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Yield a database session for testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """TestClient with database dependency override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[database.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(database.get_db, None)


@pytest.fixture
def user1(db):
    """Primary test user."""
    user = models.Users(
        username="alice",
        email="alice@example.com",
        google_id="gid_alice_123"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user2(db):
    """Secondary test user for ownership/authorization checks."""
    user = models.Users(
        username="bob",
        email="bob@example.com",
        google_id="gid_bob_456"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user3(db):
    """Third test user (e.g. for group limits and non-members)."""
    user = models.Users(
        username="charlie",
        email="charlie@example.com",
        google_id="gid_charlie_789"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def token_user1(user1):
    return access_token(username=user1.username, id=user1.id, expires_delta=timedelta(minutes=60))


@pytest.fixture
def token_user2(user2):
    return access_token(username=user2.username, id=user2.id, expires_delta=timedelta(minutes=60))


@pytest.fixture
def token_user3(user3):
    return access_token(username=user3.username, id=user3.id, expires_delta=timedelta(minutes=60))


@pytest.fixture
def auth_client_user1(client, user1, token_user1):
    """Client authenticated as user1 via cookie and dependency override helper."""
    client.cookies.set("access_token", token_user1)
    return client


@pytest.fixture
def auth_client_user2(db, user2, token_user2):
    """Client authenticated as user2."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[database.get_db] = override_get_db
    with TestClient(app) as client2:
        client2.cookies.set("access_token", token_user2)
        yield client2
    app.dependency_overrides.pop(database.get_db, None)


@pytest.fixture
def auth_client_user3(db, user3, token_user3):
    """Client authenticated as user3."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[database.get_db] = override_get_db
    with TestClient(app) as client3:
        client3.cookies.set("access_token", token_user3)
        yield client3
    app.dependency_overrides.pop(database.get_db, None)
