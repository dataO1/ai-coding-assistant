"""
Configuration management for AG2 Agent Network.
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM configuration for agent network."""
    provider: str = "openai"  # openai, anthropic, ollama
    model: str = "gpt-4"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4"),
            api_key=os.getenv("LLM_API_KEY"),
            api_base=os.getenv("LLM_API_BASE"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        )


@dataclass
class DatabaseConfig:
    """Vector database configuration."""
    type: str = "chromadb"  # chromadb, qdrant, milvus
    host: str = "localhost"
    port: int = 6379
    db_path: str = "./data/vectordb"
    collection_prefix: str = "ag2_teams"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load from environment."""
        return cls(
            type=os.getenv("DB_TYPE", "chromadb"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "6379")),
            db_path=os.getenv("DB_PATH", "./data/vectordb"),
        )


@dataclass
class NetworkConfig:
    """Agent network configuration."""
    max_workers: int = 3
    docs_base_path: str = "./docs"
    enable_code_execution: bool = False
    max_retries_per_agent: int = 3
    timeout_per_team: int = 300

    @classmethod
    def from_env(cls) -> "NetworkConfig":
        """Load from environment."""
        return cls(
            max_workers=int(os.getenv("MAX_WORKERS", "3")),
            docs_base_path=os.getenv("DOCS_PATH", "./docs"),
            enable_code_execution=os.getenv("ENABLE_CODE_EXEC", "false").lower() == "true",
        )


class Config:
    """Main configuration object."""
    def __init__(self):
        self.llm = LLMConfig.from_env()
        self.database = DatabaseConfig.from_env()
        self.network = NetworkConfig.from_env()

    @staticmethod
    def create_sample_env() -> str:
        """Generate sample .env file content."""
        return """# AG2 Agent Network Configuration

# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key-here
LLM_TEMPERATURE=0.7

# Database Configuration
DB_TYPE=chromadb
DB_HOST=localhost
DB_PORT=6379
DB_PATH=./data/vectordb

# Network Configuration
MAX_WORKERS=3
DOCS_PATH=./docs
ENABLE_CODE_EXEC=false
"""


if __name__ == "__main__":
    config = Config()
    print(f"LLM Provider: {config.llm.provider}")
    print(f"Database: {config.database.type}")
    print(f"Max Workers: {config.network.max_workers}")
