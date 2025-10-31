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

# Use absolute imports instead of relative
from ai_agent_runtime.orchestrator import MultiAgentOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
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

# Mock MCP registry
class MockMCPRegistry:
    def resolve_tools(self, manifest, context):
        return []

mcp_registry = MockMCPRegistry()

# Initialize orchestrator
orchestrator = MultiAgentOrchestrator(
    ollama_url=OLLAMA_URL,
    mcp_registry=mcp_registry,
    pipeline_manifests=manifests.get("pipelines", {}),
)

# ============================================================================
# FastAPI
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    context: str = "shell"
    pipeline: str | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting AI Agent on port {AGENT_PORT}")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "healthy", "pipelines": len(manifests.get("pipelines", {}))}

@app.get("/api/pipelines")
async def list_pipelines():
    return [
        {"name": name, "description": p.get("description", "")}
        for name, p in manifests.get("pipelines", {}).items()
    ]

@app.post("/api/query")
async def query(request: QueryRequest):
    result = await orchestrator.execute(request.query, request.context)
    return result

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    messages = request.get("messages", [])
    query_text = messages[-1]["content"] if messages else ""
    result = await orchestrator.execute(query_text, "nvim")
    return {
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": result["response"]}}],
    }
