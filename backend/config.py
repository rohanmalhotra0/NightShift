"""Configuration management for NightShift backend."""

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "sqlite:///./nightshift.db"

    # Authentication
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = ""

    # 2Captcha
    TWOCAPTCHA_API_KEY: str = ""

    # Google Services
    GOOGLE_SHEETS_CREDENTIALS: str = ""  # JSON string
    GMAIL_CREDENTIALS: str = ""  # JSON string

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Application settings
    UPLOADS_DIR: Path = Path("./uploads")
    MAX_UPLOAD_SIZE_MB: int = 10

    # LinkedIn
    LINKEDIN_COOKIES_PATH: Path = Path("./linkedin_cookies.json")

    # Scheduler
    DEFAULT_RUN_HOUR_1: int = 22  # 10 PM
    DEFAULT_RUN_HOUR_2: int = 23  # 11 PM

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

# Ensure uploads directory exists
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
