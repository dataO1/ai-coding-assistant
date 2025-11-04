# backend/PROJECT_STRUCTURE.md - Complete Backend Project Structure

## Directory Structure

```
backend/
├── main.py                              # FastAPI app entry point
├── models.py                            # Pydantic data models
│
├── config/
│   ├── __init__.py
│   ├── settings.py                      # Environment configuration (Pydantic)
│   ├── logging_config.py                # Structured logging setup
│   └── constants.py                     # Application constants
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── workflow_routes.py           # Workflow submission & streaming
│   └── middleware/
│       ├── __init__.py
│       └── correlation_id.py            # Correlation ID middleware
│
├── services/
│   ├── __init__.py
│   ├── workflow_executor.py             # LangGraph state machine orchestrator
│   ├── qdrant_manager.py                # Vector DB operations
│   ├── ollama_manager.py                # LLM interface
│   ├── git_manager.py                   # Git operations
│   ├── retrieval_agent.py               # Two-phase retrieval
│   ├── config_manager.py                # Config loading & validation
│   └── cache_manager.py                 # Retrieval caching
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py                  # Orchestrator agent (routing)
│   ├── code_generation.py               # Code gen agent
│   ├── test_generation.py               # Test gen agent
│   ├── security_analysis.py             # Security analysis agent
│   └── base_agent.py                    # Base agent class
│
├── langgraph/
│   ├── __init__.py
│   ├── state.py                         # WorkflowState definition
│   ├── nodes.py                         # State machine nodes
│   ├── edges.py                         # Conditional routing edges
│   └── builder.py                       # LangGraph graph builder
│
├── utils/
│   ├── __init__.py
│   ├── errors.py                        # Custom error classes
│   ├── validation.py                    # Input validation utilities
│   ├── ast_utils.py                     # AST parsing utilities
│   └── path_utils.py                    # Path scoping utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest fixtures
│   │
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_qdrant_manager.py
│   │   ├── test_ollama_manager.py
│   │   └── test_agents.py
│   │
│   ├── integration/
│   │   ├── test_workflow_submit.py
│   │   ├── test_retrieval.py
│   │   ├── test_agent_execution.py
│   │   └── test_end_to_end.py
│   │
│   └── fixtures/
│       ├── sample_project/              # Sample git repo for testing
│       └── mock_configs/                # Mock YAML configs for testing
│
├── __init__.py                          # Package marker
└── py.typed                             # Type hints marker for mypy
```

---

## File Descriptions

### Core Application Files

**main.py**
- FastAPI app entry point
- Lifespan management (startup/shutdown)
- Service initialization (Qdrant, Ollama)
- Health check & debug endpoints
- CORS middleware setup

**models.py**
- Pydantic request/response models
- Data validation
- Enums (WorkflowStatus, ChangeType, etc.)
- WorkflowState dataclass for LangGraph
- DiffContent for lazy-loaded code

### Configuration (backend/config/)

**settings.py**
- Environment-based settings (Pydantic BaseSettings)
- Database URLs, API keys
- Inference parameters
- Retry & timeout config
- Workspace limits

**logging_config.py**
- Structlog setup (JSON output)
- Correlation ID tracking
- Log level management

### API Routes (backend/api/)

**workflow_routes.py**
- POST /api/workflow/submit - Workflow submission
- GET /api/workflow/{execution_id}/status - Status polling
- WebSocket /api/workflow/{execution_id}/stream - Real-time updates
- GET /api/workflow/{execution_id}/commit/{commit_id}/diff - Lazy-load diffs

### Services (backend/services/)

**workflow_executor.py**
- LangGraph orchestration
- Workflow state management
- Node execution coordination
- Error handling & retry logic

**qdrant_manager.py**
- Qdrant connection management
- Collection initialization
- Two-phase retrieval (file-level + function-level)
- Workspace_id filtering for scoping

**ollama_manager.py**
- Ollama HTTP client
- LLM inference (streaming & non-streaming)
- Model management
- VRAM monitoring

**git_manager.py**
- Git operations
- Branch creation/merging
- Commit operations
- Workspace scoping (working_dir enforcement)

**retrieval_agent.py**
- Phase 1: File-level semantic search
- Phase 2: Function-level AST extraction
- Hybrid search (BM25 + semantic)
- Caching layer integration

**config_manager.py**
- Load workspace config (.agentic-ide/config.yaml)
- Validate agent configs
- Handle missing configs with defaults

### Agents (backend/agents/)

**orchestrator.py**
- Route incoming queries to workflows
- LLM-based routing decision
- Reasoning & confidence scoring

**code_generation.py**
- Generate Python/JS/TS code
- Syntax validation
- Error detection
- SUMMARY extraction

**test_generation.py**
- Generate test cases
- Use test examples from retrieval
- SUMMARY extraction

**security_analysis.py**
- Security vulnerability analysis
- CVE detection
- Dependency scanning
- SUMMARY extraction

**base_agent.py**
- Abstract base for all agents
- Common interface (execute, validate_output)
- Error handling template

### LangGraph (backend/langgraph/)

**state.py**
- WorkflowState definition
- State transitions
- Serialization/deserialization

**nodes.py**
- orchestrator_node: Route workflow
- retrieval_node: Execute two-phase retrieval
- execution_node: Run specialized agent
- adaptive_retrieval_node: Enhanced retrieval on failure
- git_commit_node: Create commits
- aggregation_node: Finalize results

**edges.py**
- Conditional routing (failure detection, retry logic)
- Next-stage routing
- Error handling branches

**builder.py**
- LangGraph graph construction
- Node registration
- Edge configuration
- Compiled graph export

### Utilities (backend/utils/)

**errors.py**
- Custom exception classes
- RetrievalError, AgentError, GitError
- Error context & debugging info

**validation.py**
- Pydantic schema validation
- Request validation helpers
- Config schema validation

**ast_utils.py**
- AST parsing (Python, JS, TS)
- Function extraction
- Signature analysis
- Import resolution

**path_utils.py**
- Workspace scoping validation
- Path sanitization
- working_dir enforcement

### Tests (backend/tests/)

**conftest.py**
- Pytest fixtures
- Mock Qdrant, Ollama, Git
- Test database setup

**unit/**
- Individual component tests
- Isolated from dependencies (mocked)

**integration/**
- Multi-component workflows
- Real service interactions (test containers)
- End-to-end scenarios

---

## Implementation Priority

### Phase 1 (FastAPI Shell)
1. main.py - Basic app structure
2. config/settings.py - Environment config
3. models.py - Data models
4. api/routes/workflow_routes.py - Stub endpoints

### Phase 2 (Connections)
1. services/qdrant_manager.py
2. services/ollama_manager.py
3. services/git_manager.py

### Phase 3 (Orchestration)
1. langgraph/state.py
2. langgraph/nodes.py
3. langgraph/builder.py
4. services/workflow_executor.py

### Phase 4 (Agents)
1. agents/base_agent.py
2. agents/orchestrator.py
3. agents/code_generation.py
4. agents/test_generation.py

### Phase 5 (Retrieval)
1. services/retrieval_agent.py
2. services/config_manager.py
3. services/cache_manager.py

### Phase 6 (Advanced)
1. utils/ - Helper utilities
2. Middleware - Correlation IDs, error handling
3. Tests - Comprehensive test suite

---

## Key Design Decisions

### Async-First Architecture
- FastAPI with async/await throughout
- Ollama HTTP client is async
- Qdrant operations are async
- Better resource utilization

### LangGraph for Orchestration
- Deterministic state machine
- Checkpoint support for recovery
- Clear visualization
- LangChain 1.x compatible

### Workspace Scoping
- Every query includes workspace_id
- Qdrant filters on workspace_id
- Git operations scoped to working_dir
- Prevents cross-project leakage

### Metadata-Only Streaming
- Status updates only (no code)
- Commits metadata sent on completion
- Code lazy-loaded via separate API call
- Reduces bandwidth & latency

### Configuration-Driven
- Workflow config from GUI
- No backend config files needed
- Agents.yaml defines agents
- Retrieval.yaml defines strategies

### Structured Logging
- JSON output for production
- Correlation IDs for tracing
- Structured fields for analysis
- Debug-friendly in development

---

## Running the Backend

```bash
# With Nix (declarative)
nix flake run

# With Poetry
poetry install
poetry run uvicorn backend.main:app --reload

# Tests
poetry run pytest tests/ -v

# Type checking
poetry run mypy backend/

# Code formatting
poetry run black backend/
poetry run ruff check backend/
```

