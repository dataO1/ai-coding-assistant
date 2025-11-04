Technical Architecture Specification: Agentic IDE (Multi-Agent, Autonomous Retrieval with Selective AST via Two-Phase Qdrant Strategy, Workflow-Aware Strategies, LangGraph Deterministic Routing, Integrated GUI)
System Overview

A self-hosted FOSS agentic IDE combining a Rust GPU-rendered GUI client (Iced) with a Python LangChain multi-agent orchestration backend via Agent Client Protocol (ACP). The GUI client provides real-time visual feedback, code editing, diff visualization, and user review interfaces. The backend system is centered around an Orchestrator Agent—a reasoning LLM with its own capability profile—that receives user queries and context, performs LLM reasoning to understand the task and select the most appropriate workflow, then decides which optional stages should be included based on task context and reasoning_guidance. After stage inclusion decisions, the orchestrator retrieves the workflow-specific retrieval strategy configuration (TART pattern: Task-Aware Retrieval with Instructions), assembles a fixed execution plan via deterministic configuration-based logic, and delegates to an Autonomous Retrieval Agent that independently analyzes task semantics using workflow-specialized strategies with two-phase selective retrieval: file-level semantic search via existing Qdrant vector DB (upfront), followed by selective AST parsing and function-level indexing (only for filtered files), generating context-aware queries, routing to appropriate sources, and executing parallel retrieval-augmented generation. The Retrieval Agent adapts behavior based on workflow type: for code workflows, it pre-computes file-level embeddings during workspace initialization and executes selective function-level AST indexing per-task using Tree-sitter, providing on-demand LSP via MCP tools during execution; for non-code workflows, it focuses on document-level retrieval. Retrieved results are merged via a Context Fusion Service combining cross-encoder semantic reranking with deterministic deduplication and token budget management. The execution workflow is modeled as a LangGraph state machine with nodes representing stages and conditional edges implementing deterministic routing based on success/failure outcomes. When stages fail, conditional edges automatically route to an Adaptive Retrieval Node that triggers the same Autonomous Retrieval Agent to dynamically generate failure-specific retrieval queries using workflow-aware strategies, or route to the next stage according to the routing table. Specialist agents execute stages with access to workflow-contextualized retrieval, MCP-based static analysis tools (for code workflows), and git-based version control. GUI client receives real-time updates via ACP callbacks, displays execution progress, presents batched diffs for user review, and provides refinement feedback loops. Full git-based change tracking and rollback support enable safe autonomous code generation.
Architecture Components
GUI Client Layer (Rust + Iced)

Responsibilities:

    Render interactive user interface for code editing, workflow visualization, progress tracking

    Capture user queries and context (files, selections, specifications)

    Send requests to backend via Agent Client Protocol (ACP)

    Receive real-time updates from backend (execution progress, diffs, errors)

    Display execution graph state (current node, routing decisions)

    Visualize batched diffs with syntax highlighting

    Provide user review interface (accept/reject changes, provide feedback)

    Maintain local git state visibility (branch, commits, diffs)

Backend Integration Points:

text
ACP Client Channels:
  ├─ Request: user_query + context → Orchestrator Agent
  ├─ Response: workflow_selected + execution_plan
  ├─ Stream: execution_progress (node_executing, edge_routing, stage_complete)
  ├─ Stream: context_available (retrieval_completed, context_summary)
  ├─ Stream: diffs_ready (batched file changes for review)
  ├─ Callback: user_accepts_changes → git commit
  └─ Callback: user_provides_feedback → adaptive_retrieval trigger (optional)

GUI State Management:

text
Workflow Visualization:
  - Display: LangGraph execution (current node, completed nodes, next edges)
  - Show: Stage names, parallel agents, routing decisions
  - Highlight: Current execution, failures, enrichment cycles

Progress Tracking:
  - Timeline: Planning phase → Retrieval → Execution stages
  - Metrics: % complete, iteration count, retrieval context used (tokens)
  - Real-time: Agent outputs, generated code snippets (preview)

Diff Viewer:
  - File-by-file diffs from all stages
  - Syntax highlighting (language-aware)
  - Batch operations: accept all, reject all, accept per-file
  - Diff annotations: which stage generated, which agent, confidence level

User Feedback Loop:
  - Optional: Provide critique on generated code
  - Triggers: Adaptive retrieval with user feedback as context
  - Result: Refined generation in next iteration

LangChain Integration (GUI Layer):

text
Components:
  - langchain_core.rpc.acp (Agent Client Protocol)
  - Streaming callbacks over ACP
  - Real-time state updates to GUI

Core Principles

LLM Reasoning for Understanding, Selection, & Stage Inclusion: Orchestrator LLM reasons about user intent, selects best workflow, and decides which optional stages to include; orchestrator does NOT generate retrieval queries.

Workflow-Aware Retrieval Strategy Selection (TART Pattern): Orchestrator passes workflow type and retrieval strategy configuration to Retrieval Agent. Retrieval Agent activation is strategy-driven (from config), not self-classifying. Follows Task-Aware Retrieval with Instructions research pattern.

Two-Phase Selective Retrieval with Qdrant (File-Level then Function-Level): Retrieval Agent uses existing Qdrant vector DB with two document types: file-level (generated during workspace initialization, reused for file filtering) and function-level (generated selectively per task after AST parsing filtered files). File-level search filters to relevant files (~50-100 of 10k), then selective AST parsing occurs only on those files, reducing upfront parsing overhead from 10s to ~2-3s while maintaining precision.

Autonomous Retrieval Agent with Domain Specialization: Dedicated agent independently analyzes tasks using workflow-specific strategies, generates context-aware queries, routes to appropriate sources, and executes retrieval without orchestrator involvement. Behavior adapts per workflow type (code vs. non-code) via configuration, not generic. Executes two-phase retrieval: file-level filtering (using pre-computed file embeddings) followed by selective function-level indexing and search.

Separation of Concerns: Orchestrator handles strategy selection and coordination; Retrieval Agent handles all query generation and execution within workflow-specified parameters; GUI client handles user interaction and diff review. Clean architectural boundaries enable independent optimization and testing.

Code-Specific Strategies (Selective AST + LSP + MCP): For code workflows: Retrieval Agent performs file-level semantic search (150ms using existing Qdrant) to identify ~50-100 relevant files, then selectively parses those files' AST via Tree-sitter (2-3s, not 10s for all), generates function-level embeddings for those functions only, stores in same Qdrant index. During execution, specialist agents access LSP via MCP tools (on-demand) for precise type information. Non-code workflows skip static analysis and AST entirely.

Non-Code Retrieval Strategies: For planning, document, and other non-code workflows, Retrieval Agent focuses on document-level semantic retrieval via Qdrant file-level search, decision log searches, specification analysis. No AST parsing, no language-specific tools. Configuration-driven specialization prevents wasted effort.

Config-Based Execution Plan Assembly: Fixed execution plan built from workflow YAML configuration deterministically (no LLM) after stage inclusion is decided; purely structural logic.

LangGraph Deterministic Routing: Execution workflow modeled as state machine with nodes for stages and conditional edges for routing. All routing paths encoded upfront in graph structure, eliminating runtime observer pattern. Routing decisions determined by stage failure outcomes and max_attempts counters in execution state.

Parallel Retrieval-Augmented Generation: Retrieval Agent pre-computes file-level context during workspace initialization and executes task-specific selective retrieval during planning phase; zero per-agent retrieval overhead during execution. Each stage receives optimized, specialized context (not generic).

Adaptive Retrieval as Graph Node: Adaptive retrieval is a node in the execution graph, not a separate reactive component. Triggered by conditional edges when failure occurs and retry is beneficial. Same Autonomous Retrieval Agent executes both upfront and adaptive retrieval using same workflow-aware strategies and two-phase approach.

Intelligent Failure Analysis: Retrieval Agent autonomously analyzes failure context using workflow-specific strategies; no separate classifier component. Direct semantic reasoning about what information would help fix failures within domain context.

Cross-Encoder Semantic Reranking: Context fusion uses learned ranking (not heuristics) to prioritize relevant information, reducing noise and hallucination risks.

Validation & Self-Correction: Validation layer checks context groundedness before injection into retry stage, preventing hallucination cascades.

Dependency-Aware Context: Subsequent retries receive enriched context addressing previous stage failures via workflow-aware retrieval executed by autonomous Retrieval Agent.

Retrieval Scoping to Workspace: All retrieval operations filtered to workspace-relevant files only; excluded patterns (node_modules, .git, build artifacts) prevent context pollution.

Workspace-Scoped Embeddings: Qdrant maintains separate collections per workspace; no global codebase cross-contamination. File-level and function-level indexing both scoped to workspace.

Multi-Source RAG with Workflow-Specific Routing: Retrieval Agent autonomously aggregates from sources appropriate to workflow type. Code workflows: codebase (via Qdrant, filtered), LSP (on-demand), web, CVE database, documentation. Non-code workflows: codebase (via Qdrant, document-level), web, documentation (no LSP/static analysis).

MCP Integration for Static Analysis Tools: Code workflows access Tree-sitter AST and LSP via standardized Model Context Protocol, enabling precise code understanding without token bloat. Agents call MCP tools on-demand during execution, not upfront. LSP queries execute selectively based on workflow config.

Fixed Execution Plan: Once assembled, execution plan is immutable during workflow execution; reflected in graph structure. Only Adaptive Retrieval augments context post-failure.

Binary Stage Routing: Stage routing uses only success/failure boolean outcomes. Encoded as conditional edge conditions evaluated on stage completion.

If-Then-Else Logic: Conditional edges implement: if stage.failure: route_to_failure_path else: route_to_success_path (deterministic, encoded in graph).

Max Attempts = Immediate Failure: When stage reaches max_attempts, conditional edge routes to failure path (no re-evaluation). Enforced by execution state counter.

Aggregated Failure Decision: Multiple parallel agents' failures aggregated via configurable strategy (any-fails, all-fail, majority-fail). Result stored in execution state as single boolean flag for conditional edge evaluation.

Agent-Defined Failure Criteria: Each agent returns boolean failure flag with rich context; orchestrator never second-guesses.

Parallel Within-Stage: Multiple agents execute in parallel; aggregated results determine stage outcome.

Sequential Between-Stages: Stages execute in order defined by graph edges; next stage determined by conditional routing based on execution state.

Single Source of Truth: Agent orchestration layer owns filesystem, embeddings, tool execution, git state, LangGraph execution state.

User-Centric Review: All modifications batched and reviewed via GUI before acceptance; feedback loops allow refinement (optional, feeds into adaptive retrieval).

Full Auditability: Every action committed to git; full history available for rollback. LangGraph execution history automatically tracked for all iterations. GUI displays commit history.

Schema-First: Tool definitions, workflows, capabilities, retrieval strategies, and task contexts generated from canonical schemas.

LangChain Integration: Built on LangChain ecosystem using standard patterns (agents, chains, tools, retrievers, memory). LangGraph used for workflow execution and state management. MCP integration via LangChain-native tools.
Architecture Layers
Layer 0: Workflow Selection + Stage Inclusion via LLM Reasoning (Focused Orchestrator)

Orchestrator LLM performs focused reasoning on strategy only (no retrieval query generation):

text
User query (from GUI): "Implement authentication feature"
Project context: {type: "web_service", languages: ["python"], security_sensitive: true}
Available workflows: [feature_workflow, architecture_discussion_workflow, ...]

    ↓
PART 1: WORKFLOW SELECTION (LLM Reasoning)

Orchestrator LLM analyzes:
  - User query semantically
  - Available workflows + selection criteria
  - Project context + agent availability

Orchestrator decides: SELECT feature_workflow

    ↓
PART 2: STAGE INCLUSION (LLM Reasoning using reasoning_guidance)

Orchestrator LLM evaluates each optional stage:
  - Stage 1 (required): Include (no reasoning needed)
  - Stage 2 (required): Include (no reasoning needed)
  - Stage 3 (optional): Reasoning_guidance says "Include if auth/security-sensitive"
    Context: JWT auth (security-critical), project.security_sensitive=true
    Decision: INCLUDE
  - Stage 4 (optional): Reasoning_guidance says "Include if production-ready"
    Context: No 'rapid' keyword, standard development mode
    Decision: INCLUDE

    ↓
Output to next phase: {
  selected_workflow: "feature_workflow",
  stages_to_include: [1, 2, 3, 4],
  stages_to_skip: [],
  stage_inclusion_reasoning: {...}
}

NO retrieval query generation (delegated to Retrieval Agent)

LangChain Integration (Layer 0):

text
Components:
  - langchain.agents.Agent (orchestrator agent wrapper)
  - langchain.chains.LLMChain (workflow selection chain)
  - langchain.prompts.ChatPromptTemplate (workflow + stage prompts)
  - langchain.output_parsers.JsonOutputParser (parse decisions)
  - langchain.callbacks.CallbackManager (trace orchestrator)
  - ACP callbacks to GUI: execution_progress

Layer 0.5: Workspace Initialization with File-Level Indexing

One-time workspace setup: Create file-level embeddings in Qdrant for future file filtering:

text
Triggered: On workspace load (or when workspace changes)

Step 1: File Discovery
  Scan: Entire workspace directory
  Exclude: .gitignore patterns, build artifacts, node_modules, .git
  Result: File list {auth.py, token_handler.py, jwt_utils.py, ...}
  Time: ~500ms

Step 2: File Metadata Collection (Per-File)
  For each file:
    Extract:
      - File name: "auth.py"
      - File path: "src/auth/auth.py"
      - First docstring (if exists): "JWT authentication module"
      - Import statements: "from jwt import ..., import typing"
      - Language/extension: ".py"

    Create document: "{filename}: {docstring}. Imports: {imports}"
    Time per file: ~1ms

Step 3: Generate File-Level Embeddings
  Embedding model: nomic-embed-text
  For each file metadata document:
    Generate embedding vector
  Time: ~50-100ms for 10k files (batched)

Step 4: Store in Qdrant (File-Level Collection)
  Collection: "workspace_files"
  Documents:
    {
      id: "file_src_auth_auth_py",
      content: "auth.py: JWT authentication module. Imports: jwt, typing, ...",
      embedding: [0.234, -0.456, ...],
      metadata: {
        type: "file",
        file_path: "src/auth/auth.py",
        file_name: "auth.py",
        language: "python",
        workspace_id: "workspace_123",
        indexed_at: "2025-11-04T14:00:00Z"
      }
    }

  Time: ~100ms for bulk insert

Total Workspace Initialization: ~1.5-2 seconds (one-time)

Result: Qdrant has file-level index ready for ALL future queries
        Enables 150ms file filtering on task arrival

LangChain Integration (Layer 0.5):

text
Components:
  - langchain.document_loaders.DirectoryLoader (file discovery)
  - langchain.embeddings.HuggingFaceEmbeddings (nomic-embed-text)
  - langchain.vectorstores.Qdrant (bulk insert file documents)
  - Workspace initialization triggered on: workspace_load event

Layer 0.6: Workflow-Specific Retrieval Strategy Configuration (TART Pattern)

Orchestrator retrieves and passes workflow-specific retrieval strategy:

text
After Orchestrator selects workflow:

1. Lookup: workflows/[workflow_name].yaml
   Extract: retrieval_strategy_config section

2. For Code Workflows (e.g., feature_workflow):
   {
     workflow_type: "code_implementation",
     retrieval_enabled: true,
     retrieval_strategy: "code_domain_selective_ast",

     strategy_config: {
       file_level_search: {
         enabled: true,
         vector_db: "qdrant",
         collection: "workspace_files",
         top_k: 50,
         time_target_ms: 150
       },

       selective_ast_parsing: {
         enabled: true,
         model: "tree_sitter",
         trigger: "after_file_level_search",
         parse_only: "filtered_files_from_search"
       },

       function_level_indexing: {
         enabled: true,
         vector_db: "qdrant",
         collection: "workspace_functions",
         store_selective: true,
         only_from_parsed_files: true
       },

       lsp_integration: {
         enabled: true,
         execution_timing: "on_demand",
         tools: ["get_signature", "find_definition", "get_references"]
       },

       context_sources: [
         {source: "codebase_semantic_search", strategy: "file_then_function", priority: "HIGH"},
         {source: "lsp_tools", strategy: "on_demand", priority: "HIGH"},
         {source: "web_search", strategy: "libraries_patterns", priority: "MEDIUM"},
         {source: "doc_retrieval", strategy: "framework_docs", priority: "MEDIUM"},
         {source: "cve_database", strategy: "vulnerabilities", priority: "HIGH_if_security_stage"}
       ],

       retrieval_hints: {
         focus_on: ["existing_patterns", "dependencies", "type_signatures"],
         avoid: ["test_code", "deprecated_patterns"],
         token_budget: {code_gen: 30000, test_gen: 25000, security: 20000}
       }
     }
   }

3. For Non-Code Workflows (e.g., architecture_discussion_workflow):
   {
     workflow_type: "text_analysis",
     retrieval_enabled: true,
     retrieval_strategy: "document_domain",

     strategy_config: {
       file_level_search: {
         enabled: true,
         vector_db: "qdrant",
         collection: "workspace_files",
         top_k: 30,
         time_target_ms: 150
       },

       selective_ast_parsing: {
         enabled: false,
         reason: "non_code_workflow"
       },

       lsp_integration: {
         enabled: false,
         reason: "not_applicable"
       },

       context_sources: [
         {source: "document_semantic_search", strategy: "section_level", priority: "HIGH"},
         {source: "specification_search", strategy: "sections", priority: "HIGH"},
         {source: "decision_log_search", strategy: "related_decisions", priority: "HIGH"},
         {source: "web_search", strategy: "current_patterns", priority: "MEDIUM"}
       ],

       retrieval_hints: {
         focus_on: ["existing_decisions", "rationale", "options"],
         avoid: ["implementation_details"],
         token_budget: {planning: 20000, analysis: 15000}
       }
     }
   }

4. Pass to Retrieval Agent:
   {
     user_task: "Implement JWT auth with comprehensive tests",
     workflow: "feature_workflow",
     workflow_type: "code_implementation",
     retrieval_config: {...strategy_config...}
   }

Key: Configuration is EXPLICIT (from YAML), not implicit
     Retrieval Agent follows instructions, doesn't classify

LangChain Integration (Layer 0.6):

text
Components:
  - Custom retrieval strategy loader (reads workflow YAML)
  - langchain.schema.Document (strategy configuration structure)
  - Environment-aware configuration (workspace-specific)

Layer 1: Autonomous Retrieval Agent with Selective Two-Phase Retrieval (Core Component)

Dedicated agent using existing Qdrant with two-phase strategy: file-level search, then selective function-level indexing:

text
Autonomous Retrieval Agent Architecture:

Receives from Orchestrator:
  {
    user_task: string,
    workflow_type: "code_domain" | "document_domain" | "other",
    retrieval_config: {...strategy configuration...}
  }

Responsibilities (Workflow-Adaptive, Two-Phase):
  1. Phase 1: File-level semantic search (using pre-computed embeddings)
  2. Phase 2: Selective AST parsing (only filtered files)
  3. Generate function-level embeddings (selective)
  4. Execute task-specific queries
  5. Return grounded, attributed context

Does NOT:
  - Parse all files' AST (selectively only)
  - Self-classify workflow type (Orchestrator decided)
  - Create generic queries (workflow-specific strategy)

Triggered in two modes:
  - Upfront mode (planning phase): Execute two-phase retrieval for all stages
  - Adaptive mode (graph edge): Execute two-phase retrieval for failure-specific context

Upfront Retrieval Phase (Planning Phase - Code Workflows - Two-Phase Selective):

text
Input from Orchestrator:
  {
    user_task: "Implement JWT authentication",
    workflow_type: "code_domain",
    retrieval_config: {
      file_level_search: enabled,
      selective_ast_parsing: enabled,
      ...
    }
  }

PHASE 1: File-Level Semantic Search (FAST - Uses Pre-Computed Embeddings)

  Condition: IF retrieval_config.file_level_search.enabled == true

  Query Generation (Per-Stage):
    For stage 1 (code_generation):
      Generate file-level queries:
        - "JWT authentication implementation"
        - "token handling utilities"
        - "authentication patterns"

    For stage 2 (test_generation):
      Generate file-level queries:
        - "JWT test utilities"
        - "authentication tests"

    For stage 3 (security_review):
      Generate file-level queries:
        - "JWT security validation"
        - "token verification"

  Qdrant Search (Parallel, All Stages):

    RetrieverTask_1 (file filtering for stage 1):
      Query: file-level vectors
      Collection: "workspace_files" (pre-computed, upfront)
      Filter: metadata.type == "file"
      Top-k: 50
      Result: [auth.py, token_handler.py, jwt_utils.py, ...] (~50 files)
      Time: ~100ms

    RetrieverTask_2 (file filtering for stage 2):
      Similar process
      Result: ~30-40 test-related files
      Time: ~100ms

    RetrieverTask_3 (file filtering for stage 3):
      Similar process
      Result: ~20-30 security-related files
      Time: ~100ms

    All run simultaneously: max(all) ≈ 100-150ms

  Output: execution_state.filtered_files = {
    stage_1: [list of 50 files],
    stage_2: [list of 40 files],
    stage_3: [list of 30 files]
  }

PHASE 2: Selective AST Parsing (MEDIUM - Only Filtered Files)

  Condition: IF retrieval_config.selective_ast_parsing.enabled == true

  Parse Only Filtered Files:
    For stage 1 filtered files (50 files):
      Tree-sitter parses each file (in parallel)
      Extracts functions/classes
      Time: ~1-2 seconds (50 files, ~1ms per file)

    For stage 2 filtered files (40 files):
      Similar parsing
      Time: ~0.8-1.5 seconds

    For stage 3 filtered files (30 files):
      Similar parsing
      Time: ~0.5-1 second

    All AST parsing runs in parallel: max(all) ≈ 2-3 seconds

  Output: execution_state.parsed_ast = {
    stage_1: {function_data: [...], class_data: [...]},
    stage_2: {function_data: [...], class_data: [...]},
    stage_3: {function_data: [...], class_data: [...]}
  }

PHASE 3: Function-Level Embedding Generation (Selective)

  Generate embeddings ONLY for parsed functions:
    For each function in parsed_ast:
      Create document: "{function_name}: {signature}. {docstring}"
      Generate embedding with nomic-embed-text
      Time: ~50-100ms for ~500 functions (vs. 5847 if all files)

  Output: Function embeddings ready for Qdrant

PHASE 4: Store Function-Level Documents in Qdrant

  Insert into Qdrant Collection: "workspace_functions"
  Documents:
    {
      id: "func_authenticate_auth_py_42",
      content: "def authenticate(token: str) -> Dict[str, Any]:\n  Validates JWT token.",
      embedding: [0.123, 0.456, ...],
      metadata: {
        type: "function",
        file_path: "src/auth/auth.py",
        function_name: "authenticate",
        line_number: 42,
        return_type: "Dict[str, Any]",
        parameters: ["token: str"],
        workspace_id: "workspace_123",
        file_included_in_stage: [1, 3],  # Which stages filtered this file
        indexed_at: "2025-11-04T14:15:00Z"
      }
    }

  Time: ~100-150ms for bulk insert

PHASE 5: Task-Specific Query Generation & Function-Level Search

  Retrieval Agent analyzes:
    "Task: JWT authentication implementation
     Filtered files: 50 for stage 1
     Parsed functions: 250 for stage 1
     Available strategy: function-level search

     What queries?"

  Generates function-level queries:
    For stage 1:
      - "JWT authentication functions"
      - "token validation functions"
      - "JWT initialization patterns"

  Qdrant Search (Function-Level, Parallel):

    RetrieverTask_1 (function search for stage 1):
      Query: function-level vectors
      Collection: "workspace_functions"
      Filter: metadata.type == "function" AND metadata.file_included_in_stage == 1
      Top-k: 10
      Result: [authenticate(), validate_token(), sign_token()] with signatures
      Time: ~100-150ms

    RetrieverTask_2 (function search for stage 2):
      Similar, filtered for test-related functions
      Time: ~100-150ms

    RetrieverTask_3 (function search for stage 3):
      Similar, filtered for security-related functions
      Time: ~100-150ms

    All run simultaneously: max(all) ≈ 100-150ms

PHASE 6: Web Search & Documentation Retrieval (Parallel)

  Execute in parallel with function-level search:

    Web search: "Python JWT best practices 2025"
      Time: ~300ms

    Doc retrieval: "Flask JWT integration"
      Time: ~200ms

    Max: ~300ms

PHASE 7: Result Aggregation & Compression

  For each stage:
    Combine:
      - Function-level results (function signatures, file locations)
      - Web search results (patterns, libraries)
      - Doc results (framework guidance)

    Deduplicate across sources
    Compress to token budget (30k for code, 25k for test, 20k for security)
    Attribute sources
    Store indexed by stage_id

  Output: execution_state.retrieval_context = {
    1: {context: "...", functions_retrieved: 10, sources: [codebase, web, docs], tokens: 30000},
    2: {context: "...", functions_retrieved: 8, sources: [...], tokens: 25000},
    3: {context: "...", functions_retrieved: 6, sources: [...], tokens: 20000}
  }

Total Upfront Time (Code Workflow):
  Phase 1: ~150ms (file-level search, uses pre-computed)
  Phase 2: ~2-3s (selective AST parsing)
  Phase 3-4: ~200ms (function embedding + Qdrant insert)
  Phase 5: ~150ms (function-level search)
  Phase 6: ~300ms (web + docs, parallel with phase 5)
  Total: ~2.8-3.5s (vs. 11s with all-file AST upfront)

  Savings: ~7-8 seconds per code workflow task

Upfront Retrieval Phase (Planning Phase - Non-Code Workflows):

text
Input from Orchestrator:
  {
    user_task: "Discuss JWT architecture decisions",
    workflow_type: "document_domain",
    retrieval_config: {
      file_level_search: enabled,
      selective_ast_parsing: disabled,
      ...
    }
  }

PHASE 1: File-Level Semantic Search (SAME - Uses Pre-Computed)

  Query: "JWT architecture, authentication design"
  Collection: "workspace_files"
  Filter: metadata.type == "file"
  Top-k: 30
  Result: Document/spec files related to architecture
  Time: ~150ms

PHASE 2: Skip AST Parsing

  Condition: IF retrieval_config.selective_ast_parsing.enabled == false
  Action: Skip (not applicable to documents)

PHASE 3: Document-Level Query Generation

  Generate queries for document sections:
    - "JWT architecture decisions"
    - "authentication design rationale"
    - "previous JWT discussions"

  Qdrant Search (Document-Level):
    Query: document-level vectors
    Collection: "workspace_files"
    Filter: metadata.file_path in [filtered files from Phase 1]
    Time: ~100-150ms

PHASE 4: Decision Log & Web Search

  Parallel with Phase 3:
    Decision log search: ~150ms
    Web search: ~300ms
    Max: ~300ms

Total Upfront Time (Non-Code Workflow):
  Phase 1: ~150ms (file filtering)
  Phase 3: ~150ms (document search)
  Phase 4: ~300ms (decision log + web, parallel)
  Total: ~600ms (vs. 11s for code, significantly faster)

Adaptive Retrieval (Graph Edge Trigger - Selective, Workflow-Aware):

text
When conditional edge detects: stage_failure == true AND max_attempts_not_exceeded

Retrieval Agent receives (with workflow context):
  {
    trigger_mode: "adaptive",
    failure_context: {...stage failure output...},
    retry_stage: 1,
    user_task: "...",
    workflow_type: "code_domain",
    retrieval_config: {...},
    execution_state.filtered_files: {...}  # Reuse filtered files
  }

Analyzes autonomously using workflow-aware strategy:
  "Given failure context + workflow strategy + previously filtered files, what queries?"

  For Code Workflows (Selective):
    - Reuse: filtered_files[retry_stage] from upfront Phase 1
    - Skip: Phase 1 (file filtering) and Phase 2 (AST parsing)
      (Already have parsed_ast for filtered files)
    - Execute: Function-level queries targeting failure context
    - Example: "Failure: Test assertion failed"
      Query: "Edge cases in JWT functions, corner case handling"
      Search: Only within already-parsed functions

    Time: ~300-400ms (reuses previous parsing)

  For Non-Code Workflows (Selective):
    - Reuse: filtered_files from upfront Phase 1
    - Skip: AST entirely
    - Execute: Document search with failure context
    - Example: "Failure: Incomplete decision information"
      Query: "Related architectural decisions, implications"
      Search: Within filtered documents

    Time: ~200-300ms

Result: Enriched context stored in execution_state.enriched_context

Retrieval Sources (Multi-Source, Using Qdrant + Tools):

text
Code Workflow Sources:

Codebase Semantic Search via Qdrant (Two-Level):

  File-Level (Upfront):
    ├─ Collection: "workspace_files"
    ├─ Documents: File metadata (pre-computed at workspace init)
    ├─ Query: File-level semantic search
    ├─ Result: Filtered file list (~50-100 files)
    └─ Time: ~150ms

  Function-Level (Per-Task):
    ├─ Collection: "workspace_functions"
    ├─ Documents: Function signatures + docstrings (generated selectively)
    ├─ Query: Function-level semantic search within filtered files
    ├─ Result: Function references + code snippets
    └─ Time: ~150ms

LSP Tools (On-Demand, MCP):
  ├─ Provider: Language Server Protocol via MCP
  ├─ Tools: GetSignature, FindDefinition, GetReferences, GetType
  ├─ When: Agent queries during execution (not upfront)
  ├─ Speed: ~100-500ms per query
  └─ Precision: Language-aware, type-accurate

Web Search:
  ├─ Provider: DuckDuckGo, Brave API
  ├─ Query: Libraries, patterns, best practices
  └─ Integration: Caching layer

CVE Database:
  ├─ Source: NVD API, indexed locally
  ├─ Query: Vulnerabilities (for security workflows)
  └─ Integration: Triggered by security stage

Documentation:
  ├─ Sources: RFC, OWASP, framework docs, MDN
  ├─ Method: Web search with site filters
  └─ Integration: Deduplicated with web search

Non-Code Workflow Sources:

Document Semantic Search via Qdrant:
  ├─ Collection: "workspace_files"
  ├─ Query: Document-level semantic search
  ├─ Result: Relevant document sections
  └─ Time: ~150ms

Decision Log Search:
  ├─ Index: Previous architectural decisions
  ├─ Query: Related decisions, implications
  └─ Result: Decision references + rationale

Specification Search:
  ├─ Collection: "workspace_files" (filtered by type)
  ├─ Query: Architectural requirements
  └─ Result: Relevant requirements

Web Search:
  ├─ Query: Current patterns, standards, best practices
  └─ Same as code workflows

LangChain Integration (Layer 1 - Retrieval Agent):

text
Components:
  - langchain.agents.AgentExecutor (retrieval agent wrapper)
  - langchain.chains.LLMChain (query generation chain)
  - langchain.retrievers.SelfQueryRetriever (autonomous query generation)
  - langchain.retrievers.ContextualCompressionRetriever (compress results)
  - langchain.vectorstores.Qdrant (single vector store, two collections)
  - langchain.embeddings.HuggingFaceEmbeddings (nomic-embed-text)
  - langchain.tools.DuckDuckGoSearchRun (web search)
  - langchain.document_loaders.WebBaseLoader (doc retrieval)
  - langchain_experimental.text_splitter.SemanticChunker (document sections)
  - langchain.chains.ConversationalRetrievalChain (adaptive mode)
  - langchain.memory.ConversationBufferMemory (iteration tracking)
  - langchain.mcp.MCPToolkit (MCP integration for LSP + Tree-sitter)
  - ACP callbacks to GUI: retrieval_progress, context_available

Layer 2: Deterministic Execution Plan Assembly (Config-Based)

After Orchestrator decides stages and retrieval strategy, assemble plan with filtered files reference:

text
Execution Plan Assembly Process:

Input:
  - selected_workflow: "feature_with_iterative_testing"
  - llm_stage_decisions: {1: INCLUDE, 2: INCLUDE, 3: INCLUDE, 4: INCLUDE}
  - retrieval_strategy_config: {...from workflow YAML...}
  - NO retrieval_queries (generated by Retrieval Agent)

Process (deterministic function, no LLM):

For each stage in workflow YAML:
  IF stage.required == true:
    ADD to planned_stages
  ELSE IF llm_stage_decision[stage_id] == INCLUDE:
    ADD to planned_stages
  ELSE:
    ADD to skipped_stages

Build routing_table (becomes graph edges):
  FOR each stage in planned_stages:
    routing_table[stage_id] = {
      next_on_success: stage.routing.next_stage_on_success,
      next_on_failure: stage.routing.next_stage_on_failure,
      max_attempts: stage.routing.max_attempts,
      parallel_agents: stage.parallel_agents,
      failure_aggregation: stage.parallel_config.failure_aggregation
    }

Build task_context for Retrieval Agent:
  FOR each stage in planned_stages:
    task_context[stage_id] = {
      stage_name: stage.name,
      stage_description: stage.description,
      stage_type: stage.type (code_generation, test, security, etc.)
    }

Return execution_plan (becomes LangGraph structure):
  Includes: workflow_type, retrieval_strategy_config, routing_table, task_context, filtered_files (after Phase 1)

LangChain Integration (Layer 2):

text
Components:
  - langchain_core.graph.StateGraph (graph structure definition)
  - Custom execution state schema (Pydantic BaseModel)
  - langchain.schema.Document (execution plan structure)
  - ACP callbacks: execution_plan_ready

Layer 2.5: LangGraph Execution Graph (Deterministic Routing with State Machine)

Execution workflow modeled as state machine with workflow-aware context and filtered file awareness:

text
Graph Architecture:

State Schema:
  - current_stage: int
  - stage_results: {stage_id: {failure, attempt, output, files_changed}}
  - enrichment_attempts: {stage_id: count}
  - enriched_context: {stage_id: context}
  - routing_table: {...from execution plan...}
  - workflow_type: "code_domain" | "document_domain" | other

  # NEW: Selective retrieval state
  - filtered_files: {stage_id: [list of files from Phase 1]}
  - parsed_ast: {stage_id: {function_data, class_data}}
  - function_context_map: {function_id: {signature, file, type_info}}

  - mcp_tools_available: {lsp: true/false, tree_sitter: true/false}
  - iterations: []
  - retrieval_context: {stage_id: context}

Nodes (Execution Units):
  1. node_stage_1_[stage_name]
  2. node_stage_2_[stage_name]
  ... (for each planned stage)
  n. node_adaptive_retrieval (reusable, workflow-aware, selective)
  n+1. node_workflow_done
  n+2. node_workflow_abort

Conditional Edges (Deterministic Routing, Workflow-Aware, Selective):

  After each stage execution:
    edge_stage_X_router:
      Evaluates: execution_state.stage_results[X].failure + routing_table[X]

      Condition 1: IF failure == false
        → Route to: routing_table[X].next_on_success

      Condition 2: IF failure == true AND enrichment_attempts[X] < 2 AND retrieval_config.allows_enrichment
        → Route to: node_adaptive_retrieval
           Set context: {
             retry_stage: X,
             workflow_type,
             retrieval_config,
             filtered_files: execution_state.filtered_files[X],
             parsed_ast: execution_state.parsed_ast[X]
           }

      Condition 3: IF failure == true AND enrichment_attempts[X] >= 2
        → Route to: routing_table[X].next_on_failure (or ABORT)

  After adaptive_retrieval:
    edge_adaptive_retrieval_router:
      → Route to: execution_state.retry_stage
      → Increment: execution_state.enrichment_attempts[retry_stage]
      → Pass: enriched_context to retry stage

Graph Construction:
  StateGraph(
    name="agentic_ide_workflow",
    state_schema=ExecutionState
  )

  Add nodes: all stage nodes + adaptive_retrieval + terminals
  Add conditional edges with routing logic (from routing_table)
  Set entry point: first planned stage
  Set end points: done, abort
  Compile graph

  Run with state = ExecutionState(
    filtered_files: {...from Phase 1...},
    parsed_ast: {...from Phase 2...},
    ...
  )

LangChain Integration (Layer 2.5):

text
Components:
  - langchain_core.graph.StateGraph (state machine with selective retrieval state)
  - langchain_core.runnables.RunnableBranch (conditional edge logic)
  - Pydantic BaseModel (execution state schema with filtered_files, parsed_ast)
  - langchain_core.runnables.RunnableGraph (compiled executable)
  - ACP callbacks: node_executing, edge_routing, stage_complete

Layer 3: Context Fusion Service (Learned Ranking + Algorithm)

Intelligent context merging combining cross-encoder reranking with workflow-aware deduplication:

text
Context Fusion Service Architecture:

Component 1: Cross-Encoder Reranker (Workflow-Aware)

  Model: cross-encoder/ms-marco-MiniLM-L12-v2 (33M params)
  VRAM: <500MB
  Input: (query, context_chunk) pairs
  Output: Relevance score [0, 1]

  Workflow-aware scoring:
    Code workflows: Prioritize code-specific relevance (type match, signature compatibility)
    Document workflows: Prioritize section/decision relevance

Component 2: Workflow-Specific Deduplication

  Exact Deduplication:
    ├─ String matching across all chunks
    ├─ Remove identical content
    └─ Time: <50ms

  Semantic Deduplication (Workflow-Aware):
    ├─ For code: Compare function signatures + implementations
    ├─ For docs: Compare section summaries + topics
    ├─ Use cosine similarity > 0.95
    └─ Time: <100ms for selective set

Component 3: Token Budget Management

  Budget enforcement:
    Retrieve from: retrieval_config.retrieval_hints.token_budget
    Apply: Per-stage token limits

Component 4: Workflow-Specific Attribution

  For code workflows:
    ├─ Tag: function_id, file_path, line_number, ast_type
    ├─ Preserve: Function signatures, type info, LSP-queryable references
    └─ Include: Filtered file context

  For document workflows:
    ├─ Tag: section_id, document, section_path
    ├─ Preserve: Document structure, hierarchy
    └─ Include: Decision references

LangChain Integration (Layer 3):

text
Components:
  - langchain.retrievers.ContextualCompressionRetriever
  - langchain.retrievers.DocumentCompressor
  - sentence_transformers.CrossEncoder
  - langchain.schema.Document (with workflow-specific metadata)

Layer 4: Validation Layer (Self-Correcting RAG)

Validates context before injection, workflow-aware:

text
Validation Layer (Unchanged):

1. Grounding Check:
   For code: Is code snippet from actual codebase + in parsed files?
   For docs: Is section from actual document?

2. Consistency Check:
   For code: Does code contradict previous iterations?
   For docs: Does information conflict with decisions?

3. Relevance Check:
   Use cross-encoder scores (already computed)
   Workflow-specific thresholds

LangChain Integration (Layer 4):

text
Components:
  - langchain.evaluation.qa.QAEvalChain
  - Custom workflow-aware validation logic

Layer 5: Stage Execution within LangGraph (Workflow-Aware, With MCP Tools)

Stages execute as graph nodes with workflow-specific context and MCP tools:

text
LangGraph Execution Flow (Workflow-Aware, Code Example):

Stage Execution for Code Workflows:

  Stage Node receives:
    {
      task: string,
      retrieval_context: {function signatures, code snippets from filtered files},
      filtered_files: [...files from Phase 1...],
      parsed_ast: {functions from those files},
      function_context_map: {function_id: {signature, type_info}},
      enriched_context: {...if adaptive...},
      mcp_tools: {lsp_get_signature, lsp_find_definition, ...}
    }

  CodeAgent executes:
    1. Reads task + retrieval context (selective, from filtered files)
    2. Can call MCP tools on-demand:
       - lsp.get_signature(function_name): Get precise type signature
       - lsp.find_definition(symbol): Find where symbol defined
       - lsp.get_references(symbol): Find usages
       - tree_sitter.get_ast_node(file, line): Get AST structure
    3. References: function_context_map for quick lookups
    4. Uses enriched context if retry
    5. Generates code
    6. Returns: {failure: bool, output: code}

Stage Execution for Non-Code Workflows:

  Stage Node receives:
    {
      task: string,
      retrieval_context: {document sections from filtered files},
      filtered_files: [...documents...],
      enriched_context: {...if adaptive...},
      mcp_tools: {} # Empty
    }

  AnalysisAgent executes:
    1. Reads task + retrieval context
    2. No MCP tools
    3. Analyzes document context directly
    4. Generates analysis
    5. Returns: {failure: bool, output: analysis}

Conditional Routing (Same for Both):

  After stage completion:
    Edge evaluation checks state, routes accordingly
    Adaptive retrieval reuses filtered_files, parsed_ast for efficiency

GUI Updates (Real-Time via ACP):

  Stage Node Execution:
    Send to GUI: node_executing event with:
      - Stage name, description
      - Current agent executing
      - Retrieval context summary (token count, sources)
      - MCP tools available (if code workflow)

  After Completion:
    Send to GUI: stage_complete event with:
      - Result (success/failure)
      - Generated output (code preview)
      - Files changed
      - Iteration number

  On Failure:
    Send to GUI: failure_detected event with:
      - Stage ID, failure reason
      - Will trigger adaptive retrieval: true/false

  On Adaptive Retrieval:
    Send to GUI: adaptive_retrieval_triggered event with:
      - Previous failure context
      - New queries being generated
      - Estimated enrichment time

  Ready for Review:
    Send to GUI: diffs_ready event with:
      - All file changes batched
      - Per-stage annotations
      - Iteration summary

LangChain Integration (Layer 5):

text
Components:
  - langchain_core.graph.StateGraph (execution graph with selective state)
  - langchain_core.runnables.RunnableBranch (conditional edges)
  - langchain.agents.AgentExecutor (stage agents)
  - langchain.tools.Tool (file operations, terminal, retrieval)
  - langchain.mcp.MCPToolkit (LSP + Tree-sitter via MCP)
  - langchain.memory.ConversationBufferMemory (iteration tracking)
  - langchain_core.runnables.RunnableGraph (compiled execution)
  - ACP streaming callbacks: real-time updates to GUI

Messaging Schemas (Updated for Selective Two-Phase Retrieval)
Orchestrator Output with Retrieval Strategy

json
{
  "type": "workflow_and_stages_selection_with_strategy",
  "correlationId": "string",

  "selected_workflow": "feature_with_iterative_testing",
  "workflow_type": "code_implementation",

  "stage_inclusion_decisions": {
    "1": "INCLUDE (required)",
    "2": "INCLUDE (required)",
    "3": "INCLUDE (LLM reasoned)",
    "4": "INCLUDE (LLM reasoned)"
  },

  "retrieval_strategy": "code_domain_selective_ast",

  "retrieval_strategy_config": {
    "file_level_search": {
      "enabled": true,
      "vector_db": "qdrant",
      "collection": "workspace_files",
      "top_k": 50,
      "time_target_ms": 150
    },
    "selective_ast_parsing": {
      "enabled": true,
      "model": "tree_sitter",
      "trigger": "after_file_level_search",
      "parse_only": "filtered_files_from_search"
    },
    "context_sources": [
      {source: "codebase_semantic_search", strategy: "file_then_function", priority: "HIGH"},
      {source: "lsp_tools", strategy: "on_demand", priority: "HIGH"}
    ],
    "token_budget": {1: 30000, 2: 25000, 3: 20000, 4: 10000}
  },

  "tart_pattern_applied": true,
  "two_phase_selective_retrieval": true,
  "vector_db_used": "qdrant_workspace_files_collection"
}

Workspace Initialization Complete

json
{
  "type": "workspace_initialization_complete",
  "correlationId": "string",
  "timestamp": "ISO8601",

  "workspace": {
    "id": "workspace_123",
    "path": "/home/user/project",
    "files_discovered": 10240,
    "languages": ["python", "javascript"]
  },

  "file_level_indexing": {
    "status": "completed",
    "files_indexed": 10240,
    "documents_created": 10240,
    "collection": "workspace_files",
    "embedding_model": "nomic-embed-text",
    "time_ms": 1850,
    "qdrant_documents_inserted": 10240
  },

  "retrieval_readiness": {
    "file_level_search": "ready",
    "file_level_collection": "workspace_files",
    "function_level_collection": "workspace_functions (empty, populated per-task)",
    "ready_for_file_filtering": true
  }
}

Autonomous Retrieval Agent Response (Two-Phase, Code Workflow)

json
{
  "type": "autonomous_retrieval_completed",
  "correlationId": "string",
  "workflow_type": "code_domain",
  "mode": "upfront",
  "retrieval_pattern": "two_phase_selective",

  "phase_1_file_level_search": {
    "status": "completed",
    "qdrant_collection": "workspace_files",
    "queries_executed": 3,
    "time_ms": 145,

    "results_per_stage": {
      "1": {
        "files_filtered": 50,
        "files": ["auth.py", "token_handler.py", "jwt_utils.py", "..."]
      },
      "2": {
        "files_filtered": 40,
        "files": ["test_auth.py", "test_token.py", "..."]
      },
      "3": {
        "files_filtered": 30,
        "files": ["security_validator.py", "..."]
      }
    }
  },

  "phase_2_selective_ast_parsing": {
    "status": "completed",
    "total_files_parsed": 120,
    "total_functions_extracted": 487,
    "time_ms": 2100,

    "per_stage": {
      "1": {files: 50, functions: 180},
      "2": {files: 40, functions: 150},
      "3": {files: 30, functions: 157}
    }
  },

  "phase_3_function_level_indexing": {
    "status": "completed",
    "qdrant_collection": "workspace_functions",
    "documents_created": 487,
    "documents_inserted": 487,
    "time_ms": 250
  },

  "phase_4_function_level_search": {
    "status": "completed",
    "qdrant_collection": "workspace_functions",
    "queries_executed": 3,
    "time_ms": 120,

    "results_per_stage": {
      "1": {functions_retrieved: 12, avg_score: 0.89},
      "2": {functions_retrieved: 10, avg_score: 0.87},
      "3": {functions_retrieved: 8, avg_score: 0.91}
    }
  },

  "phase_5_web_and_docs": {
    "status": "completed",
    "time_ms": 300,
    "sources": ["web_search", "doc_retrieval"]
  },

  "total_upfront_time_ms": 2915,
  "optimization_vs_all_files_ast": "66% faster (3s vs 11s)",

  "retrieval_results": {
    "1": {
      "strategy_applied": "file_level_filter (50 files) -> function_level_search",
      "sources": ["codebase_filtered_ast", "web_search", "docs"],
      "functions_retrieved": 12,
      "context_summary": "JWT auth patterns (function-level)",
      "token_count": 30000
    }
  },

  "execution_state_populated": {
    "filtered_files": "populated per stage",
    "parsed_ast": "populated per stage",
    "function_context_map": "ready for agent reference"
  },

  "mcp_tools_prepared": {
    "lsp": ["get_signature", "find_definition", "get_references"],
    "tree_sitter": ["get_ast_node"]
  }
}

LangGraph Execution Progress (With Filtered File Context)

json
{
  "type": "langgraph_execution_progress",
  "correlationId": "string",
  "workflow_type": "code_domain",

  "current_node": "node_stage_1_code_generation",
  "execution_context": {
    "retrieval_context_available": true,
    "filtered_files_available": true,
    "parsed_ast_available": true,
    "function_context_map_available": true,
    "mcp_tools_available": ["lsp", "tree_sitter"],
    "token_budget_remaining": 5000,
    "selective_retrieval_used": true,
    "files_in_context": 50
  },

  "stage_result": {
    "stage_id": 1,
    "failure": false,
    "tools_used_during_execution": ["lsp_get_signature", "lsp_find_definition"],
    "output_tokens": 2000,
    "referenced_files": 5,
    "referenced_functions": 8
  },

  "gui_update": {
    "display": "CodeAgent: Implementing JWT auth",
    "status": "executing_with_mcp_tools",
    "files_filtered": 50,
    "functions_available": 180,
    "context_source": "selective_retrieval (not all-files)",
    "progress_bar": "stage 1/4"
  }
}

Diff Ready for GUI Review

json
{
  "type": "diffs_ready_for_review",
  "correlationId": "string",
  "workflow": "feature_with_iterative_testing",
  "total_iterations": 2,

  "batched_diffs": [
    {
      "iteration": 1,
      "stage": 1,
      "agent": "code_agent",
      "files_changed": 2,
      "file_diffs": [
        {
          "file": "src/auth/auth.py",
          "action": "create",
          "diff": "...",
          "language": "python",
          "retrieved_from_stage": 1,
          "confidence": 0.92
        }
      ]
    },
    {
      "iteration": 2,
      "stage": 1,
      "agent": "code_agent",
      "files_changed": 1,
      "file_diffs": [
        {
          "file": "src/auth/auth.py",
          "action": "modify",
          "diff": "...",
          "change_reason": "adaptive_retrieval - test failure enrichment",
          "confidence": 0.88
        }
      ]
    }
  ],

  "gui_action_required": "batch_diff_review",
  "user_options": [
    "accept_all_changes",
    "accept_per_file",
    "accept_per_stage",
    "provide_feedback_for_refinement"
  ]
}

Configuration Schemas (Updated for Selective Two-Phase Retrieval)
Orchestrator Configuration

text
# orchestrator_config.yaml
orchestrator:
  agent_profile: "agent_profiles/orchestrator.yaml"

  planning_phase:
    workflow_selection:
      model: "claude-3-5-sonnet"
      temperature: 0.2
      reasoning_scope: "workflow_selection_and_stage_inclusion"
      estimated_time_ms: 200

    stage_inclusion:
      enabled: true
      reasoning_based_on: "reasoning_guidance_in_workflow_yaml"
      no_retrieval_query_generation: true

  retrieval_strategy_configuration:
    enabled: true
    source: "workflow_yaml_retrieval_strategy_section"
    pattern: "TART (Task-Aware Retrieval with Instructions)"
    passes_to_agent: "explicit_instructions_not_implicit_classification"

  execution_framework: "langgraph"
  execution_routing: "deterministic_conditional_edges"

  langchain_integration:
    enabled: true
    agent_framework: "langchain"
    workflow_framework: "langgraph"

Autonomous Retrieval Agent Configuration (Updated Two-Phase)

text
# retrieval_agent_config.yaml
autonomous_retrieval_agent:
  agent_type: "workflow_aware_two_phase_selective_retrieval"
  autonomy: "full"

  strategy_selection:
    method: "configuration_driven"
    source: "workflow_retrieval_strategy_config"
    pattern: "TART"
    no_self_classification: true

  reasoning_model:
    model: "mistral-7b-instruct"
    quantization: "q4"
    vram_gb: 3.8
    inference_time_ms_target: 500
    temperature: 0.3
    foss_model: true

  code_workflow_specialization:
    enabled: true

    phase_1_file_level_search:
      enabled: true
      vector_db: "qdrant"
      collection: "workspace_files"
      timing: "upfront_per_workspace"
      data_source: "pre_computed_file_embeddings"
      execution: "per_task_query"
      top_k: 50
      time_target_ms: 150

    phase_2_selective_ast_parsing:
      enabled: true
      tool: "tree_sitter"
      trigger: "after_phase_1_file_filtering"
      parse_only: "filtered_files_from_phase_1"
      time_target_ms: "2000-3000 for 50-100 files"

    phase_3_function_level_indexing:
      enabled: true
      vector_db: "qdrant"
      collection: "workspace_functions"
      documents_created_from: "selectively_parsed_ast"
      time_target_ms: "200-300"

    phase_4_function_level_search:
      enabled: true
      vector_db: "qdrant"
      collection: "workspace_functions"
      filters: ["metadata.type == function", "metadata.file in phase_1_filtered_files"]
      execution: "per_task_query"
      top_k: 10
      time_target_ms: 150

    lsp_integration:
      enabled: true
      protocol: "Language Server Protocol"
      integration: "MCP (Model Context Protocol)"
      execution: "on_demand_during_agent_execution"
      tools: ["get_signature", "find_definition", "get_references", "get_type"]

    rag_strategy:
      chunk_strategy: "semantic_functions_from_filtered_files"
      sources:
        - codebase_semantic_search (filtered_file_level_then_function_level)
        - lsp_tools (on_demand)
        - web_search (libraries_patterns)
        - doc_retrieval (framework_docs)
        - cve_database (security_stage)

    timing_optimization:
      savings_vs_all_files_ast: "66% faster"
      time_reduction_seconds: "7-8"
      typical_sequence: "3s (Phase 1-4) vs 11s (all-AST)"

  non_code_workflow_specialization:
    enabled: true

    file_level_search:
      enabled: true
      vector_db: "qdrant"
      collection: "workspace_files"
      time_target_ms: 150

    selective_ast_parsing:
      enabled: false
      reason: "not_applicable"

    rag_strategy:
      chunk_strategy: "document_sections_from_filtered_files"
      sources:
        - document_semantic_search (section_level)
        - specification_search
        - decision_log_search
        - web_search (current_standards)

  adaptive_mode:
    enabled: true
    trigger: "langgraph_conditional_edge_on_failure"
    strategy: "workflow_aware_failure_analysis_selective"
    reuse_filtered_files: true
    reuse_parsed_ast: true
    max_adaptive_cycles: 2

  retrieval_execution:
    parallel_enabled: true
    max_parallel_tasks: 5
    timeout_per_source_ms: 3000

    vector_db_config:
      provider: "qdrant"
      collections:
        file_level:
          name: "workspace_files"
          document_type: "file"
          populated_at: "workspace_initialization"
          reused_for: "all_file_level_searches"

        function_level:
          name: "workspace_functions"
          document_type: "function"
          populated_at: "per_task_after_selective_ast"
          filtered_to: "filtered_files_from_phase_1"

    embedding_model: "nomic-embed-text"

    sources_config:
      codebase_semantic_search:
        provider: "qdrant"
        two_phase_approach: true
        phase_1_collection: "workspace_files"
        phase_2_collection: "workspace_functions"
        phase_2_filtering: "file_membership"
        workspace_scoping: true

      web_search:
        provider: "duckduckgo"
        caching: true
        rate_limit_qpm: 30

      lsp:
        provider: "MCP (Model Context Protocol)"
        execution_timing: "on_demand"
        tools_per_workflow: "from_workflow_config"

      cve_database:
        provider: "nvd_api"
        local_indexing: true
        update_frequency: "daily"

LangGraph Execution Configuration (Updated With Selective State)

text
# langgraph_execution_config.yaml
langgraph:
  workflow_name: "agentic_ide_execution"
  workflow_aware: true
  selective_retrieval_aware: true

  state_management:
    schema: "ExecutionState"
    persistence: "enabled"

    state_fields:
      workflow_type:
        type: "string"
        values: ["code_domain", "document_domain", "other"]
        determines: "behavior_of_all_agents_and_edges"

      # NEW: Selective retrieval state
      filtered_files:
        type: "dict"
        keys: [stage_id]
        values: "list[file_paths]"
        populated_by: "phase_1_file_level_search"
        usage: "filter_ast_parsing, constraint_function_search"

      parsed_ast:
        type: "dict"
        keys: [stage_id]
        values: "{function_data: [...], class_data: [...]}"
        populated_by: "phase_2_selective_ast_parsing"
        scoped_to: "filtered_files[stage_id]"
        availability: "to_all_agents_for_reference"

      function_context_map:
        type: "dict"
        keys: [function_id]
        values: "{signature, file, type_info, dependencies}"
        populated_by: "phase_3_function_level_indexing"
        usage: "quick_lookups, LSP_query_targets"

      mcp_tools_available:
        type: "dict"
        keys: ["lsp", "tree_sitter"]
        values_per_workflow: "from_retrieval_strategy_config"

  nodes:
    stage_nodes:
      execution_context: "workflow_aware_selective"
      receive_context: "{task, retrieval_context, filtered_files, parsed_ast, function_context_map, mcp_tools}"
      tools_available: "based_on_workflow_type_and_config"

    adaptive_retrieval_node:
      workflow_aware: true
      selective_aware: true
      reuses: "filtered_files, parsed_ast_from_execution_state"
      applies_strategy: "from_retrieval_strategy_config"

  conditional_edges:
    routing_logic: "deterministic"
    uses: "routing_table + execution_state"
    workflow_awareness: "in_failure_analysis_for_enrichment"
    selective_awareness: "reuse_filtered_files_for_adaptive"

  callbacks:
    handlers:
      - type: "ACP_StreamingCallbackHandler"
        streams_to: "GUI_client"
        events:
          - "node_executing"
          - "edge_routing"
          - "stage_complete"
          - "retrieval_progress"
          - "context_available"
          - "diffs_ready"
          - "user_feedback_received"

  langchain_integration:
    core_modules:
      - "langchain_core.graph.StateGraph"
      - "langchain_core.runnables.RunnableBranch"
      - "langchain_core.runnables.RunnableGraph"
      - "Pydantic BaseModel (ExecutionState with selective retrieval fields)"

    vector_db_modules:
      - "langchain.vectorstores.Qdrant"
      - "qdrant collections: workspace_files, workspace_functions"

    mcp_modules:
      - "langchain.mcp.MCPToolkit"
      - "LSP_Server, Tree_Sitter_Server (external)"

    acp_streaming:
      - "langchain_core.rpc.acp (Agent Client Protocol)"
      - "Callbacks: on_node_start, on_node_end, on_chat_model_stream"

Workflow Definition (Updated with Selective Retrieval Strategy)

text
# workflows/feature_with_iterative_testing.yaml
metadata:
  name: "feature_with_iterative_testing"
  description: "Implement feature with test-driven refinement loop"
  version: "1.0"
  workflow_type: "code_implementation"

  selection_criteria:
    applicable_patterns: ["implement.*feature", "add.*functionality"]
    agents_required: ["code_agent", "test_agent"]
    agents_optional: ["security_agent", "formatter_agent"]

retrieval_strategy_config:
  enabled: true
  strategy_name: "code_domain_selective_ast"
  pattern_applied: "TART (Task-Aware Retrieval with Instructions)"

  file_level_search:
    enabled: true
    vector_db: "qdrant"
    collection: "workspace_files"
    top_k: 50
    time_target_ms: 150

  selective_ast_parsing:
    enabled: true
    model: "tree_sitter"
    trigger: "after_file_level_search"
    parse_only: "filtered_files_from_search"

  function_level_indexing:
    enabled: true
    vector_db: "qdrant"
    collection: "workspace_functions"
    documents_from: "selectively_parsed_ast_only"

  lsp_integration:
    enabled: true
    execution: "on_demand"
    tools:
      - get_signature
      - find_definition
      - get_references

  rag_strategy:
    chunk_strategy: "semantic_functions_from_filtered_files"
    sources:
      - name: "codebase_semantic_search"
        phases: ["phase_1_file_filtering", "phase_4_function_search"]
        vector_db_collections: ["workspace_files", "workspace_functions"]
        priority: "HIGH"
      - name: "lsp_tools"
        execution_timing: "on_demand"
        priority: "HIGH"
      - name: "web_search"
        priority: "MEDIUM"
      - name: "doc_retrieval"
        priority: "MEDIUM"
      - name: "cve_database"
        trigger_stages: ["security_review"]
        priority: "HIGH_if_triggered"

  retrieval_hints:
    focus_on: ["existing_patterns", "dependencies", "type_signatures"]
    avoid: ["test_code", "deprecated_patterns"]
    token_budget:
      code_generation: 30000
      test_generation: 25000
      security_review: 20000
      lint_and_format: 10000

stages:
  - stage_id: 1
    name: "code_generation"
    required: true

    parallel_agents:
      - agent: "code_agent"
        mcp_tools: ["lsp_get_signature", "lsp_find_definition", "tree_sitter_get_ast"]
        receives_context: "retrieval_context (filtered), parsed_ast (stage 1), function_context_map"

    retrieval_guidance: |
      This stage generates implementation code.

      Retrieval strategy: code_domain_selective_ast (two-phase)

      Phase 1: File-level search (50 files filtered from 10k)
      Phase 2: Selective AST parsing (only those 50 files)
      Phase 3: Function-level indexing (only from those files)
      Phase 4: Function-level search

      Context priorities (from retrieval_strategy_config):
      - HIGH: Existing code patterns (function-level from filtered files)
      - HIGH: On-demand LSP queries during generation
      - MEDIUM: Latest best practices (web)
      - MEDIUM: Framework guides (docs)

      Agent can call MCP tools:
        - lsp.get_signature(function): Get exact parameter types
        - lsp.find_definition(symbol): Find where symbol is defined
        - tree_sitter.get_ast_node(file, line): Get code structure

      Context scope: filtered_files[1] ≈ 50 files (not 10k)

    routing:
      next_stage_on_success: 2
      next_stage_on_failure: "ABORT"
      max_attempts: 1

    failure_criteria:
      agent_defined: true

  - stage_id: 2
    name: "test_generation_and_execution"
    required: true

    parallel_agents:
      - agent: "test_agent"
        mcp_tools: ["lsp_get_references"]
        receives_context: "retrieval_context (filtered for tests), parsed_ast (stage 2)"

    retrieval_guidance: |
      This stage generates and runs tests.

      Retrieval strategy: code_domain_selective_ast

      Context priorities:
      - HIGH: Existing test functions (from filtered AST, stage 2)
      - MEDIUM: Web search for test patterns

      Can use MCP tools:
        - lsp.get_references(function): Find all usages of function to test

      Context scope: filtered_files[2] ≈ 40 files (test-relevant)

    routing:
      next_stage_on_success: 3
      next_stage_on_failure: 1
      max_attempts: 3

    failure_criteria:
      agent_defined: true

  - stage_id: 3
    name: "security_review"
    required: false

    parallel_agents:
      - agent: "security_agent"

    reasoning_guidance: |
      Include if: Code involves auth, authorization, payment, sensitive data
      OR project is security-sensitive

    retrieval_guidance: |
      This stage performs security audit.

      Retrieval strategy: code_domain_selective_ast + CVE database

      Context priorities:
      - HIGH: Known vulnerabilities (CVE database)
      - HIGH: Security standards (OWASP, RFC)
      - MEDIUM: Security best practices

      Context scope: filtered_files[3] ≈ 30 files (security-relevant)

    routing:
      next_stage_on_success: 4
      next_stage_on_failure: 1
      max_attempts: 1

    failure_criteria:
      agent_defined: true

  - stage_id: 4
    name: "lint_and_format"
    required: false

    parallel_agents:
      - agent: "code_agent"
      - agent: "formatter_agent"

    reasoning_guidance: |
      Include if production-ready code.

    retrieval_guidance: |
      This stage ensures code quality.

      Retrieval strategy: lightweight (no AST, no LSP)

      Context priorities:
      - MEDIUM: Style guides (docs)
      - LOW: Framework conventions

    routing:
      next_stage_on_success: "DONE"
      next_stage_on_failure: "DONE"
      max_attempts: 1

---

# workflows/architecture_discussion.yaml
metadata:
  name: "architecture_discussion"
  description: "Discuss and plan architectural decisions"
  version: "1.0"
  workflow_type: "text_analysis"

  selection_criteria:
    applicable_patterns: ["discuss.*architecture", "plan.*design", "evaluate.*options"]
    agents_required: ["analysis_agent"]
    agents_optional: ["documentation_agent"]

retrieval_strategy_config:
  enabled: true
  strategy_name: "document_domain_file_filtered"
  pattern_applied: "TART"

  file_level_search:
    enabled: true
    vector_db: "qdrant"
    collection: "workspace_files"
    top_k: 30
    time_target_ms: 150

  selective_ast_parsing:
    enabled: false
    reason: "non_code_workflow"

  lsp_integration:
    enabled: false
    reason: "not_applicable"

  rag_strategy:
    chunk_strategy: "document_sections_from_filtered_files"
    sources:
      - name: "document_semantic_search"
        vector_db: "qdrant"
        collection: "workspace_files"
        indexing: "section_level"
        priority: "HIGH"
      - name: "decision_log_search"
        priority: "HIGH"
      - name: "specification_search"
        priority: "MEDIUM"
      - name: "web_search"
        priority: "MEDIUM"

  retrieval_hints:
    focus_on: ["existing_decisions", "rationale", "architectural_implications"]
    avoid: ["implementation_details"]
    token_budget:
      planning: 20000
      analysis: 15000

stages:
  - stage_id: 1
    name: "architectural_analysis"
    required: true

    parallel_agents:
      - agent: "analysis_agent"
        mcp_tools: []

    retrieval_guidance: |
      This stage analyzes architectural decisions.

      Retrieval strategy: document_domain_file_filtered

      File filtering (Phase 1): ~30 documents from Qdrant
      No AST parsing (non-code)

      Context: Previous decisions, specifications, options
      No MCP tools (non-code workflow)

    routing:
      next_stage_on_success: 2
      next_stage_on_failure: "ABORT"
      max_attempts: 1

  - stage_id: 2
    name: "decision_documentation"
    required: false

    parallel_agents:
      - agent: "documentation_agent"

    routing:
      next_stage_on_success: "DONE"
      next_stage_on_failure: "DONE"
      max_attempts: 1

Complete Workflow Execution Flow: Two-Phase Selective Retrieval with GUI Integration
Code Workflow Example

text
USER QUERY (from GUI): "Implement JWT authentication with comprehensive tests"

    ↓
GUI sends query via ACP to backend
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0: PLANNING (Orchestrator - Workflow Selection)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestrator LLM (200ms):
  Selects: feature_with_iterative_testing workflow
  Decides stages: [1, 2, 3, 4] all included

Loads workflow YAML → Extracts retrieval_strategy_config:
  {
    strategy_name: "code_domain_selective_ast",
    file_level_search: enabled,
    selective_ast_parsing: enabled,
    ...
  }

Passes to Retrieval Agent:
  {
    user_task: "Implement JWT auth with tests",
    workflow_type: "code_implementation",
    retrieval_config: {...}
  }

GUI receives: execution_plan_ready event
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: TWO-PHASE SELECTIVE RETRIEVAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Retrieval Agent reads config:
  "file_level_search: enabled" → Activates Phase 1
  "selective_ast_parsing: enabled" → Activates Phase 2
  "lsp_integration: enabled" → Prepares LSP tools

    ↓
PHASE 1A: File-Level Semantic Search (150ms)

Query Qdrant Collection "workspace_files" (PRE-COMPUTED):
  Queries:
    - "JWT authentication implementation" (stage 1)
    - "JWT test utilities" (stage 2)
    - "JWT security validation" (stage 3)

  Results:
    Stage 1: [auth.py, token_handler.py, jwt_utils.py, ...] (50 files)
    Stage 2: [test_auth.py, test_token.py, ...] (40 files)
    Stage 3: [security_validator.py, ...] (30 files)

  Time: ~150ms (reuses pre-computed file embeddings from workspace init)

  Store: execution_state.filtered_files = {...}

    ↓
PHASE 1B: Selective AST Parsing (2-3 seconds)

Tree-sitter parses ONLY filtered files:
  Stage 1: Parse 50 files → Extract 180 functions
  Stage 2: Parse 40 files → Extract 150 functions
  Stage 3: Parse 30 files → Extract 157 functions

  Time: ~2-3s (in parallel, not sequential)

  Store: execution_state.parsed_ast = {...}

    ↓
PHASE 1C: Function-Level Embedding & Indexing (250ms)

Generate embeddings for only parsed functions (487 total, not 5,847):
  Create function documents
  Generate embeddings with nomic-embed-text
  Store in Qdrant Collection "workspace_functions"

  Time: ~250ms

  Store: execution_state.function_context_map = {...}

    ↓
PHASE 1D: Function-Level Query Execution (150ms)

Query Qdrant Collection "workspace_functions" (JUST INDEXED):
  Queries (per stage):
    - "JWT authentication functions" (stage 1)
    - "JWT test functions" (stage 2)
    - "JWT security functions" (stage 3)

  Results:
    Stage 1: [authenticate(), validate_token(), sign_token()] with signatures
    Stage 2: [test_auth(), test_validation()]
    Stage 3: [security_check()]

  Time: ~150ms

    ↓
PHASE 1E: Web Search & Documentation (Parallel, 300ms)

  Web search: "Python JWT best practices 2025" (300ms)
  Doc retrieval: "Flask JWT integration" (200ms)
  CVE search: "JWT vulnerabilities" (200ms)

  Max: ~300ms

    ↓
PHASE 1F: Result Aggregation & Compression

For each stage:
  Combine: Function results + web + docs
  Compress: To token budget (30k, 25k, 20k)
  Attribute: Sources

  Store: execution_state.retrieval_context = {...}

Total Upfront Time: ~150ms + 2-3s + 250ms + 150ms + 300ms = 2.85-3.85 seconds
Savings vs All-Files AST: 66% faster (3.5s vs 11s)

GUI receives: retrieval_complete event
  - "File filtering: 50, 40, 30 files"
  - "AST parsing: 487 functions"
  - "Context ready: 30k, 25k, 20k tokens"
  - "Estimated execution time: 5-10 minutes"

    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: LANGGRAPH EXECUTION (Deterministic, Selective)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LangGraph initialized with:
  execution_state.workflow_type = "code_domain"
  execution_state.filtered_files = {...}
  execution_state.parsed_ast = {...}
  execution_state.function_context_map = {...}
  execution_state.mcp_tools_available = {lsp: true}
  execution_state.retrieval_context = {...}

    ↓
Stage 1 Node: code_generation

  CodeAgent receives:
    {
      task: "Implement JWT auth",
      retrieval_context[1]: 30k tokens (from filtered files),
      filtered_files[1]: 50 files,
      parsed_ast[1]: 180 functions,
      function_context_map: {function_id: {signature, file, type_info}},
      mcp_tools: {lsp_get_signature, lsp_find_definition, ...}
    }

  CodeAgent executes:
    1. Reads retrieval context (selective, not generic)
    2. Analyzes function_context_map for available functions
    3. Calls MCP LSP tool: lsp.get_signature("authenticate")
       → Returns: "def authenticate(token: str) -> Dict[str, Any]"
    4. Calls MCP LSP tool: lsp.find_definition("TokenPayload")
       → Returns: "class TokenPayload in jwt_models.py"
    5. References parsed_ast for structure
    6. Generates code with precise type info + existing patterns
    7. Returns: {failure: false, files_changed: 1}

  Conditional edge evaluation:
    failure == false → Route to: node_stage_2

  GUI receives: stage_complete event
    - Stage: "code_generation"
    - Result: success
    - Files changed: 1
    - Generated code: "...jwt auth implementation..."
    - MCP tools used: 2 (lsp_get_signature, lsp_find_definition)

    ↓
Stage 2 Node: test_generation

  TestAgent receives same context structure
  Executes tests
  Returns: {failure: true, failed_tests: 3}

  GUI receives: failure_detected event
    - Stage: "test_generation"
    - Reason: "3 assertions failed"
    - Will trigger adaptive retrieval: yes

  Conditional edge evaluation:
    failure == true AND enrichment_attempts < 2
    → Route to: node_adaptive_retrieval (with selective context)

    ↓
Adaptive Retrieval Node (REUSES Filtered Files & Parsed AST)

  Receives:
    {
      failure_context: {failed_tests, error_logs},
      retry_stage: 1,
      workflow_type: "code_domain",
      filtered_files[1]: 50 files (REUSED),
      parsed_ast[1]: 180 functions (REUSED)
    }

  Retrieval Agent (adaptive mode, selective):
    Skip: Phase 1 (already have filtered_files)
    Skip: Phase 2 (already have parsed_ast)
    Execute:
      - Generate failure-specific queries:
        "Edge cases in JWT validation, corner cases"
      - Search: Only within already-indexed functions
      - Web search: Test patterns, error handling
      - Results: Edge case implementations

    Time: ~400ms (reuses previous parsing, no duplication)

    Result: enriched_context[1] with:
      - Edge case implementations
      - Test patterns
      - Mock examples

  GUI receives: adaptive_retrieval_complete event
    - Enrichment time: 400ms
    - New context size: 5k tokens
    - Ready to retry stage 1

    ↓
Stage 1 Retry: code_generation

  CodeAgent receives enriched context:
    {
      retrieval_context[1]: {...original...},
      enriched_context[1]: {...edge cases + test patterns...},
      mcp_tools: {still available}
    }

  CodeAgent:
    Uses enriched context to understand test failures
    Calls MCP tools again if needed
    Generates improved code (iteration 2)
    Returns: {failure: false}

  GUI receives: stage_complete event
    - Iteration: 2
    - Stage: code_generation (retry)
    - Result: success
    - Adaptive enrichment used: yes

  Routes to: node_stage_2 retry

    ↓
Stage 2 Retry: test_generation

  TestAgent rerun tests (with improved code)
  Returns: {failure: false, tests_passed: 10}

  Routes to: node_stage_3

    ↓
(Continue with stages 3, 4...)

    ↓
WORKFLOW COMPLETE

execution_state.iterations = [
  {iteration: 1, stages: [1, 2]},
  {iteration: 2, stages: [1, 2]},
  {iteration: 3, stages: [3, 4]}
]

    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: USER REVIEW (GUI Diff Visualization)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GUI receives: diffs_ready event
  - Batched file changes from all iterations
  - Syntax-highlighted diffs
  - Per-file review options

GUI displays:
  - Iteration 1, Stage 1: auth.py created (CodeAgent)
  - Iteration 1, Stage 2: test_auth.py created (TestAgent, failed)
  - Iteration 2, Stage 1: auth.py modified (CodeAgent, edge cases added)
  - Iteration 2, Stage 2: test_auth.py modified (TestAgent, now passes)
  - Iteration 3, Stage 3: No changes (SecurityAgent passes)
  - Iteration 3, Stage 4: auth.py reformatted (FormatterAgent)

User clicks: Accept All Changes
  → GUI sends: user_accepts_changes event
  → Backend commits to git
  → GUI displays: "Changes committed to main branch"

Performance Profile (Two-Phase Selective Retrieval)

text
Code Workflow Timing:

Planning Phase (Selective):
  Orchestrator reasoning: 200ms
  File-level search: 150ms (reuses pre-computed)
  Selective AST parsing: 2-3s (only 120 filtered files, not 10k)
  Function embedding + indexing: 250ms
  Function-level search: 150ms
  Web + docs: 300ms (parallel with function search)
  Total: ~3.2-3.5s (vs. 11s with all-AST)

  Savings: 7-8 seconds per task (66% faster)

Execution Phase (Same as before):
  Stage 1: 4s
  Stage 2: 4s (if success)
  Stage 3: 3s
  Stage 4: 2s

  With 1 adaptive cycle: +1.2s

Total Workflow:
  Planning: 3.5s
  Execution: 13s
  Adaptive: 1.2s
  Total: ~17.7s (vs. 22s with all-AST planning)

  Net workflow improvement: ~4.3 seconds

Non-Code Workflow Timing:

Planning Phase (Even Faster):
  Orchestrator: 200ms
  File-level search: 150ms
  No AST parsing (skip)
  Document search: 150ms
  Web search: 300ms
  Total: ~0.8s (vs. 11s for code workflows)

  80x faster than all-AST approach

Memory Profile:

  Upfront Indexing (Once):
    File-level embeddings: ~50MB for 10k files
    Function-level (on-task): ~100MB for 487 functions
    Qdrant collections: ~200MB total

  Per-Task (Runtime):
    Filtered files context: ~5-10MB
    Parsed AST: ~20-50MB
    Total peak: ~300MB (manageable)

Key Architectural Improvements (Two-Phase + Selective)
Aspect	All-Files AST (Old)	Two-Phase Selective (New)	Improvement
Upfront AST Time	10s	2-3s	66% faster
Total Planning	11s	3.5s	68% faster
Files Parsed	10,000	50-100	99% fewer
Functions Indexed	5,847	300-500	92% fewer
Memory (Indexing)	High	Low	Significant
Vector DB Usage	Single collection	Two collections (smart)	Better
Selective by Stage	No (all at once)	Yes (per-stage)	More efficient
Adaptive Retrieval	Recompute all	Reuse previous	3-4x faster
Non-Code Penalty	Same as code	80x faster	Huge win
Per-Task Cost	11s overhead	3.5s overhead	Better
Summary

This enhanced specification now includes:

✅ Workspace Initialization: One-time file-level embedding generation (1.5-2s)
✅ Two-Phase Retrieval: File-level filtering (150ms) → Selective AST parsing (2-3s)
✅ Single Vector DB: Qdrant with two collections (workspace_files, workspace_functions)
✅ Selective State Management: LangGraph tracks filtered_files, parsed_ast per stage
✅ Reusable Filtered Context: Adaptive retrieval reuses previous filtering/parsing
✅ GUI Integration: Real-time ACP callbacks for progress, diffs, user review
✅ Workflow Variants: Code (selective AST) and non-code (doc-only, 80x faster)
✅ 66% Speed Improvement: 11s → 3.5s planning phase for code workflows
✅ Research-Backed: Selective retrieval, file-then-function pattern (LinkAnchor, LSFS)
✅ LangChain-Native: Uses standard patterns, MCP integration, ACP streaming
