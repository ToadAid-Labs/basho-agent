"""
Configuration module for the crypto agent backend.

This module provides configuration settings for:
- Database connections
- Redis connections
- API endpoints
- Security settings
- Trading parameters
"""

import os
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    app_name: str = "Crypto Trading Bot"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: Optional[str] = None
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: Optional[str] = None
    redis_enabled: bool = True

    # Telegram Bot
    telegram_token: Optional[str] = None
    admin_telegram_ids: List[int] = Field(default_factory=list)

    # Trust Wallet
    trust_wallet_url: Optional[str] = "https://api.trustwallet.com/v3"

    # API Keys (optional, for specific providers)
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    coinbase_api_key: Optional[str] = None
    coinbase_api_secret: Optional[str] = None

    # Security
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Trading Parameters
    default_risk_level: int = 50
    max_positions: int = 10
    position_size_percentage: int = 10
    max_drawdown: float = 20.0

    # Market Data
    refresh_interval: int = 60  # seconds
    data_sources: list = ["binance", "coinbase"]

    # Celery (background tasks)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Notifications
    enable_notifications: bool = True
    notification_channels: list = ["telegram"]

    # CORS
    cors_origins: list = ["*"]

    @field_validator("database_url", mode="before")
    def validate_database_url(cls, v):
        """Validate database URL."""
        if v is None:
            v = os.getenv("DATABASE_URL", "sqlite:///./crypto_agent.db")
        return v

    @field_validator("redis_url", mode="before")
    def validate_redis_url(cls, v):
        """Validate Redis URL."""
        if v is None:
            v = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return v

    @field_validator("admin_telegram_ids", mode="before")
    def validate_admin_telegram_ids(cls, v):
        """Validate admin Telegram IDs."""
        if v is None:
            v = os.getenv("ADMIN_TELEGRAM_IDS", "")
        if v:
            if isinstance(v, str):
                return [int(x.strip()) for x in v.split(",") if x.strip()]
            if isinstance(v, list):
                return [int(x) for x in v]
        return []


# Create settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance."""
    return settings
