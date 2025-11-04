# backend/config/settings.py - Application Settings (Pydantic)

from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file
    
    Uses Pydantic BaseSettings for validation and type safety
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "info"
    
    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Qdrant Vector Database
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    
    # Ollama LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_ORCHESTRATOR: str = "mistral:7b-instruct-v0.3"
    OLLAMA_MODEL_CODE_GEN: str = "mistral:7b-instruct-v0.3"
    OLLAMA_MODEL_EMBEDDING: str = "nomic-embed-text"  # For embeddings
    
    # Inference Parameters
    INFERENCE_TEMPERATURE: float = 0.7
    INFERENCE_MAX_TOKENS: int = 2000
    ORCHESTRATOR_TEMPERATURE: float = 0.3  # Lower temp for routing
    ORCHESTRATOR_MAX_TOKENS: int = 500
    
    # Retrieval Configuration
    RETRIEVAL_TOP_K_FILES: int = 50
    RETRIEVAL_TOP_K_FUNCTIONS: int = 20
    RETRIEVAL_MAX_TOKENS: int = 3000
    RETRIEVAL_MIN_RELEVANCE: float = 0.7
    
    # Retry Configuration
    AGENT_MAX_RETRIES: int = 3
    RETRIEVAL_TIMEOUT_SECONDS: int = 10
    AGENT_TIMEOUT_SECONDS: int = 120
    
    # Git Configuration
    GIT_BRANCH_PREFIX: str = "agentic/workflow"
    GIT_AUTHOR_NAME: str = "agentic-ide"
    GIT_AUTHOR_EMAIL: str = "bot@agentic-ide.local"
    
    # Caching
    ENABLE_RETRIEVAL_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 1800
    CACHE_DEDUP_THRESHOLD: float = 0.85
    
    # Workspace
    MAX_WORKSPACE_SIZE_MB: int = 1000
    
    # API Keys (if using external services)
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None


settings = Settings()


# .env.example - Example environment file

"""
# Application
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=debug

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# CORS
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_ORCHESTRATOR=mistral:7b-instruct-v0.3
OLLAMA_MODEL_CODE_GEN=mistral:7b-instruct-v0.3
OLLAMA_MODEL_EMBEDDING=nomic-embed-text

# Inference
INFERENCE_TEMPERATURE=0.7
INFERENCE_MAX_TOKENS=2000
ORCHESTRATOR_TEMPERATURE=0.3
ORCHESTRATOR_MAX_TOKENS=500

# Retrieval
RETRIEVAL_TOP_K_FILES=50
RETRIEVAL_TOP_K_FUNCTIONS=20
RETRIEVAL_MAX_TOKENS=3000
RETRIEVAL_MIN_RELEVANCE=0.7

# Retry
AGENT_MAX_RETRIES=3
RETRIEVAL_TIMEOUT_SECONDS=10
AGENT_TIMEOUT_SECONDS=120

# Git
GIT_BRANCH_PREFIX=agentic/workflow
GIT_AUTHOR_NAME=agentic-ide
GIT_AUTHOR_EMAIL=bot@agentic-ide.local

# Caching
ENABLE_RETRIEVAL_CACHE=true
CACHE_TTL_SECONDS=1800
CACHE_DEDUP_THRESHOLD=0.85

# Workspace
MAX_WORKSPACE_SIZE_MB=1000
"""
