# backend/services/__init__.py - Services Package

"""
Backend services for Agentic IDE

Includes:
- Workflow execution orchestration (LangGraph)
- Retrieval (Qdrant + embeddings)
- Agent execution (Ollama)
- Git operations
"""

from backend.services.workflow_executor import WorkflowExecutor
from backend.services.qdrant_manager import QdrantManager
from backend.services.ollama_manager import OllamaManager
from backend.services.git_manager import GitManager
from backend.services.retrieval_agent import RetrievalAgent

__all__ = [
    "WorkflowExecutor",
    "QdrantManager",
    "OllamaManager",
    "GitManager",
    "RetrievalAgent",
]
