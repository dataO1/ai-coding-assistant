# BACKEND_SETUP_GUIDE.md - Complete Backend Setup Instructions

## Quick Start with Nix Flakes

### Prerequisites
- NixOS or Nix package manager installed
- `nix` command with flakes support
- Git installed

### One-Command Setup

```bash
# Clone or download the backend directory
cd backend

# Enter dev environment (all dependencies installed)
nix flake enter

# Install dependencies
poetry install

# Start development server
poetry run uvicorn backend.main:app --reload

# Server running on http://localhost:8000
```

### Without Nix (Manual Setup)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\\Scripts\\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn backend.main:app --reload
```

---

## Nix Flakes Configuration

### What's Included

**flake.nix** provides:

1. **Default Package**: `agentic-ide-backend`
   - Complete reproducible build
   - All dependencies pinned
   - No runtime installation needed

2. **Dev Shell**: `agentic-ide-backend-dev`
   - Development environment
   - Poetry, Python 3.11
   - Redis, Docker Compose for testing
   - Debugging tools (ipython, debugpy)

3. **Docker Image**: `packages.docker-image`
   - Lightweight production image
   - Based on poetry environment

4. **Apps**: Quick commands
   - `nix run .#dev` - Start dev server
   - `nix run .#test` - Run tests

### Using with NixOS Home-Manager

```nix
# home.nix or flake.nix
{
  inputs = {
    agentic-ide-backend.url = "path:/path/to/backend";
  };
  
  outputs = { self, agentic-ide-backend, ... }: {
    homeConfigurations.myuser = {
      home.packages = [
        agentic-ide-backend.packages.${system}.agentic-ide-backend-dev
      ];
    };
  };
}
```

### Generating lock file

```bash
cd backend
nix flake update   # Updates flake.lock
nix flake check    # Validates flake
```

---

## Dependencies (Latest Versions)

### Python: 3.11
- Type hints, better performance
- Full async/await support

### FastAPI: ^0.104.1
- High-performance async web framework
- Built-in OpenAPI documentation
- WebSocket support

### LangChain: ^0.1.0 (Latest Architecture)
- Modern component-based design
- Better type hints
- Improved error handling

### LangGraph: ^0.0.25
- State machine orchestration
- Checkpoint support
- Production-ready

### Ollama: ^0.1.20
- Local LLM inference
- Python client library

### Qdrant: ^2.7.0
- Hybrid vector search (semantic + BM25)
- Workspace scoping via filters

### Additional
- Pydantic 2.5 (data validation)
- Structlog (structured logging)
- GitPython (git operations)
- Sentence-transformers (embeddings)

---

## Project Structure

```
backend/
├── flake.nix                # Nix flakes configuration
├── pyproject.toml          # Poetry & tool config
├── poetry.lock             # Locked dependencies
│
├── main.py                 # FastAPI entry point
├── models.py               # Pydantic models
│
├── config/                 # Configuration
│   ├── settings.py
│   └── logging_config.py
│
├── api/                    # HTTP endpoints
│   └── routes/
│       └── workflow_routes.py
│
├── services/               # Business logic
│   ├── workflow_executor.py
│   ├── qdrant_manager.py
│   ├── ollama_manager.py
│   ├── git_manager.py
│   └── retrieval_agent.py
│
├── agents/                 # LLM agents
│   ├── orchestrator.py
│   ├── code_generation.py
│   ├── test_generation.py
│   └── security_analysis.py
│
├── langgraph/              # State machine
│   ├── state.py
│   ├── nodes.py
│   ├── edges.py
│   └── builder.py
│
├── utils/                  # Utilities
│   ├── errors.py
│   ├── validation.py
│   └── ast_utils.py
│
└── tests/                  # Test suite
    ├── unit/
    └── integration/
```

---

## Environment Configuration

### Create .env file

```bash
cp .env.example .env
```

### .env Template

```env
# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=debug

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

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

# Retrieval
RETRIEVAL_TOP_K_FILES=50
RETRIEVAL_TOP_K_FUNCTIONS=20
RETRIEVAL_MAX_TOKENS=3000

# Retry
AGENT_MAX_RETRIES=3
RETRIEVAL_TIMEOUT_SECONDS=10
```

---

## Development Commands

### Using Nix

```bash
# Enter dev shell
nix flake enter
# or just: nix develop

# Run app
nix run .#dev

# Run tests
nix run .#test

# Build Docker image
nix build .#docker-image
```

### Using Poetry Directly

```bash
# Install dependencies
poetry install

# Run dev server (with reload)
poetry run uvicorn backend.main:app --reload --port 8000

# Run tests
poetry run pytest tests/ -v --cov=backend

# Type checking
poetry run mypy backend/

# Code formatting
poetry run black backend/
poetry run ruff check backend/

# Interactive shell
poetry run ipython

# Debug with debugpy
poetry run python -m debugpy --listen 5678 -m uvicorn backend.main:app
```

---

## Local Development Services

### Docker Compose (Optional)

```yaml
# docker-compose.dev.yml
version: "3.8"

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    environment:
      QDRANT_API_KEY: development-key
    volumes:
      - qdrant_data:/qdrant/storage

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: serve

volumes:
  qdrant_data:
  ollama_data:
```

```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### First-Time Setup with Services

```bash
# 1. Start supporting services
docker-compose -f docker-compose.dev.yml up -d

# 2. Wait for services to be ready
sleep 10

# 3. Pull Ollama models (first time only)
docker exec ollama ollama pull mistral:7b-instruct-v0.3
docker exec ollama ollama pull nomic-embed-text

# 4. Enter Nix environment
nix develop

# 5. Install dependencies
poetry install

# 6. Run backend
poetry run uvicorn backend.main:app --reload

# 7. Verify endpoints
curl http://localhost:8000/health
```

---

## Testing

### Run All Tests

```bash
poetry run pytest tests/ -v
```

### Unit Tests Only

```bash
poetry run pytest tests/unit/ -v -m unit
```

### Integration Tests Only

```bash
poetry run pytest tests/integration/ -v -m integration
```

### With Coverage Report

```bash
poetry run pytest tests/ --cov=backend --cov-report=html
# Open htmlcov/index.html in browser
```

### Watch Mode (Continuous Testing)

```bash
poetry run pytest-watch tests/
```

---

## IDE Setup

### VS Code

**.vscode/settings.json**
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

**Recommended Extensions**
- Python
- Pylance
- Black Formatter
- Even Better TOML

### PyCharm

1. File → Settings → Project → Python Interpreter
2. Click ⚙️ → Add → Add Local Interpreter
3. Select `venv/bin/python`
4. Configure code style: Black

---

## Troubleshooting

### Qdrant Connection Failed

```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# If not running:
docker-compose -f docker-compose.dev.yml up -d qdrant
```

### Ollama Connection Failed

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running:
docker-compose -f docker-compose.dev.yml up -d ollama

# Pull required models
docker exec ollama ollama pull mistral:7b-instruct-v0.3
```

### Nix Flake Issues

```bash
# Update flake.lock
nix flake update

# Check flake validity
nix flake check

# Rebuild dev environment
nix flake enter --recreate-lock-file
```

### Import Errors

```bash
# Reinstall in development mode
poetry install --with dev

# Ensure PYTHONPATH is set
export PYTHONPATH="${PWD}:${PYTHONPATH}"
```

---

## Next Steps

1. **Phase 1**: Complete FastAPI shell (main.py working)
2. **Phase 2**: Integrate Qdrant & Ollama managers
3. **Phase 3**: Build LangGraph state machine
4. **Phase 4**: Implement agents (orchestrator, code gen)
5. **Phase 5**: Add retrieval agent
6. **Phase 6**: Streaming & error handling

See **BACKEND_README.md** for detailed component documentation.

