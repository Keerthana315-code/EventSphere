
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "EventSphere"
    APP_ENV: str = "development"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./eventsphere.db"
    SECRET_KEY: str = "development-only-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
