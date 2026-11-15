"""
Configuration management for CLI Agent AI using Pydantic Settings.
Environment variables are loaded securely from .env files or the host system.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application configuration settings.
    Never exposes secrets or API keys through serialization.
    """
    app_name: str = "CLI Agent AI"
    app_env: str = "development"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS settings - strictly restricted in production
    cors_origins: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Groq AI settings (Never hardcode credentials)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # SQLite Database connection string
    database_url: str = "sqlite:///./cli_agent.db"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return [str(origin).strip() for origin in v]
        return ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached Settings instance.
    """
    return Settings()

