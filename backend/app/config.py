from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "JAGUAR TECHNOLOGIES"
    environment: str = "development"
    database_url: str = "sqlite:///./jaguar.db"
    jwt_secret: str = Field(default="change-this-before-production")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    admin_email: str = "admin@jaguar.local"
    admin_password: str = "ChangeMeNow!2026"
    freeradius_shared_secret: str = "change-radius-secret"
    payment_webhook_secret: str = "change-payment-secret"
    satellite_api_key: str = "change-satellite-key"
    static_dir: Path = Path(__file__).resolve().parents[2] / "frontend"


@lru_cache
def get_settings() -> Settings:
    return Settings()
