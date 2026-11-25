"""Application settings, read from environment variables (never hard-code secrets)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    tz_offset_minutes: int
    hold_minutes: int
    sweep_seconds: int
    agent_api_key: str
    https_only: bool
    seed_demo: bool
    demo_password: str
    currency: str = "LKR"
    public_base_url: str = ""  # e.g. https://eventsphere.onrender.com - used inside the ticket QR


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./eventsphere.db"),
        secret_key=os.getenv("SECRET_KEY", "dev-only-secret-change-me"),
        tz_offset_minutes=int(os.getenv("TZ_OFFSET_MINUTES", "330")),  # Sri Lanka = UTC+05:30
        hold_minutes=int(os.getenv("WAITLIST_HOLD_MINUTES", "10")),
        sweep_seconds=int(os.getenv("SWEEP_INTERVAL_SECONDS", "30")),
        agent_api_key=os.getenv("AGENT_API_KEY", ""),
        https_only=os.getenv("HTTPS_ONLY", "0") == "1",
        seed_demo=os.getenv("SEED_DEMO", "1") == "1",
        demo_password=os.getenv("DEMO_PASSWORD", "Demo@2026!"),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"),
    )
