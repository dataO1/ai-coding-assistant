# BACKEND/SERVER - COMPREHENSIVE ARCHITECTURE & IMPLEMENTATION GUIDE

**Status**: Complete Architectural Specification  
**Last Updated**: November 4, 2025  
**Version**: 2.0  
**Audience**: Backend developers, no prior project knowledge assumed

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architectural Overview](#architectural-overview)
3. [Component Design](#component-design)
4. [Data Flow & State Machine](#data-flow--state-machine)
5. [API Specification](#api-specification)
6. [Database Schema](#database-schema)
7. [Configuration Management](#configuration-management)
8. [Deployment & Execution](#deployment--execution)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Development Guidelines](#development-guidelines)

---

## EXECUTIVE SUMMARY

### What This System Does

The Backend is a **LLM-orchestrated multi-agent pipeline** that receives user queries and workspace context from the GUI, then:

1. **Routes** the query to appropriate workflow (via Orchestrator)
2. **Retrieves** relevant code from the workspace (via Retrieval Agent)
3. **Executes** specialized agents (Code Gen, Test Gen, Security Analysis)
4. **Manages** git operations and commits
5. **Streams** real-time status updates to GUI via ACP protocol

**Key Point**: Backend is STATELESS for workflow execution. All config comes from GUI request. Backend only manages Qdrant/Ollama/Git connections.

### Technology Stack

| Component | Technology | Reasoning |
|-----------|-----------|-----------|
| Framework | FastAPI/Python | LLM integration, async, type-safe |
| Agent Orchestration | LangGraph | Deterministic state machine, checkpointing |
| LLM Interface | Ollama (local) | Self-hosted, no API keys, full control |
| Vector Database | Qdrant | Hybrid search, workspace scoping, fast |
| Configuration | YAML (from GUI) | Flexible, versionable, user-customizable |
| Communication | HTTP/WebSocket (ACP) | Real-time streaming, stateless |
| Git | GitPython | Commit management, branch handling |
| Logging | Structured JSON | Correlation IDs, debugging, production monitoring |

---

## ARCHITECTURAL OVERVIEW

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: API GATEWAY (FastAPI)                                  │
│ - HTTP endpoints (/api/workflow/submit, /api/*/status)          │
│ - Request validation                                             │
│ - Response formatting                                            │
│ - Error handling                                                 │
│ - ACP callback streaming                                         │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: ORCHESTRATION (LangGraph State Machine)                │
│ - Workflow execution coordination                                │
│ - State transitions                                              │
│ - Conditional routing (success/failure/adaptive retrieval)       │
│ - Checkpoint management                                          │
│ - Error recovery                                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: AGENTS & SERVICES                                       │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│ │ Orchestrator │ │ Retrieval    │ │ Specialists  │             │
│ │ Agent (LLM)  │ │ Agent        │ │ (Code/Test)  │             │
│ └──────────────┘ └──────────────┘ └──────────────┘             │
│                                                                 │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│ │ Git Manager  │ │ MCP Tools    │ │ Config Mgmt  │             │
│ └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Request Lifecycle

```
1. GUI submits: POST /api/workflow/submit
   Payload: {workflow_config, agents_config, retrieval_config, workspace_context}
            │
            ▼
2. API Gateway validates request
   ├─ Schema validation
   ├─ Workspace scoping (workspace_id exists?)
   └─ Config version check
            │
            ▼
3. Create Workflow Execution
   ├─ Generate execution_id
   ├─ Initialize LangGraph state
   └─ Set correlation_id for logging
            │
            ▼
4. Start Orchestration State Machine
   ├─ Step 1: Orchestrator Agent (route workflow)
   ├─ Step 2-N: Per stage (Retrieval → Agent → Git)
   └─ Final: Aggregation
            │
            ▼
5. Stream Updates via ACP
   ├─ Status updates (every stage)
   ├─ Commit notifications
   └─ Final completion with metadata
            │
            ▼
6. Return Success/Error to GUI
```

---

## COMPONENT DESIGN

### Component 1: API Gateway (FastAPI Server)

**Responsibility**: HTTP request handling, validation, response formatting

**Key Endpoints**:

```python
# config/app_routes.py

# 1. Workflow Submission
POST /api/workflow/submit
├─ Input: WorkflowSubmitRequest (see below)
├─ Processing: Validate → Initialize → Return execution_id
└─ Output: {execution_id, status: "accepted"}

# 2. Workflow Status
GET /api/workflow/{execution_id}/status
├─ Returns: Current state (queued/running/complete)
└─ Output: {status, current_stage, progress}

# 3. Stream Updates (SSE or WebSocket)
GET /api/workflow/{execution_id}/stream
├─ Transport: Server-Sent Events or WebSocket
└─ Output: Continuous stream of {type, data} objects

# 4. Commit Diff (Lazy Load)
GET /api/workflow/{execution_id}/commit/{commit_id}/diff
├─ Returns: Unified diff for specific commit
└─ Output: {diff_content, stats}

# 5. Debug Endpoints
GET /debug/metrics → Agent execution metrics
GET /debug/vram → GPU VRAM usage
GET /debug/checkpoints → LangGraph checkpoint inspection
```

**Request/Response Models**:

```python
class WorkflowSubmitRequest(BaseModel):
    workflow_id: str = "workflow_feature_001"
    workflow_type: str = "feature_implementation"
    user_query: str = "Implement JWT authentication"
    
    # GUI sends complete configs
    workflow_config: Dict  # From workflows.yaml
    agents_config: Dict    # From agents.yaml
    retrieval_config: Dict # From retrieval.yaml
    mcp_config: Dict       # From mcp_integration.yaml
    
    # Workspace context
    workspace_context: WorkspaceContext
    
    correlation_id: str = "req_xyz_12345"

class WorkspaceContext(BaseModel):
    workspace_id: str = "ws_jwt_feature_001"
    working_dir: str = "/home/user/my-project"
    language: str = "python"
    framework: str = "fastapi"

class WorkflowStatusResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str  # "queued" | "running" | "complete" | "failed"
    current_stage: Optional[str]
    progress_percent: int
    commits_completed: int
    total_stages: int
```

**Error Handling**:

```python
# API error responses
{
    "error": "configuration_error",
    "message": "Invalid workflow config: missing 'stages' field",
    "correlation_id": "req_xyz",
    "details": {...}
}
```

---

### Component 2: LangGraph State Machine (Orchestration)

**Responsibility**: Workflow execution coordination, state transitions, failure handling

**State Definition**:

```python
# backend/state_machine.py

@dataclass
class WorkflowState:
    # Input
    user_query: str
    workflow_id: str
    workflow_config: Dict
    agents_config: Dict
    retrieval_config: Dict
    workspace_context: WorkspaceContext
    
    # Execution tracking
    execution_id: str
    correlation_id: str
    current_stage: str
    stage_results: Dict  # {stage_id: agent_result}
    
    # Retrieval & context
    retrieved_context: Optional[str] = None
    retrieval_needs: List[str] = []
    enrichment_context: Dict = {}  # For adaptive retrieval
    
    # Git operations
    workflow_branch: str
    commits: List[Dict] = []
    
    # Error tracking
    failures: Dict = {}  # {stage_id: failure_info}
    attempt_count: Dict = {}  # {stage_id: attempts}
    
    # Output
    is_success: bool = False
    final_message: str = ""

# State machine nodes
def orchestrator_node(state: WorkflowState) -> WorkflowState:
    """Route to appropriate workflow"""
    # Use LLM to select workflow type
    # Set state.current_stage = selected_workflow
    return state

def retrieval_node(state: WorkflowState) -> WorkflowState:
    """Retrieve relevant context for current stage"""
    # Get agent's retrieval_needs
    # Execute two-phase retrieval (file-level + AST)
    # Check cache, populate context
    state.retrieved_context = context
    return state

def execution_node(state: WorkflowState) -> WorkflowState:
    """Execute specialized agent"""
    # Load agent config from state.agents_config
    # Execute with retrieved_context
    # Check failure_detector
    state.stage_results[state.current_stage] = result
    return state

def git_commit_node(state: WorkflowState) -> WorkflowState:
    """Commit changes to git"""
    # Extract SUMMARY from agent output
    # Write files to workspace
    # Create commit
    state.commits.append(commit_info)
    return state

# Conditional edges (routing logic)
def should_retry_on_failure(state: WorkflowState) -> str:
    """Decide: retry with adaptive retrieval or proceed?"""
    current_result = state.stage_results.get(state.current_stage, {})
    is_failed = current_result.get("is_failed", False)
    attempt = state.attempt_count.get(state.current_stage, 0)
    
    if is_failed and attempt < 3:
        state.enrichment_context = {
            "failure_reason": current_result.get("failure_info"),
            "previous_context": state.retrieved_context
        }
        return "adaptive_retrieval"  # Route to enhanced retrieval
    elif is_failed:
        return "error"  # Max retries exceeded
    else:
        return "next_stage"  # Success, proceed

def next_stage_router(state: WorkflowState) -> str:
    """Route to next enabled stage or aggregation"""
    current_index = find_stage_index(state)
    if current_index < len(stages) - 1:
        state.current_stage = stages[current_index + 1]
        return "retrieval"
    else:
        return "aggregation"
```

**LangGraph Builder**:

```python
# backend/langgraph_builder.py

from langgraph.graph import StateGraph, END

def build_workflow_graph(state_schema):
    graph = StateGraph(state_schema)
    
    # Add nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("execution", execution_node)
    graph.add_node("git_commit", git_commit_node)
    graph.add_node("adaptive_retrieval", adaptive_retrieval_node)
    graph.add_node("aggregation", aggregation_node)
    graph.add_node("error", error_node)
    
    # Add edges
    graph.add_edge("START", "orchestrator")
    graph.add_edge("orchestrator", "retrieval")
    
    # Conditional edges (success/failure/retry)
    graph.add_conditional_edges(
        "execution",
        should_retry_on_failure,
        {
            "adaptive_retrieval": "adaptive_retrieval",
            "next_stage": "git_commit",
            "error": "error"
        }
    )
    
    graph.add_edge("git_commit", next_stage_router)
    graph.add_edge("adaptive_retrieval", "execution")
    graph.add_edge("error", END)
    graph.add_edge("aggregation", END)
    
    return graph.compile()

# Compiled graph ready for execution
workflow_graph = build_workflow_graph(WorkflowState)
```

---

### Component 3: Orchestrator Agent

**Responsibility**: Route incoming query to correct workflow

**Implementation**:

```python
# backend/agents/orchestrator.py

class OrchestratorAgent:
    def __init__(self, model_config):
        self.model = Ollama(
            model=model_config["name"],
            temperature=0.3,  # Lower temp for consistent routing
            max_tokens=500
        )
    
    def route_workflow(self, user_query: str, workflows: Dict) -> str:
        """Select appropriate workflow for query"""
        
        prompt = f"""
        User Query: {user_query}
        
        Available Workflows:
        - feature_implementation: For new features/functionality
        - bug_fix: For fixing bugs with tests
        - refactoring: For improving code structure
        - security_review: For analyzing security
        
        Reasoning:
        1. Understand the user's intent
        2. Select most appropriate workflow
        3. Explain reasoning
        
        Output JSON:
        {{
            "selected_workflow": "feature_implementation",
            "reasoning": "User wants new feature, needs tests",
            "confidence": 0.95
        }}
        """
        
        response = self.model.invoke(prompt)
        result = json.loads(response)
        
        return result["selected_workflow"]
```

---

### Component 4: Retrieval Agent

**Responsibility**: Execute two-phase retrieval with workspace/stage scoping

**Implementation**:

```python
# backend/agents/retrieval.py

class RetrievalAgent:
    def __init__(self, qdrant_client, embedding_model, reranker):
        self.qdrant = qdrant_client
        self.embedding = embedding_model
        self.reranker = reranker
        self.cache = {}  # Simple in-memory cache
    
    def retrieve(
        self,
        query: str,
        workspace_id: str,
        stage_type: str,
        retrieval_needs: List[str],
        retrieval_config: Dict
    ) -> str:
        """Execute workspace-scoped two-phase retrieval"""
        
        # 1. Check cache
        cache_key = self._cache_key(query, workspace_id, stage_type)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 2. Phase 1: File-level retrieval
        file_filter = self._build_filter(workspace_id, retrieval_needs)
        files_context = self._phase_1_file_retrieval(
            query=query,
            filter=file_filter,
            top_k=50
        )
        
        # 3. Phase 2: Function-level AST
        functions_context = self._phase_2_function_retrieval(
            files=files_context,
            query=query,
            stage_type=stage_type,
            top_k=20
        )
        
        # 4. Aggregate context
        final_context = self._aggregate_context(
            files_context,
            functions_context,
            max_tokens=3000
        )
        
        # 5. Cache and return
        self.cache[cache_key] = final_context
        return final_context
    
    def _build_filter(self, workspace_id: str, needs: List[str]):
        """Build Qdrant filter for workspace + stage-specific needs"""
        
        # Mandatory: workspace_id
        must_filters = [{
            "key": "workspace_id",
            "match": {"value": workspace_id}
        }]
        
        # Optional: based on retrieval_needs
        if "test_examples_only" in needs:
            must_filters.append({
                "key": "file_name",
                "match": {"value": "*_test.py"}
            })
        
        return {"must": must_filters}
    
    def _phase_1_file_retrieval(self, query: str, filter: Dict, top_k: int):
        """Semantic file-level search"""
        query_embedding = self.embedding.embed_query(query)
        
        results = self.qdrant.search(
            collection_name="workspace_files",
            query_vector=query_embedding,
            query_filter=filter,
            limit=top_k
        )
        
        return results
    
    def _phase_2_function_retrieval(self, files, query, stage_type, top_k):
        """AST extraction and function-level reranking"""
        
        functions = []
        for file_result in files:
            # Parse AST of file
            ast_functions = parse_ast(file_result.payload["file_path"])
            functions.extend(ast_functions)
        
        # Rerank with cross-encoder
        reranked = self.reranker.rank(
            query=query,
            passages=[f["signature"] for f in functions],
            top_k=top_k
        )
        
        return [functions[idx] for idx in reranked]
    
    def _cache_key(self, query: str, workspace_id: str, stage_type: str) -> str:
        content = f"{query}:{workspace_id}:{stage_type}"
        return hashlib.md5(content.encode()).hexdigest()
```

---

### Component 5: Specialized Execution Agents

**Responsibility**: Generate code, tests, or security analysis

**Implementation**:

```python
# backend/agents/code_generation.py

class CodeGenerationAgent:
    def __init__(self, model_config):
        self.model = Ollama(
            model=model_config["name"],
            temperature=0.7,
            max_tokens=2000
        )
    
    def execute(
        self,
        user_query: str,
        retrieved_context: str,
        workspace_context: WorkspaceContext
    ) -> Dict:
        """Generate code with failure detection"""
        
        prompt = f"""
        Task: {user_query}
        
        Existing Code Context:
        {retrieved_context}
        
        Requirements:
        1. Generate Python code
        2. Use same style as existing code
        3. Include error handling
        4. At end, provide: SUMMARY: [one-line description]
        
        Generated Code:
        """
        
        try:
            response = self.model.invoke(prompt)
            
            # Extract code and SUMMARY
            code = extract_code_block(response)
            summary = extract_summary(response)
            
            # Failure detection
            is_failed = not self._validate_syntax(code)
            
            return {
                "generated_code": code,
                "summary": summary,
                "explanation": response,
                "is_failed": is_failed,
                "failure_info": "Syntax error" if is_failed else None
            }
        
        except Exception as e:
            return {
                "is_failed": True,
                "failure_info": str(e)
            }
    
    def _validate_syntax(self, code: str) -> bool:
        """Check if generated code has valid syntax"""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
```

---

### Component 6: Git Manager

**Responsibility**: Branch creation, file writing, committing

**Implementation**:

```python
# backend/services/git_manager.py

class GitManager:
    def __init__(self, repo_path: str):
        self.repo = git.Repo(repo_path)
    
    def create_workflow_branch(self, workflow_id: str) -> str:
        """Create feature branch for workflow"""
        
        branch_name = f"agentic/workflow_{workflow_id}_{int(time.time())}"
        
        # Create and checkout branch
        self.repo.create_head(branch_name)
        self.repo.heads[branch_name].checkout()
        
        return branch_name
    
    def commit_changes(
        self,
        files: Dict[str, str],  # {file_path: content}
        summary: str,
        agent_name: str
    ) -> str:
        """Write files and create commit with semantic message"""
        
        # 1. Write files to disk
        for file_path, content in files.items():
            full_path = os.path.join(self.repo.working_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
        
        # 2. Stage files
        self.repo.index.add(list(files.keys()))
        
        # 3. Create commit message
        prefix = self._get_prefix(agent_name)  # "feat:", "test:", "docs:"
        commit_message = f"{prefix} {summary}"
        
        # 4. Commit
        commit = self.repo.index.commit(commit_message)
        
        return commit.hexsha
    
    def _get_prefix(self, agent_name: str) -> str:
        prefixes = {
            "code_generation": "feat:",
            "test_generation": "test:",
            "security_analysis": "docs:",
            "refactoring": "refactor:"
        }
        return prefixes.get(agent_name, "chore:")
    
    def merge_workflow_branch(self, branch_name: str, strategy: str = "merge"):
        """Merge workflow branch to main"""
        
        if strategy == "merge":
            # Merge keeping all commits
            self.repo.heads.main.checkout()
            self.repo.remotes.origin.pull()
            self.repo.heads.main.merge_base(branch_name)
        
        elif strategy == "squash":
            # Combine all commits into one
            self.repo.heads.main.checkout()
            base = self.repo.merge_base(
                self.repo.heads.main,
                self.repo.heads[branch_name]
            )
            self.repo.index.merge_tree(base, self.repo.heads[branch_name])
        
        # Delete branch
        git.GitCommandError.allow_unsafe = True
        self.repo.delete_head(branch_name, force=True)
```

---

### Component 7: Configuration Management

**Responsibility**: Validate and manage workflow configs from GUI

**Implementation**:

```python
# backend/services/config_manager.py

class ConfigManager:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.workspace_config = self._load_workspace_config()
    
    def _load_workspace_config(self) -> Dict:
        """Load .agentic-ide/config.yaml from workspace root"""
        
        config_path = os.path.join(
            self.workspace_path,
            ".agentic-ide",
            "config.yaml"
        )
        
        if not os.path.exists(config_path):
            return self._default_config()
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate schema
        self._validate_schema(config)
        return config
    
    def _default_config(self) -> Dict:
        """Fallback to defaults if config missing"""
        return {
            "version": "1.0",
            "workspace": {"name": "default"},
            "retrieval": {
                "enabled": True,
                "strategy": "TART_code_generation",
                "agents": {
                    "code_generation": {"enabled": True},
                    "test_generation": {"enabled": True},
                    "security_analysis": {"enabled": True}
                }
            }
        }
    
    def validate_agent_config(self, config: Dict) -> bool:
        """Validate agent config from GUI request"""
        required_fields = ["model", "role", "retrieval_needs"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        return True
```

---

## DATA FLOW & STATE MACHINE

### Complete Request to Response Flow

```
1. GUI submits POST /api/workflow/submit
   └─ Payload: {workflow_config, agents_config, retrieval_config, workspace_context}

2. API validates request
   └─ Schema check, version check, workspace_id exists?

3. LangGraph initializes WorkflowState
   ├─ execution_id: auto-generated
   ├─ correlation_id: from request
   └─ Load all config from request payload

4. LangGraph executes "orchestrator" node
   ├─ Orchestrator LLM routes to workflow
   ├─ Set current_stage = first_stage
   └─ Emit: status_update("Routing workflow...")

5. LangGraph executes "retrieval" node
   ├─ Load agent's retrieval_needs
   ├─ Load workspace retrieval config (.agentic-ide/config.yaml)
   ├─ Execute two-phase retrieval (file-level + AST)
   ├─ Check cache, populate state.retrieved_context
   └─ Emit: status_update("Retrieving context...")

6. LangGraph executes "execution" node
   ├─ Load specialist agent (Code Gen, Test Gen, etc)
   ├─ Execute with user_query + retrieved_context
   ├─ Agent generates output with SUMMARY line
   ├─ Failure detector checks output
   └─ Emit: status_update("Generating code...")

7. Conditional edge: Check failure
   ├─ If failed & attempts < 3:
   │  └─ Route to "adaptive_retrieval" (enhanced context from failure)
   ├─ If failed & attempts >= 3:
   │  └─ Route to "error" (return error to user)
   └─ If success:
      └─ Route to "git_commit"

8. LangGraph executes "git_commit" node
   ├─ Extract SUMMARY from agent output
   ├─ Write generated files to working_dir
   ├─ Create commit with semantic message
   ├─ Get commit_id
   └─ Add to state.commits[]

9. Route to next stage OR aggregation
   ├─ If more stages:
   │  └─ current_stage = next_stage, loop to step 5
   └─ If all stages done:
      └─ Route to "aggregation"

10. LangGraph executes "aggregation" node
    ├─ Collect all commits from state.commits[]
    ├─ Generate metadata (files changed, +/- lines)
    ├─ Emit: workflow_complete(commits=[...])
    └─ End

11. GUI receives workflow_complete callback
    ├─ Display diff view (metadata only)
    ├─ Show commits summary
    └─ Wait for user feedback
```

### State Machine Diagram

```
                    ┌─────────────────┐
                    │   START         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Orchestrator    │ Route to workflow
                    │ (LLM routing)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
    For Each Enabled Stage:                    Error?
         │                                       │
         ▼                                       ▼
    ┌─────────────┐                      ┌─────────────┐
    │ Retrieval   │◄─────────────────────┤ Error Node  │
    │ (Two-phase) │                      └─────────────┘
    └────────┬────┘                              │
             │                                   │
             ▼                                   ▼
    ┌──────────────────┐                   Return to GUI
    │ Execution Agent  │                   (workflow_failed)
    │ (Code/Test/Sec)  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Failure Detector?│
    └──┬──────────────┬┘
       │              │
   Failed         Success
       │              │
       ▼              ▼
    ┌──────────────┐  ┌─────────────┐
    │Retry Count?  │  │ Git Commit  │
    └┬────────┬┬───┘  └────┬────────┘
     │ < 3    ││ >= 3       │
     │        │└─→ Error    │
     │        │             │
     ▼ < 3    │             ▼
  ┌─────────────────────┐   ┌──────────────┐
  │ Adaptive Retrieval  │   │ More Stages? │
  │ (Enhanced context)  │   └┬────────────┬┘
  └──────────┬──────────┘    │            │
             │            No │            │ Yes
             │               │            │
             │               ▼            ▼
         Retry Agent     ┌──────────┐  Go to Next
             │           │ Aggreg-  │  Stage
             │           │ ation    │  (loop)
             │           └────┬─────┘
             │                │
             └────────────┬───┘
                          │
                          ▼
                    ┌───────────┐
                    │ Send to   │
                    │ GUI       │
                    │ (metadata)│
                    └───────────┘
                          │
                          ▼
                    ┌───────────┐
                    │   END     │
                    └───────────┘
```

---

## API SPECIFICATION

### Detailed Endpoint Reference

#### 1. POST /api/workflow/submit

**Purpose**: Submit workflow request to backend

**Request**:
```json
{
    "workflow_id": "workflow_feature_001",
    "workflow_type": "feature_implementation",
    "user_query": "Implement JWT authentication with 1 hour expiration",
    
    "workflow_config": {
        "stages": [
            {"id": "code_generation", "agent": "code_generation", "enabled": true},
            {"id": "test_generation", "agent": "test_generation", "enabled": true}
        ]
    },
    
    "agents_config": {
        "code_generation": {
            "model": "primary",
            "role": "code_generation",
            "retrieval_needs": ["file_level_semantic", "function_ast_selective"],
            "context_limits": {"max_tokens": 3000}
        },
        "test_generation": {
            "model": "primary",
            "role": "test_generation",
            "retrieval_needs": ["test_examples_only"],
            "context_limits": {"max_tokens": 2000}
        }
    },
    
    "retrieval_config": {
        "enabled": true,
        "strategy": "TART_code_generation"
    },
    
    "mcp_config": {
        "python_tools": {"enabled": true},
        "language_servers": {"python": {"enabled": true}}
    },
    
    "workspace_context": {
        "workspace_id": "ws_jwt_feature_001",
        "working_dir": "/home/user/my-project",
        "language": "python",
        "framework": "fastapi"
    },
    
    "correlation_id": "req_xyz_12345"
}
```

**Response** (202 Accepted):
```json
{
    "execution_id": "exec_abc123xyz789",
    "workflow_id": "workflow_feature_001",
    "status": "accepted",
    "message": "Workflow queued for execution",
    "streaming_url": "ws://localhost:8000/api/workflow/exec_abc123xyz789/stream"
}
```

**Error Response** (400 Bad Request):
```json
{
    "error": "configuration_error",
    "message": "Missing required field: 'user_query'",
    "correlation_id": "req_xyz_12345"
}
```

---

#### 2. GET /api/workflow/{execution_id}/status

**Purpose**: Get current workflow status

**Response** (200 OK):
```json
{
    "execution_id": "exec_abc123xyz789",
    "workflow_id": "workflow_feature_001",
    "status": "running",
    "current_stage": "code_generation",
    "progress_percent": 45,
    "stages_completed": 0,
    "total_stages": 2,
    "commits_completed": 0,
    "last_update": "2025-11-04T18:35:22.123456Z"
}
```

---

#### 3. WebSocket /api/workflow/{execution_id}/stream

**Purpose**: Stream real-time updates (SSE or WebSocket)

**Message Types**:

```json
// Status Update
{
    "type": "status_update",
    "correlation_id": "req_xyz_12345",
    "stage_id": "code_generation",
    "workflow_id": "workflow_feature_001",
    "timestamp": "2025-11-04T18:35:22.123456Z",
    "status": "Generating code...",
    "progress_percent": 60,
    "metrics": {
        "tokens_generated": 450,
        "inference_speed_tokens_per_sec": 22,
        "elapsed_seconds": 20
    }
}

// Workflow Complete (Metadata Only - NO CODE)
{
    "type": "workflow_complete",
    "correlation_id": "req_xyz_12345",
    "workflow_id": "workflow_feature_001",
    "status": "success",
    "timestamp": "2025-11-04T18:36:50.654321Z",
    "commits": [
        {
            "commit_id": "abc1234567890",
            "agent": "code_generation",
            "message": "feat: Implement JWT authentication with 1 hour expiration",
            "files_changed": 1,
            "additions": 142,
            "deletions": 0,
            "timestamp": "2025-11-04T18:36:45.654321Z"
        },
        {
            "commit_id": "def9876543210",
            "agent": "test_generation",
            "message": "test: Add JWT authentication tests",
            "files_changed": 1,
            "additions": 85,
            "deletions": 0,
            "timestamp": "2025-11-04T18:36:48.654321Z"
        }
    ],
    "total_changes": {
        "files": 2,
        "additions": 227,
        "deletions": 0
    }
}

// Error
{
    "type": "error",
    "correlation_id": "req_xyz_12345",
    "error_code": "agent_max_retries",
    "message": "Code generation failed after 3 attempts",
    "details": "Syntax error in generated code"
}
```

---

#### 4. GET /api/workflow/{execution_id}/commit/{commit_id}/diff

**Purpose**: Get unified diff for specific commit (lazy load)

**Response** (200 OK):
```json
{
    "commit_id": "abc1234567890",
    "agent": "code_generation",
    "file_path": "src/auth/jwt_handler.py",
    "change_type": "created",
    "additions": 142,
    "deletions": 0,
    "diff": "--- /dev/null\n+++ b/src/auth/jwt_handler.py\n@@ -0,0 +1,25 @@\n+import jwt\n+from datetime import datetime, timedelta\n+...",
    "hunks": [
        {
            "hunk_id": "hunk_1",
            "lines_start": 1,
            "lines_end": 25,
            "summary": "Adds create_jwt_token() function"
        }
    ]
}
```

---

#### 5. GET /debug/metrics

**Purpose**: Get agent execution metrics (debug)

**Response**:
```json
{
    "metrics": {
        "code_generation": {
            "total_executions": 142,
            "successful": 135,
            "failed": 7,
            "success_rate": 0.951,
            "avg_latency_seconds": 45.2,
            "p95_latency_seconds": 62.3,
            "total_tokens": 285000,
            "avg_tokens_per_execution": 2113
        },
        "retrieval": {
            "total_queries": 142,
            "cache_hits": 45,
            "cache_hit_rate": 0.317,
            "avg_latency_seconds": 2.8,
            "p95_latency_seconds": 5.2
        }
    }
}
```

---

#### 6. GET /debug/vram

**Purpose**: Monitor GPU VRAM usage (debug)

**Response**:
```json
{
    "vram": {
        "used_mb": 5234,
        "available_mb": 10766,
        "total_mb": 16000,
        "percentage": 32.7,
        "peak_mb": 6100,
        "components": {
            "mistral_7b": 4200,
            "embedding_model": 500,
            "gui_buffer": 34
        }
    }
}
```

---

## DATABASE SCHEMA

### Qdrant Collections

#### Collection: workspace_files

**Purpose**: File-level semantic embeddings (Phase 1 retrieval)

**Schema**:
```yaml
name: "workspace_files"
vector_config:
  size: 768  # nomic-embed-text-v1.5 dimension
  distance: "Cosine"

payload_schema:
  workspace_id:
    type: "keyword"
    index: true
  
  file_path:
    type: "keyword"
    index: true
  
  file_name:
    type: "text"
  
  relative_path:
    type: "text"  # Path relative to workspace root
  
  language:
    type: "keyword"
  
  file_size_kb:
    type: "integer"
  
  docstring:
    type: "text"
  
  imports:
    type: "array"
    value_type: "text"
  
  indexed_at:
    type: "datetime"

# Sparse vectors for BM25 hybrid search
sparse_vectors:
  bm25:
    index: true

# HNSW indexing for fast search
hnsw_config:
  m: 16
  ef_construct: 200
  ef_search: 100

# Quantization for memory efficiency
quantization:
  scalar:
    type: "int8"
    quantile: 0.99
```

#### Collection: workspace_functions

**Purpose**: Function-level AST embeddings (Phase 2 retrieval)

**Schema**:
```yaml
name: "workspace_functions"
vector_config:
  size: 768
  distance: "Cosine"

payload_schema:
  workspace_id:
    type: "keyword"
    index: true
  
  function_name:
    type: "text"
    index: true
  
  file_path:
    type: "keyword"
    index: true
  
  relative_path:
    type: "text"
  
  file_included_in_stage:
    type: "array"
    value_type: "integer"
    index: true
  
  signature:
    type: "text"
  
  docstring:
    type: "text"
  
  line_number:
    type: "integer"
  
  line_number_end:
    type: "integer"
  
  return_type:
    type: "text"
  
  parameters:
    type: "array"
    value_type: "text"
  
  language:
    type: "keyword"
  
  indexed_at:
    type: "datetime"

sparse_vectors:
  bm25:
    index: true

hnsw_config:
  m: 16
  ef_construct: 200
  ef_search: 100
```

---

## CONFIGURATION MANAGEMENT

### Runtime Configuration Flow

```
1. GUI loads local config files:
   ├─ config/agents.yaml
   ├─ config/workflows.yaml
   ├─ config/retrieval.yaml
   └─ config/mcp_integration.yaml

2. User selects workspace (e.g., /home/user/my-project)

3. Backend checks .agentic-ide/config.yaml in workspace root
   └─ If missing: Use defaults

4. GUI submits workflow request with complete config in payload
   ├─ Backend receives config in request
   └─ Backend does NOT need local config files

5. Backend validates config:
   ├─ Schema check
   ├─ Version compatibility
   └─ Workspace_id scoping
```

### Configuration Validation

```python
# backend/config_validator.py

class ConfigValidator:
    @staticmethod
    def validate_workflow_config(config: Dict) -> bool:
        required = ["stages"]
        if not all(k in config for k in required):
            raise ValueError(f"Missing required fields: {required}")
        
        for stage in config["stages"]:
            if not all(k in stage for k in ["id", "agent", "enabled"]):
                raise ValueError("Invalid stage config")
        
        return True
    
    @staticmethod
    def validate_agent_config(config: Dict) -> bool:
        required = ["model", "role", "retrieval_needs"]
        if not all(k in config for k in required):
            raise ValueError(f"Missing required fields: {required}")
        
        if not isinstance(config["retrieval_needs"], list):
            raise ValueError("retrieval_needs must be list")
        
        return True
```

---

## DEPLOYMENT & EXECUTION

### Docker Container Setup

```dockerfile
# Dockerfile.backend

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install fastapi uvicorn langchain langgraph qdrant-client ollama pyyaml gitpython

# Copy source
COPY backend/ /app/backend/

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Startup Sequence

```bash
# 1. Start dependencies
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
docker run -d --name ollama -p 11434:11434 ollama/ollama

# 2. Load initial model
docker exec ollama ollama pull mistral-7b-instruct-v0.3

# 3. Start backend
docker run -d \
  --name agentic-backend \
  -p 8000:8000 \
  --link qdrant \
  --link ollama \
  agentic-ide-backend

# 4. Verify
curl http://localhost:8000/health
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Core Infrastructure (Weeks 1-2, 80 hours)

**Week 1**:
- [ ] FastAPI skeleton (app structure, error handling)
- [ ] Qdrant connection & client setup
- [ ] Request/response models (Pydantic)
- [ ] API Gateway (basic endpoints)

**Week 2**:
- [ ] LangGraph state machine setup
- [ ] Ollama integration
- [ ] Config validation
- [ ] Logging infrastructure (correlation IDs)

**Deliverable**: Basic API accepting requests, Qdrant connected

---

### Phase 2: Orchestrator & Routing (Weeks 2-3, 60 hours)

- [ ] Orchestrator Agent implementation
- [ ] Workflow selection logic
- [ ] LangGraph node implementations
- [ ] Conditional edge routing

**Deliverable**: Workflow routing working, requests flow through orchestrator

---

### Phase 3: Retrieval & Scoping (Weeks 3-4, 100 hours)

- [ ] Two-phase retrieval (file-level + AST)
- [ ] Workspace_id filtering
- [ ] Stage-specific retrieval needs
- [ ] Caching layer
- [ ] Adaptive retrieval on failure

**Deliverable**: Retrieval agent working, context-aware retrieval per stage

---

### Phase 4: Execution Agents (Weeks 4-5, 80 hours)

- [ ] Code generation agent
- [ ] Test generation agent
- [ ] Security analysis agent
- [ ] Failure detectors
- [ ] SUMMARY extraction

**Deliverable**: Agents generate output, failures detected

---

### Phase 5: Git Integration (Weeks 5-6, 60 hours)

- [ ] Git manager (branch creation, commits)
- [ ] File writing to workspace
- [ ] Semantic commit messages
- [ ] Merge strategies
- [ ] working_dir scoping

**Deliverable**: Changes committed to git, branch strategy working

---

### Phase 6: Error Handling & Recovery (Weeks 6-7, 70 hours)

- [ ] Config validation & fallbacks
- [ ] Agent retry logic
- [ ] Adaptive retrieval on failure
- [ ] Error messaging
- [ ] Logging & debugging

**Deliverable**: Robust error handling, graceful degradation

---

### Phase 7: ACP Streaming (Weeks 7-8, 50 hours)

- [ ] WebSocket/SSE implementation
- [ ] Status update callbacks
- [ ] Workflow completion callbacks
- [ ] Client connection management

**Deliverable**: Real-time streaming updates to GUI

---

### Phase 8: Testing & Optimization (Weeks 8-9, 100 hours)

- [ ] Unit tests (pytest)
- [ ] Integration tests
- [ ] Performance benchmarking
- [ ] Regression testing (pytest-harvest)
- [ ] Documentation

**Deliverable**: Test suite passing, performance baselines established

---

## DEVELOPMENT GUIDELINES

### Code Organization

```
backend/
├── main.py                    # FastAPI app entry point
├── config/
│   ├── settings.py           # Global settings
│   ├── logging_config.py      # Structured logging
│   └── constants.py           # Constants
├── api/
│   ├── routes.py             # HTTP endpoints
│   ├── models.py             # Request/response models
│   └── errors.py             # Error handlers
├── agents/
│   ├── orchestrator.py        # Orchestrator agent
│   ├── retrieval.py           # Retrieval agent
│   ├── code_generation.py     # Code agent
│   ├── test_generation.py     # Test agent
│   └── security_analysis.py   # Security agent
├── services/
│   ├── langgraph_builder.py   # State machine
│   ├── git_manager.py         # Git operations
│   ├── config_manager.py      # Config handling
│   └── qdrant_manager.py      # Vector DB ops
├── utils/
│   ├── logging.py             # Logging helpers
│   ├── errors.py              # Error utilities
│   └── validation.py          # Input validation
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

### Development Workflow

```bash
# 1. Local development
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Run services locally
docker-compose up -d  # Qdrant, Ollama

# 3. Development server
uvicorn backend.main:app --reload

# 4. Run tests
pytest tests/ -v --cov=backend

# 5. Linting
ruff check backend/

# 6. Type checking
mypy backend/
```

### Error Handling Best Practices

```python
# Always include correlation_id in logs
import logging

logger = logging.getLogger(__name__)

try:
    result = process_request(request)
except Exception as e:
    logger.error(
        "request_failed",
        extra={
            "correlation_id": request.correlation_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
    )
    raise
```

### Testing Guidelines

```python
# Use fixtures for mocking
@pytest.fixture
def mock_qdrant():
    with patch('backend.services.qdrant_manager.QdrantClient'):
        yield

# Test each node independently
def test_orchestrator_node():
    state = WorkflowState(...)
    result = orchestrator_node(state)
    assert result.current_stage == "code_generation"

# Test error scenarios
def test_retrieval_timeout():
    # Mock Qdrant timeout
    # Verify fallback to defaults
    pass
```

---

**END OF BACKEND SPECIFICATION**

This document is your complete guide to implementing the backend system. Every architectural decision is explained, every component is detailed, and every integration point is specified.

**Questions?** Refer back to:
- Section 4 (API Specification) for endpoint details
- Section 5 (Data Flow) for request lifecycle
- Section 6 (Components) for implementation details
- Section 13 (Roadmap) for phase breakdown

