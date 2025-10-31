# ai-coding-assistant

A Nixos flake for a custom AI-powered coding assistant.

# Architecture

┌─────────────────────────────────────────────────────────────────┐
│ NixOS System Layer │
│ - Ollama service (GPU acceleration) │
│ - Global dependencies │
└──────────────────────┬──────────────────────────────────────────┘
│
┌──────────────────────▼──────────────────────────────────────────┐
│ Home Manager Layer │
│ - Flowise (user service) │
│ - MCP configuration │
│ - Global tools │
└──────────────────────┬──────────────────────────────────────────┘
│
┌──────────────────────▼──────────────────────────────────────────┐
│ Per-Project Layer (devenv/flake) │
│ - Project-specific MCP servers │
│ - Language-specific tools (LSP, linters, etc.) │
│ - Context isolation │
└──────────────────────┬──────────────────────────────────────────┘
│
┌──────────────────────▼──────────────────────────────────────────┐
│ Flowise Application │
│ │
│ ┌──────────────────────────────────────────────────┐ │
│ │ User Input │ │
│ └─────────────────┬─────────────────────────────────┘ │
│ │ │
│ ┌─────────────────▼─────────────────────────────────┐ │
│ │ MCP Root Listener (Project Detector) │ │
│ │ - Monitors workspace changes │ │
│ │ - Loads project context from flake.nix │ │
│ │ - Switches MCP server configurations │ │
│ └─────────────────┬─────────────────────────────────┘ │
│ │ │
│ ┌─────────────────▼─────────────────────────────────┐ │
│ │ Supervisor Agent (Router) │ │
│ │ Model: qwen2.5-coder:7b │ │
│ │ Task: Classify CODE_TASK / LOOKUP_TASK / HYBRID │ │
│ └─────────────┬───────────────────┬─────────────────┘ │
│ │ │ │
│ ┌──────────▼────────┐ ┌──────▼────────────┐ │
│ │ CodeExpert Worker │ │ KnowledgeScout │ │
│ │ Model: 14b/33b │ │ Model: 70b │ │
│ │ Tools: │ │ Tools: │ │
│ │ - ReadFileAST │ │ - WebSearch │ │
│ │ - LSPNavigate │ │ - SearchDocs │ │
│ │ - GetGitHistory │ │ - SummarizeWeb │ │
│ │ - LintCode │ │ │ │
│ │ - TestCoverage │ │ │ │
│ │ - SearchCode │ │ │ │
│ │ - ExecuteCode │ │ │ │
│ └───────────────────┘ └───────────────────┘ │
│ │
└─────────────────────────────────────────────────────────────────┘

# Per Project Settings

use nix

# Export project to MCP_WORKSPACE_PATH for agents/tools

export MCP_WORKSPACE_PATH=$(pwd)

# Export Nix flake project root to let MCP detect root

export NIX_PROJECT_ROOT=$(dirname $(nix eval --json .# --json | jq -r '.path'))

# Optional: Set Flowise API URL if different per project

export FLOWISE_API_URL="http://localhost:3000"

# Notify

echo "♻ Project environment loaded for directory: $(pwd)"

# Verify Setup

#!/usr/bin/env bash
set -euo pipefail

echo "1. Checking systemd Flowise service status..."
systemctl status flowise --no-pager

echo "2. Verifying Ollama models loaded..."
ollama list

echo "3. Testing environment variables..."
echo "Supervisor Agent Model: $SUPERVISOR_AGENT_MODEL"
echo "Code Agent Model: $CODE_AGENT_MODEL"
echo "Code Thinking Agent Model: $CODE_THINKING_AGENT_MODEL"
echo "Knowledge Agent Model: $KNOWLEDGE_AGENT_MODEL"

echo "4. Test curl to Flowise UI"
curl -s http://localhost:3000 | head -20

echo "Verify that MCP bind mounts exist:"
mount | grep agent-workspace || echo "No MCP workspace bind mounts found"
