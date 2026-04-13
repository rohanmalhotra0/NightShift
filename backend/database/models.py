"""SQLAlchemy models for NightShift."""

from datetime import datetime
from typing import Optional
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

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    tier = Column(Enum(UserTier), default=UserTier.FREE)
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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Job preferences stored as JSON arrays
    job_titles = Column(JSON, default=list)  # ["Software Engineer", "Backend Developer"]
    locations = Column(JSON, default=list)  # ["San Francisco, CA", "Remote"]

    salary_min = Column(Integer, nullable=True)  # Minimum salary in USD
    work_auth = Column(String(100), nullable=True)  # "US Citizen", "Green Card", etc.
    remote_pref = Column(Enum(RemotePreference), default=RemotePreference.ANY)

    # Cover letter preferences
    cover_letter_template = Column(Text, nullable=True)
    generate_cover_letter = Column(Boolean, default=False)

    # Scheduling preferences
    run_hour_1 = Column(Integer, default=22)  # 10 PM
    run_hour_2 = Column(Integer, default=23)  # 11 PM

    # Google Sheets
    sheets_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="preferences")


class Resume(Base):
    """User resume storage."""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Local path or S3 path
    is_primary = Column(Boolean, default=False)
    parsed_content = Column(Text, nullable=True)  # Extracted text for Claude
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resumes")


class Job(Base):
    """Scraped job listings."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), default="linkedin")  # linkedin, indeed, etc.
    external_id = Column(String(255), index=True)  # Job ID from source

    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    url = Column(String(1000), nullable=False)

    description = Column(Text, nullable=True)
    salary_range = Column(String(100), nullable=True)
    job_type = Column(String(50), nullable=True)  # full-time, contract, etc.

    is_easy_apply = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # Unique constraint on source + external_id for deduplication
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    # Relationships
    applications = relationship("Application", back_populates="job")


class Application(Base):
    """Job application records."""
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)

    # Application data
    answers_json = Column(JSON, nullable=True)  # Field mappings used
    cover_letter_used = Column(Text, nullable=True)

    # Error tracking
    error_log = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    metrics = relationship("Metric", back_populates="application", uselist=False)


class Metric(Base):
    """Metrics and cost tracking per application."""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)

    # Token usage
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)

    # Costs
    captcha_cost = Column(Float, default=0.0)  # In USD
    claude_cost = Column(Float, default=0.0)  # In USD

    # Performance
    duration_sec = Column(Float, default=0.0)

    # Metadata
    job_site = Column(String(50), nullable=True)
    success = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="metrics")
    application = relationship("Application", back_populates="metrics")
