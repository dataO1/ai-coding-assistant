# /etc/ai-agent/runtime/server.py (Updated)

import os
import json
import asyncio
import logging
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from orchestrator import MultiAgentOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

config_dir = Path.home() / ".config" / "ai-agent"
ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
agent_port = int(os.getenv("AGENT_SERVER_PORT", "8080"))

# Load manifests
manifest_file = config_dir / "manifests.json"
if not manifest_file.exists():
    logger.error(f"Manifests not found at {manifest_file}")
    manifests = {}
else:
    with open(manifest_file) as f:
        manifests = json.load(f)

# Mock MCP registry for now (implement full version separately)
class MockMCPRegistry:
    def resolve_tools(self, manifest: Dict, context: str) -> list:
        return []

mcp_registry = MockMCPRegistry()

# Initialize orchestrator
orchestrator = MultiAgentOrchestrator(
    ollama_url=ollama_url,
    mcp_registry=mcp_registry,
    pipeline_manifests=manifests.get("pipelines", {}),
)

# ============================================================================
# FastAPI App
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    context: str = "shell"
    pipeline: Optional[str] = None  # Override with specific pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Multi-Agent Orchestrator")
    yield
    logger.info("Shutting down")

app = FastAPI(
    title="AI Agent Orchestrator",
    description="Multi-agent system with intelligent routing",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "orchestrator": "running",
        "pipelines": len(manifests.get("pipelines", {})),
    }

@app.get("/api/pipelines")
async def list_pipelines():
    """List all available pipelines"""
    return [
        {
            "name": name,
            "description": pipeline.get("description", ""),
            "model": pipeline.get("model", ""),
            "contexts": pipeline.get("contexts", []),
        }
        for name, pipeline in manifests.get("pipelines", {}).items()
    ]

@app.post("/api/query")
async def query(request: QueryRequest):
    """Query the multi-agent orchestrator"""
    logger.info(f"Received query: {request.query[:100]}...")

    try:
        result = await orchestrator.execute(
            query=request.query,
            context=request.context,
        )

        return result
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "owned_by": "local",
            }
            for name in manifests.get("pipelines", {}).keys()
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """OpenAI-compatible chat endpoint for Continue.dev, Avante"""
    messages = request.get("messages", [])
    query_text = messages[-1]["content"] if messages else "Help me"
    model = request.get("model", "supervisor")

    result = await orchestrator.execute(query_text, context="nvim")

    return {
        "id": "local",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["response"],
                },
                "finish_reason": "stop",
            }
        ],
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=agent_port, log_level="info")
