"""
Configuration management for the RCRAG service.

Loads environment variables and provides typed access to configuration values.
"""

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    chromadb_api_key: str | None = Field(
        default=None, env="CHROMADB_API_KEY", description="API key for ChromaDB client"
    )
    chromadb_endpoint: str | None = Field(
        default=None, env="CHROMADB_ENDPOINT", description="Endpoint URL for ChromaDB client"
    )
    # Add other configuration variables here as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
