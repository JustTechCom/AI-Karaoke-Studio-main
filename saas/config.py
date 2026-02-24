"""
SaaS Configuration Module
Manages all SaaS-related environment variables and settings.
"""

import os
from pathlib import Path
from typing import Optional

# Base paths
BASE_DIR = Path(__file__).parent.parent
SAAS_DIR = Path(__file__).parent


class Settings:
    # App
    APP_NAME: str = os.getenv("APP_NAME", "AI Karaoke Studio")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production-very-secret-key-123")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/saas_data/karaoke_saas.db")

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # Redis / Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Stripe Price IDs (configure in Stripe Dashboard)
    STRIPE_PRICE_STARTER: str = os.getenv("STRIPE_PRICE_STARTER", "")
    STRIPE_PRICE_PRO: str = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_ENTERPRISE: str = os.getenv("STRIPE_PRICE_ENTERPRISE", "")

    # Email (SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@aikaraoke.studio")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "AI Karaoke Studio")

    # Storage
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")  # local | s3
    STORAGE_LOCAL_PATH: Path = BASE_DIR / "saas_data" / "uploads"

    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "ai-karaoke-studio")

    # Processing
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

    # Existing API keys (passed through from .env)
    ACOUST_ID: str = os.getenv("ACOUST_ID", "")
    GENIUS_API_ACCESS_TOKEN: str = os.getenv("GENIUS_API_ACCESS_TOKEN", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


# Subscription Plan Definitions
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Ücretsiz",
        "price_monthly": 0,
        "songs_per_month": 3,
        "max_duration_seconds": 300,  # 5 minutes
        "max_resolution": "720p",
        "priority": 0,
        "features": [
            "Ayda 3 şarkı",
            "720p video çıkışı",
            "Temel özellikler",
        ],
    },
    "starter": {
        "name": "Başlangıç",
        "price_monthly": 9.99,
        "songs_per_month": 20,
        "max_duration_seconds": 600,  # 10 minutes
        "max_resolution": "1080p",
        "priority": 1,
        "features": [
            "Ayda 20 şarkı",
            "1080p video çıkışı",
            "AI sözü düzeltme",
            "Genius entegrasyonu",
            "E-posta desteği",
        ],
    },
    "pro": {
        "name": "Profesyonel",
        "price_monthly": 29.99,
        "songs_per_month": 100,
        "max_duration_seconds": 900,  # 15 minutes
        "max_resolution": "1080p",
        "priority": 2,
        "features": [
            "Ayda 100 şarkı",
            "1080p video çıkışı",
            "AI sözü düzeltme",
            "Genius entegrasyonu",
            "Öncelikli işlem sırası",
            "API erişimi",
            "Öncelikli destek",
        ],
    },
    "enterprise": {
        "name": "Kurumsal",
        "price_monthly": 99.99,
        "songs_per_month": -1,  # Unlimited
        "max_duration_seconds": -1,  # Unlimited
        "max_resolution": "4k",
        "priority": 3,
        "features": [
            "Sınırsız şarkı",
            "4K video çıkışı",
            "Tüm özellikler",
            "API erişimi",
            "Webhook desteği",
            "Özel destek",
            "SLA garantisi",
        ],
    },
}


settings = Settings()
