from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "URL Health Monitor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///./health_monitor.db"
    ASYNC_DATABASE_URL: str = "sqlite+aiosqlite:///./health_monitor.db"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    DEFAULT_CHECK_INTERVAL: int = 60
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    SLACK_WEBHOOK_URL: Optional[str] = None
    DISCORD_WEBHOOK_URL: Optional[str] = None

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    NOTIFICATION_EMAILS: Optional[str] = None

    INCIDENT_THRESHOLD: int = 3
    RESPONSE_TIME_WARNING_MS: int = 2000

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
