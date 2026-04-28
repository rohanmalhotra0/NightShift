"""Shared pytest fixtures.

Each test gets a fresh in-memory SQLite database and a FastAPI TestClient
with `get_db` overridden, so tests are isolated from each other and from
any local nightshift.db file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `from config import settings`, `from database import ...`, etc.
# resolve when pytest is invoked from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Force a known webhook secret + price ids before importing anything
# that reads settings. The api/payments module reads
# settings.STRIPE_WEBHOOK_SECRET at request time, so test-level
# overrides on `settings` work, but seed env first to be safe.
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
os.environ.setdefault("STRIPE_PRICE_ID_STARTER", "price_starter_test")
os.environ.setdefault("STRIPE_PRICE_ID_PRO", "price_pro_test")
os.environ.setdefault("STRIPE_PRICE_ID_MAX", "price_max_test")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from config import settings  # noqa: E402
from database.models import Base  # noqa: E402
from database import db as db_module  # noqa: E402
from main import app  # noqa: E402
from database import get_db  # noqa: E402


@pytest.fixture
def test_engine():
    """Fresh in-memory SQLite engine per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_engine):
    """FastAPI TestClient bound to the in-memory DB."""
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def _override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def webhook_secret():
    """Make sure settings has the test secret loaded for the duration."""
    original = settings.STRIPE_WEBHOOK_SECRET
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_dummy"
    yield "whsec_test_dummy"
    settings.STRIPE_WEBHOOK_SECRET = original


@pytest.fixture
def price_ids():
    """Ensure price-id settings are populated for tier mapping."""
    originals = (
        settings.STRIPE_PRICE_ID_STARTER,
        settings.STRIPE_PRICE_ID_PRO,
        settings.STRIPE_PRICE_ID_MAX,
    )
    settings.STRIPE_PRICE_ID_STARTER = "price_starter_test"
    settings.STRIPE_PRICE_ID_PRO = "price_pro_test"
    settings.STRIPE_PRICE_ID_MAX = "price_max_test"
    yield {
        "starter": "price_starter_test",
        "pro": "price_pro_test",
        "max": "price_max_test",
    }
    (
        settings.STRIPE_PRICE_ID_STARTER,
        settings.STRIPE_PRICE_ID_PRO,
        settings.STRIPE_PRICE_ID_MAX,
    ) = originals
