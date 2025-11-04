"""Allow running as python -m ai_agent_runtime.server"""
import sys
from ai_agent_runtime.server import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
