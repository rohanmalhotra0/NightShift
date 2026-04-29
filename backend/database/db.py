"""Database connection and session management."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from config import settings
from database.models import Base


# Create engine - SQLite for local dev
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True if "postgresql" in settings.DATABASE_URL else False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Lightweight column-add migrations for SQLite/Postgres. Keyed by table.
# Older deployments predate Stripe billing columns; SQLAlchemy create_all
# never alters existing tables, so we add them here on startup.
_INLINE_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "stripe_subscription_id": "VARCHAR(255)",
        "subscription_status": "VARCHAR(32)",
        "current_period_end": "TIMESTAMP",
    },
}


def _apply_inline_migrations() -> None:
    """Add missing columns to existing tables. Idempotent.

    create_all already creates any wholly-new tables (e.g.
    stripe_webhook_events), so this only covers column additions on
    pre-existing tables that create_all won't touch.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _INLINE_MIGRATIONS.items():
        if table not in existing_tables:
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table)}
        with engine.begin() as conn:
            for col_name, col_type in columns.items():
                if col_name in existing_cols:
                    continue
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}'))


def init_db() -> None:
    """Initialize database tables and apply inline migrations."""
    Base.metadata.create_all(bind=engine)
    _apply_inline_migrations()


def get_db() -> Generator[Session, None, None]:
    """Get database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions outside of FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
