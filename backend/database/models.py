"""SQLAlchemy models for NightShift."""

from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Enum,
)
# Using String(36) for UUIDs for SQLite compatibility
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class UserTier(str, enum.Enum):
    """Subscription tiers."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    MAX = "max"
    ADMIN = "admin"


class ApplicationStatus(str, enum.Enum):
    """Application status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"


class RemotePreference(str, enum.Enum):
    """Remote work preferences."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    tier = Column(String(20), default="free")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    preferences = relationship("UserPrefs", back_populates="user", uselist=False)
    resumes = relationship("Resume", back_populates="user")
    applications = relationship("Application", back_populates="user")
    metrics = relationship("Metric", back_populates="user")


class UserPrefs(Base):
    """User job preferences."""
    __tablename__ = "user_prefs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # Job preferences stored as JSON arrays (compatible with SQLite and PostgreSQL)
    job_titles = Column(JSON, default=[])
    locations = Column(JSON, default=[])

    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    work_auth = Column(String(100), nullable=True)
    remote_preference = Column(String(20), default="any")

    # Cover letter preferences
    cover_letter_template = Column(Text, nullable=True)
    generate_cover_letter = Column(Boolean, default=False)

    # Scheduling preferences
    run_hour_1 = Column(Integer, default=22)
    run_hour_2 = Column(Integer, default=23)

    # Google Sheets
    sheets_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="preferences")


class Resume(Base):
    """User resume storage."""
    __tablename__ = "resumes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    is_default = Column(Boolean, default=False)
    parsed_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resumes")


class Job(Base):
    """Scraped job listings."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(50), default="linkedin")
    external_id = Column(String(255), index=True)

    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    url = Column(String(1000), nullable=False)

    description = Column(Text, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    job_type = Column(String(50), nullable=True)

    is_easy_apply = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    applications = relationship("Application", back_populates="job")


class Application(Base):
    """Job application records."""
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)

    status = Column(String(20), default="pending")
    resume_used = Column(String(36), ForeignKey("resumes.id"), nullable=True)

    # Application data
    answers_json = Column(JSON, nullable=True)
    cover_letter_used = Column(Text, nullable=True)

    # Error tracking
    error_log = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    metrics = relationship("Metric", back_populates="application", uselist=False)


class Metric(Base):
    """Metrics and cost tracking per application."""
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=True)

    # Token usage
    tokens_used = Column(Integer, default=0)

    # Costs
    captcha_cost = Column(Float, default=0.0)

    # Performance
    duration_seconds = Column(Integer, default=0)

    # Metadata
    job_site = Column(String(50), nullable=True)
    success = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="metrics")
    application = relationship("Application", back_populates="metrics")


class ContactSubmission(Base):
    """Contact form submissions."""
    __tablename__ = "contact_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
