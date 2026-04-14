"""Database module."""

from database.db import get_db, get_db_context, init_db, engine, SessionLocal
from database.supabase_client import supabase, get_supabase
from database.models import (
    Base,
    User,
    UserPrefs,
    Resume,
    Job,
    Application,
    Metric,
    ContactSubmission,
    UserTier,
    ApplicationStatus,
    RemotePreference,
)

__all__ = [
    "get_db",
    "get_db_context",
    "init_db",
    "engine",
    "SessionLocal",
    "supabase",
    "get_supabase",
    "Base",
    "User",
    "UserPrefs",
    "Resume",
    "Job",
    "Application",
    "Metric",
    "ContactSubmission",
    "UserTier",
    "ApplicationStatus",
    "RemotePreference",
]
