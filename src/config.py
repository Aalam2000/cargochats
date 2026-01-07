from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    ENV: str = "dev"
    APP_NAME: str = "cargochats"
    LOG_LEVEL: str = "INFO"

    API_KEY: str = "CHANGE_ME"

    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "cargochats"
    DB_USER: str = "cargochats"
    DB_PASSWORD: str = "cargochats"

    OPENAI_API_KEY: str = ""


def get_settings() -> Settings:
    return Settings()
