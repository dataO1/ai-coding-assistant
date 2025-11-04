# BACKEND_COMPLETE_GUIDE.md - Full Backend Implementation Guide

**Complete Backend Skeleton - Ready to Build**

---

## 📦 Deliverables Summary

### Generated Files (15 Core + Documentation)

**Build & Config:**
- ✅ `flake.nix` - Nix flakes (reproducible builds)
- ✅ `pyproject.toml` - Poetry + dependencies
- ✅ `.env.example` - Environment template

**Application:**
- ✅ `backend/main.py` - FastAPI app + lifespan
- ✅ `backend/models.py` - Pydantic models
- ✅ `backend/__init__.py` - Package init
- ✅ `backend/config/settings.py` - Configuration
- ✅ `backend/config/logging_config.py` - Logging
- ✅ `backend/api/routes/workflow_routes.py` - Endpoints
- ✅ `backend/services/__init__.py` - Services package
- ✅ `backend/services/qdrant_manager.py` - Vector DB
- ✅ `backend/services/ollama_manager.py` - LLM

**Documentation:**
- ✅ `BACKEND_SKELETON_SUMMARY.md` - This guide
- ✅ `BACKEND_SETUP_GUIDE.md` - Setup instructions
- ✅ `backend/PROJECT_STRUCTURE.md` - File descriptions

**Supporting Documentation (Already Provided):**
- ✅ `BACKEND_README.md` - Complete architecture
- ✅ `FLOW_DIAGRAMS_DETAILED.md` - Request/response flows
- ✅ `REFINED_SPECIFICATION_v2.0.md` - Full specification

---

## 🚀 Getting Started (5 Minutes)

### Step 1: Verify Prerequisites

```bash
# Check Nix
nix --version

# Check Python
python --version  # Should be 3.11+

# Check Git
git --version
```

### Step 2: Enter Dev Environment

```bash
cd backend

# Option A: With Nix (Recommended)
nix flake enter
poetry install

# Option B: Without Nix
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
poetry install
```

### Step 3: Start Services (In Separate Terminal)

```bash
# Start Qdrant + Ollama
docker-compose -f docker-compose.dev.yml up -d

# Wait for services
sleep 5

# Pull models (first time only)
docker exec ollama ollama pull mistral:7b-instruct-v0.3
docker exec ollama ollama pull nomic-embed-text

# Verify
curl http://localhost:6333/health
curl http://localhost:11434/api/tags
```

### Step 4: Run Backend

```bash
# In original terminal
poetry run uvicorn backend.main:app --reload

# Output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

### Step 5: Test

```bash
# In another terminal
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0","environment":"development"}
```

✅ **Backend is running!**

---

## 📂 Project Layout

```
backend/
├── flake.nix                    # Nix configuration
├── pyproject.toml               # Dependencies
│
├── main.py                      # App entry
├── models.py                    # Data models
├── __init__.py
│
├── config/
│   ├── settings.py              # Configuration
│   ├── logging_config.py        # Logging
│   └── __init__.py
│
├── api/
│   ├── routes/
│   │   ├── workflow_routes.py   # Endpoints
│   │   └── __init__.py
│   └── __init__.py
│
├── services/
│   ├── qdrant_manager.py        # Vector DB
│   ├── ollama_manager.py        # LLM
│   ├── __init__.py
│   └── (to be implemented)
│
└── (agents/, langgraph/, utils/ - ready for Phase 2+)
```

---

## 🔧 Key Files Explained

### main.py - Application Entry Point

```python
# What it does:
# 1. Sets up FastAPI app with lifespan management
# 2. Initializes Qdrant and Ollama on startup
# 3. Cleans up connections on shutdown
# 4. Registers API routes
# 5. Provides health check endpoint

# When to modify:
# - Add new routes
# - Change middleware
# - Modify startup/shutdown behavior
```

### models.py - Data Models

```python
# Contains:
# - WorkflowSubmitRequest (from GUI)
# - WorkflowSubmitResponse (to GUI)
# - StatusUpdate, WorkflowCompleteUpdate (streaming)
# - CommitMetadata, FileChange (diff data)
# - WorkflowState (LangGraph state machine)

# When to modify:
# - Change request/response format
# - Add new streaming message types
# - Extend state machine data
```

### config/settings.py - Configuration

```python
# Loads from environment variables
# Examples:
# - BACKEND_PORT=8000
# - QDRANT_URL=http://localhost:6333
# - OLLAMA_BASE_URL=http://localhost:11434
# - LOG_LEVEL=debug

# When to modify:
# - Add new configuration options
# - Change defaults
# - Add validation rules
```

### api/routes/workflow_routes.py - Endpoints

```python
# Implements:
# POST /api/workflow/submit - Submit workflow request
# GET /api/workflow/{execution_id}/status - Get status
# WebSocket /api/workflow/{execution_id}/stream - Real-time updates
# GET /api/workflow/{execution_id}/commit/{commit_id}/diff - Load diff

# When to modify:
# - Implement workflow submission logic
# - Add request validation
# - Implement streaming updates
# - Add error handling
```

### services/qdrant_manager.py - Vector Database

```python
# Implements:
# - Connect/disconnect from Qdrant
# - Initialize collections
# - Search with workspace filtering
# - Upsert points

# When to modify:
# - Implement collection initialization
# - Add two-phase retrieval logic
# - Add workspace filtering
# - Implement caching
```

### services/ollama_manager.py - LLM Interface

```python
# Implements:
# - Verify connection
# - Generate text (streaming & non-streaming)
# - Get VRAM info

# When to modify:
# - Implement inference logic
# - Add prompt templates
# - Handle errors & timeouts
# - Implement token counting
```

---

## 🎯 Implementation Phases

### Phase 1: Core Setup ✅ DONE

- [x] FastAPI application shell
- [x] Qdrant manager skeleton
- [x] Ollama manager skeleton
- [x] Data models
- [x] Configuration management
- [x] API route stubs
- [x] Structured logging
- [x] Nix flakes + Poetry

**Estimated Time**: 2 days  
**Status**: ✅ Complete - Ready to code Phase 2

---

### Phase 2: Service Integration (Next)

**Tasks:**
- [ ] Implement QdrantManager.connect() & disconnect()
- [ ] Implement QdrantManager.search() & upsert_points()
- [ ] Implement OllamaManager.generate() (streaming & non-streaming)
- [ ] Implement OllamaManager.get_vram_info()
- [ ] Implement GitManager (branch, commit, merge)
- [ ] Add integration tests

**Estimated Time**: 3-4 days  
**Files to Create**:
- `backend/services/git_manager.py`
- `tests/integration/test_services.py`

---

### Phase 3: LangGraph Orchestration

**Tasks:**
- [ ] Define WorkflowState
- [ ] Create orchestrator node
- [ ] Create retrieval node (stub)
- [ ] Create execution node (stub)
- [ ] Create git commit node
- [ ] Implement conditional edges
- [ ] Build graph

**Estimated Time**: 5-6 days  
**Files to Create**:
- `backend/langgraph/state.py`
- `backend/langgraph/nodes.py`
- `backend/langgraph/edges.py`
- `backend/langgraph/builder.py`
- `backend/services/workflow_executor.py`

---

### Phases 4-8: Agents, Retrieval, Polish

**See**: BACKEND_README.md (Section 13: Implementation Roadmap)

---

## 📖 Documentation Reference

### For Different Roles

**Frontend Developer**: Skip to FRONTEND_README.md

**Backend Developer**: Read in order:
1. This file (orientation)
2. `backend/PROJECT_STRUCTURE.md` (file layout)
3. `BACKEND_README.md` (component design)
4. `FLOW_DIAGRAMS_DETAILED.md` (state machine flow)
5. `REFINED_SPECIFICATION_v2.0.md` (full spec)

**Tech Lead**: Read:
1. This file (overview)
2. `REFINED_SPECIFICATION_v2.0.md` (architecture)
3. `FLOW_DIAGRAMS_DETAILED.md` (request flows)
4. `DOCUMENTATION_MANIFEST.md` (team guide)

---

## 🧪 Testing

### Run Tests

```bash
# All tests
poetry run pytest tests/ -v

# Unit tests only
poetry run pytest tests/unit/ -v -m unit

# Integration tests
poetry run pytest tests/integration/ -v -m integration

# With coverage
poetry run pytest tests/ --cov=backend --cov-report=html
```

### Add Tests (Phase 2)

```bash
# Test Qdrant manager
tests/unit/test_qdrant_manager.py

# Test Ollama manager
tests/unit/test_ollama_manager.py

# Integration tests
tests/integration/test_services_integration.py
```

---

## 🐛 Debugging

### Enable Debug Logging

```bash
# Set in .env or as env var
LOG_LEVEL=debug
DEBUG=true

poetry run uvicorn backend.main:app --reload
```

### Use IPython REPL

```bash
poetry run ipython

# In IPython:
from backend.services.qdrant_manager import QdrantManager
from backend.config.settings import settings

qm = QdrantManager(settings.QDRANT_URL)
# ... test code
```

### Debug with PyCharm

1. Set breakpoint in code
2. Click Run → Debug 'main'
3. Use debug console

### Profile with py-spy

```bash
poetry run py-spy record -o profile.svg --function python -m uvicorn backend.main:app
```

---

## 💡 Common Tasks

### Add New Environment Variable

1. Add to `backend/config/settings.py`:
```python
NEW_VAR: str = "default_value"
```

2. Add to `.env`:
```
NEW_VAR=my_value
```

3. Use in code:
```python
from backend.config.settings import settings
print(settings.NEW_VAR)
```

### Add New Endpoint

1. Add to `backend/api/routes/workflow_routes.py`:
```python
@router.get("/new-endpoint")
async def new_endpoint():
    return {"message": "Hello"}
```

2. Test:
```bash
curl http://localhost:8000/api/new-endpoint
```

### Add New Service

1. Create `backend/services/new_service.py`
2. Implement class with methods
3. Import in `backend/services/__init__.py`
4. Initialize in `main.py` lifespan (if needed)

### Format Code

```bash
# Format with Black
poetry run black backend/

# Sort imports
poetry run isort backend/

# Lint with ruff
poetry run ruff check backend/

# Type check
poetry run mypy backend/
```

---

## 🔍 Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
poetry run uvicorn backend.main:app --port 8001
```

### Qdrant Connection Failed

```bash
# Check if running
docker ps | grep qdrant

# Restart
docker-compose -f docker-compose.dev.yml restart qdrant

# Verify
curl http://localhost:6333/health
```

### Ollama Not Responding

```bash
# Check if running
docker ps | grep ollama

# Check logs
docker logs ollama

# Restart
docker-compose -f docker-compose.dev.yml restart ollama

# Pull model
docker exec ollama ollama pull mistral:7b-instruct-v0.3
```

### Import Errors

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Reinstall with poetry
poetry install

# Try running again
poetry run uvicorn backend.main:app --reload
```

### Nix Issues

```bash
# Update flake.lock
nix flake update

# Check flake validity
nix flake check

# Rebuild dev environment
rm -rf .venv
nix flake enter --recreate-lock-file
poetry install
```

---

## 📞 Getting Help

**Documentation**:
- Full Architecture: `BACKEND_README.md`
- Setup Issues: `BACKEND_SETUP_GUIDE.md`
- Component Details: `backend/PROJECT_STRUCTURE.md`
- Flows: `FLOW_DIAGRAMS_DETAILED.md`
- Spec: `REFINED_SPECIFICATION_v2.0.md`

**Code Examples**:
- Look at `main.py` for FastAPI patterns
- Look at `services/qdrant_manager.py` for async patterns
- Look at `models.py` for Pydantic patterns

**External Resources**:
- FastAPI: https://fastapi.tiangolo.com
- LangChain: https://python.langchain.com
- LangGraph: https://github.com/langchain-ai/langgraph
- Pydantic: https://docs.pydantic.dev

---

## ✅ Checklist: Next Steps

- [ ] Run backend locally (follow Quick Start above)
- [ ] Verify all endpoints responding
- [ ] Read `BACKEND_README.md` sections 1-3
- [ ] Review `FLOW_DIAGRAMS_DETAILED.md` Flow 1
- [ ] Plan Phase 2 implementation (services integration)
- [ ] Set up IDE with proper Python interpreter
- [ ] Create first test in `tests/unit/`
- [ ] Run tests and verify coverage

---

**YOU ARE READY TO BUILD!**

The backend skeleton is complete, fully documented, and ready for Phase 2 implementation. Start with the QdrantManager and OllamaManager implementation.

Good luck! 🚀

