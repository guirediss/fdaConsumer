from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "openfda_db"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/openfda_db"
    OPENFDA_API_KEY: str | None = None
    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/label.json"

    @model_validator(mode="before")
    @classmethod
    def build_database_url(cls, values: Any) -> Any:
        if isinstance(values, dict) and "DATABASE_URL" not in values:
            values["DATABASE_URL"] = URL.create(
                "postgresql+psycopg",
                username=values.get("POSTGRES_USER", "postgres"),
                password=values.get("POSTGRES_PASSWORD", "postgres"),
                host="db",
                port=5432,
                database=values.get("POSTGRES_DB", "openfda_db"),
            ).render_as_string(hide_password=False)
        return values


settings = Settings()
