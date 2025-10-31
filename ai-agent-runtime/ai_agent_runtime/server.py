# ai-agent-runtime/ai_agent_runtime/server.py

import os
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from ai_agent_runtime.orchestrator import MultiAgentOrchestrator
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

# ============================================================================
# Configuration - FROM ENVIRONMENT (set by systemd)
# ============================================================================

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
AGENT_PORT = int(os.getenv("AGENT_SERVER_PORT", "8080"))
MANIFESTS_PATH = Path(os.getenv("AI_AGENT_MANIFESTS", Path.home() / ".config/ai-agent/manifests.json"))

logger.info(f"Loading manifests from: {MANIFESTS_PATH}")

# Load user-defined pipelines
manifests = {}
if MANIFESTS_PATH.exists():
    with open(MANIFESTS_PATH) as f:
        manifests = json.load(f)
    logger.info(f"Loaded {len(manifests.get('pipelines', {}))} pipelines")
else:
    logger.warning(f"Manifests file not found: {MANIFESTS_PATH}")

# Initialize orchestrator (only needs ollama_url and pipeline_manifests)
orchestrator = MultiAgentOrchestrator(
    ollama_url=OLLAMA_URL,
    pipeline_manifests=manifests.get("pipelines", {}),
)

# ============================================================================
# FastAPI App
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    context: str = "shell"
    pipeline: str | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting AI Agent on port {AGENT_PORT}")
    yield
    logger.info("Shutting down AI Agent")

app = FastAPI(
    title="AI Agent Orchestrator",
    description="Multi-agent system with intelligent routing",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
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
        }
        for name, pipeline in manifests.get("pipelines", {}).items()
    ]

@app.post("/api/query")
async def query(request: QueryRequest):
    """Query the orchestrator"""
    logger.info(f"Processing query in context '{request.context}'")

    try:
        result = await orchestrator.execute(
            query=request.query,
            context=request.context,
        )
        return result
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
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
    query_text = messages[-1]["content"] if messages else ""

    try:
        result = await orchestrator.execute(query_text, "nvim")

        return {
            "id": "local",
            "object": "chat.completion",
            "model": "supervisor",
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
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        }
    except Exception as e:
        logger.error(f"Error in chat completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT, log_level="info")
