from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Meal Prep Nutrition Planner")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    environment: str = os.getenv("APP_ENV", "development")


settings = Settings()
