from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Meal Prep Nutrition Planner")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    environment: str = os.getenv("APP_ENV", "development")
    supabase_url: str | None = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL") or None
    supabase_anon_key: str | None = (
        os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY") or None
    )
    supabase_auth_timeout_seconds: float = float(os.getenv("SUPABASE_AUTH_TIMEOUT_SECONDS", "10"))


settings = Settings()
