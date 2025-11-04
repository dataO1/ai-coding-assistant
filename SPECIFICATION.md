Technical Architecture Specification: Agentic IDE (Multi-Agent, Autonomous Retrieval, Workflow-Aware Strategies, LangGraph Deterministic Routing)
System Overview

A self-hosted FOSS agentic IDE combining a Rust GPU-rendered GUI client (Iced) with a Python LangChain multi-agent orchestration backend via Agent Client Protocol (ACP). The system is centered around an Orchestrator Agent—a reasoning LLM with its own capability profile—that receives user queries and context, performs LLM reasoning to understand the task and select the most appropriate workflow, then decides which optional stages should be included based on task context and reasoning_guidance. After stage inclusion decisions, the orchestrator retrieves the workflow-specific retrieval strategy configuration (TART pattern: Task-Aware Retrieval with Instructions), assembles a fixed execution plan via deterministic configuration-based logic, and delegates to an Autonomous Retrieval Agent that independently analyzes task semantics using workflow-specialized strategies, generates context-aware queries, routes to appropriate sources (codebase, web, CVE database, documentation, LSP), and executes parallel retrieval-augmented generation. The Retrieval Agent adapts its behavior based on workflow type: for code workflows, it pre-computes function-level AST indices via Tree-sitter (upfront) and provides on-demand LSP via MCP tools during execution; for non-code workflows, it skips static analysis and focuses on document/semantic-level retrieval. Retrieved results are merged via a Context Fusion Service combining cross-encoder semantic reranking with deterministic deduplication and token budget management. The execution workflow is modeled as a LangGraph state machine with nodes representing stages and conditional edges implementing deterministic routing based on success/failure outcomes. When stages fail, conditional edges automatically route to an Adaptive Retrieval Node that triggers the same Autonomous Retrieval Agent to dynamically generate failure-specific retrieval queries using workflow-aware strategies, or route to the next stage according to the routing table. Specialist agents execute stages with access to workflow-contextualized retrieval, MCP-based static analysis tools (for code workflows), and git-based version control. Users review all proposed changes in batched diff views before acceptance, with optional feedback loops for refinement. Full git-based change tracking and rollback support enable safe autonomous code generation.
Core Principles

LLM Reasoning for Understanding, Selection, & Stage Inclusion: Orchestrator LLM reasons about user intent, selects best workflow, and decides which optional stages to include; orchestrator does NOT generate retrieval queries.

Workflow-Aware Retrieval Strategy Selection (TART Pattern): Orchestrator passes workflow type and retrieval strategy configuration (not task classification) to Retrieval Agent. Retrieval Agent activation is strategy-driven (from config), not self-classifying. Follows Task-Aware Retrieval with Instructions research pattern.

Autonomous Retrieval Agent with Domain Specialization: Dedicated agent independently analyzes tasks using workflow-specific strategies, generates context-aware queries, routes to appropriate sources, and executes retrieval without orchestrator involvement. Behavior adapts per workflow type (code vs. non-code) via configuration, not generic.

Separation of Concerns: Orchestrator handles strategy selection and coordination; Retrieval Agent handles all query generation and execution within workflow-specified parameters. Clean architectural boundaries enable independent optimization and testing.

Code-Specific Strategies (AST + LSP + MCP): For code workflows: Retrieval Agent pre-computes function-level AST indices via Tree-sitter during planning (upfront, one-time, ~10s for 10k files). During execution, specialist agents access LSP via MCP tools (on-demand) for precise type information, definitions, references, and signatures. Non-code workflows skip static analysis entirely.

Non-Code Retrieval Strategies: For planning, document, and other non-code workflows, Retrieval Agent focuses on semantic document/section retrieval, decision log searches, specification analysis. No AST parsing, no language-specific tools. Configuration-driven specialization prevents wasted effort.

Config-Based Execution Plan Assembly: Fixed execution plan built from workflow YAML configuration deterministically (no LLM) after stage inclusion is decided; purely structural logic.

LangGraph Deterministic Routing: Execution workflow modeled as state machine with nodes for stages and conditional edges for routing. All routing paths encoded upfront in graph structure, eliminating runtime observer pattern. Routing decisions determined by stage failure outcomes and max_attempts counters in execution state.

Parallel Retrieval-Augmented Generation: Retrieval Agent pre-computes stage-specific context during planning phase in parallel; zero per-agent retrieval overhead during execution. Each stage receives optimized, specialized context (not generic).

Adaptive Retrieval as Graph Node: Adaptive retrieval is a node in the execution graph, not a separate reactive component. Triggered by conditional edges when failure occurs and retry is beneficial. Same Autonomous Retrieval Agent executes both upfront and adaptive retrieval using same workflow-aware strategies.

Intelligent Failure Analysis: Retrieval Agent autonomously analyzes failure context using workflow-specific strategies; no separate classifier component. Direct semantic reasoning about what information would help fix failures within domain context.

Cross-Encoder Semantic Reranking: Context fusion uses learned ranking (not heuristics) to prioritize relevant information, reducing noise and hallucination risks.

Validation & Self-Correction: Validation layer checks context groundedness before injection into retry stage, preventing hallucination cascades.

Dependency-Aware Context: Subsequent retries receive enriched context addressing previous stage failures via workflow-aware retrieval executed by autonomous Retrieval Agent.

Retrieval Scoping to Workspace: All retrieval operations filtered to workspace-relevant files only; excluded patterns (node_modules, .git, build artifacts) prevent context pollution.

Workspace-Scoped Embeddings: File indexing maintains separate embeddings per workspace; no global codebase cross-contamination. Function-level indexing for code workflows, document-level for non-code.

Multi-Source RAG with Workflow-Specific Routing: Retrieval Agent autonomously aggregates from sources appropriate to workflow type. Code workflows: codebase, LSP, web, CVE database, documentation. Non-code workflows: codebase, web, documentation (no LSP/static analysis).

MCP Integration for Static Analysis Tools: Code workflows access Tree-sitter AST and LSP via standardized Model Context Protocol, enabling precise code understanding without token bloat. Agents call MCP tools on-demand during execution, not upfront.

Fixed Execution Plan: Once assembled, execution plan is immutable during workflow execution; reflected in graph structure. Only Adaptive Retrieval augments context post-failure.

Binary Stage Routing: Stage routing uses only success/failure boolean outcomes. Encoded as conditional edge conditions evaluated on stage completion.

If-Then-Else Logic: Conditional edges implement: if stage.failure: route_to_failure_path else: route_to_success_path (deterministic, encoded in graph).

Max Attempts = Immediate Failure: When stage reaches max_attempts, conditional edge routes to failure path (no re-evaluation). Enforced by execution state counter.

Aggregated Failure Decision: Multiple parallel agents' failures aggregated via configurable strategy (any-fails, all-fail, majority-fail). Result stored in execution state as single boolean flag for conditional edge evaluation.

Agent-Defined Failure Criteria: Each agent returns boolean failure flag with rich context; orchestrator never second-guesses.

Parallel Within-Stage: Multiple agents execute in parallel; aggregated results determine stage outcome.

Sequential Between-Stages: Stages execute in order defined by graph edges; next stage determined by conditional routing based on execution state.

Single Source of Truth: Agent orchestration layer owns filesystem, embeddings, tool execution, git state.

User-Centric Review: All modifications batched and reviewed before acceptance; feedback loops allow refinement.

Full Auditability: Every action committed to git; full history available for rollback. LangGraph execution history automatically tracked for all iterations.

Schema-First: Tool definitions, workflows, capabilities, retrieval strategies, and task contexts generated from canonical schemas.

LangChain Integration: Built on LangChain ecosystem using standard patterns (agents, chains, tools, retrievers, memory). LangGraph used for workflow execution and state management. MCP integration via LangChain-native tools.
Architecture Layers
Layer 0: Workflow Selection + Stage Inclusion via LLM Reasoning (Focused Orchestrator)

Orchestrator LLM performs focused reasoning on strategy only (no retrieval query generation):

text
User query: "Implement authentication feature"
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

Layer 0.5: Workflow-Specific Retrieval Strategy Configuration (NEW - TART Pattern)

Orchestrator retrieves and passes workflow-specific retrieval strategy (Task-Aware Retrieval with Instructions pattern):

text
After Orchestrator selects workflow:

1. Lookup: workflows/[workflow_name].yaml
   Extract: retrieval_strategy_config section

2. For Code Workflows (e.g., feature_workflow):
   {
     workflow_type: "code_implementation",
     retrieval_enabled: true,
     retrieval_strategy: "code_domain",

     strategy_config: {
       ast_parsing: true,
       ast_model: "tree_sitter",
       index_level: "function",
       lsp_integration: true,
       rag_chunk_strategy: "semantic_functions",

       context_sources: [
         {source: "codebase_semantic_search", strategy: "function_level", priority: "HIGH"},
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
       ast_parsing: false,
       lsp_integration: false,
       rag_chunk_strategy: "semantic_sections",

       context_sources: [
         {source: "codebase_semantic_search", strategy: "document_level", priority: "MEDIUM"},
         {source: "specification_search", strategy: "sections", priority: "HIGH"},
         {source: "decision_log_search", strategy: "related_decisions", priority: "HIGH"},
         {source: "web_search", strategy: "current_patterns_standards", priority: "MEDIUM"}
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

Key: Configuration is EXPLICIT (from YAML), not implicit (from agent reasoning)
     Retrieval Agent follows instructions, doesn't classify

TART Pattern Application: Following Task-Aware Retrieval with Instructions research, orchestrator provides explicit task instructions (via workflow config) rather than expecting Retrieval Agent to infer strategy. Research shows this outperforms 3x larger generic models.

LangChain Integration (Layer 0.5):

text
Components:
  - Custom retrieval strategy loader (reads workflow YAML)
  - langchain.schema.Document (strategy configuration structure)
  - Environment-aware configuration (workspace-specific)

Layer 1: Autonomous Retrieval Agent with Workflow-Aware Strategies (Core Component)

Dedicated agent with its own intelligence that handles ALL retrieval operations using workflow-specific strategies:

text
Autonomous Retrieval Agent Architecture:

Receives from Orchestrator:
  {
    user_task: string,
    workflow_type: "code_domain" | "document_domain" | "other",
    retrieval_config: {...strategy configuration...}
  }

Responsibilities (Workflow-Adaptive):
  1. Analyze task semantics within workflow context
  2. Generate context-aware queries using workflow-specific strategy
  3. Decide source routing (based on retrieval_config, not self-decision)
  4. For code workflows: Prepare AST indices (upfront) + LSP tools (on-demand)
  5. For non-code workflows: Prepare document-level indices
  6. Execute parallel retrieval
  7. Rerank and structure results per workflow
  8. Return grounded, attributed context

Does NOT:
  - Self-classify workflow type (Orchestrator decided)
  - Create retrieval queries against config (Orchestrator provided)
  - Waste resources on irrelevant tools (config-driven activation)

Triggered in two modes:
  - Upfront mode (planning phase): Generate initial context for all stages
  - Adaptive mode (graph edge): Generate failure-specific context on retry

Upfront Retrieval Phase (Planning Phase - Code Workflows):

text
Input from Orchestrator:
  {
    user_task: "Implement JWT authentication",
    workflow_type: "code_domain",
    retrieval_config: {...with ast_parsing: true, index_level: "function"...}
  }

Step 1: AST Parsing & Function-Level Indexing (Code Workflows Only)

  Condition: IF retrieval_config.ast_parsing == true

  Execute:
    └─ Tree-sitter Parsing Agent:
       For each workspace file:
         1. Parse with Tree-sitter (Rust-based, ~1ms per file)
         2. Extract AST nodes: functions, classes, imports
         3. Generate semantic embeddings per function (not per file)
         4. Store in vector DB: {function_id: {ast_type, signature, dependencies, embedding}}

       Metadata stored:
         - Function name, file location, line number
         - Type signature (from AST)
         - Dependencies (imported functions, classes)
         - Return type, parameters

       Time: ~5-10 seconds for 10k files (one-time per session)

  After indexing:
    Generate "AST Context Map" (structured reference):
      {
        functions: [{name, file, params, returns}],
        classes: [{name, file, methods}],
        imports: [{module, symbols}],
        structure: hierarchical
      }

    Store: execution_state.ast_context_map

Step 2: Task-Specific Query Generation (Code Workflows)

  Retrieval Agent analyzes:
    "Task: JWT authentication implementation
     Workflow: code_domain
     Available strategies: [function_level_search, lsp_tools, web_search]

     What context would help?
     - Existing JWT functions in codebase
     - Latest JWT libraries
     - Framework-specific integration patterns"

  Generates queries (using strategy from config):
    For codebase (function-level, not file-level):
      - "JWT authentication implementation functions"
      - "Token validation functions"
      - "existing auth utilities"

    For web search (pattern discovery):
      - "Python JWT best practices 2025"
      - "JWT security patterns"

    For docs (framework guidance):
      - "Flask JWT integration"
      - "Flask security best practices"

Step 3: Parallel Retrieval Execution (Code Workflows)

  Parallel tasks for each stage:

    RetrieverTask_1 (code_generation):
      ├─ Semantic search on AST indices (function-level):
      │  Query: "JWT implementation functions"
      │  Time: ~300ms (fast, targeted)
      ├─ Web search: "JWT best practices"
      │  Time: ~300ms
      ├─ Doc retrieval: "Flask JWT guide"
      │  Time: ~200ms
      └─ Deduplicate + compress to 30k tokens

    RetrieverTask_2 (test_generation):
      ├─ Semantic search on AST indices (function-level):
      │  Query: "JWT test functions"
      │  Time: ~300ms
      ├─ Web search: "pytest JWT testing"
      │  Time: ~200ms
      └─ Compress to 25k tokens

    RetrieverTask_3 (security_review):
      ├─ CVE database search: "JWT vulnerabilities"
      │  Time: ~200ms
      ├─ Web search: "OWASP JWT"
      │  Time: ~300ms
      └─ Compress to 20k tokens

    All run simultaneously: max(all) ≈ 600ms

Step 4: Result Aggregation & Structuring (Code Workflows)

  For each stage:
    ├─ Results include: code snippets + AST metadata
    ├─ Store function references: {function_id, file, line, signature}
    ├─ Deduplicate across sources
    ├─ Compress to token budget
    ├─ Attribute sources
    └─ Store indexed by stage_id

  Output: execution_state.retrieval_context populated
          execution_state.ast_context_map populated

Total Upfront Time: ~400ms reasoning + 600ms retrieval + 10s AST parsing = 11s total
                   (AST parsing one-time, amortized across stages)

Upfront Retrieval Phase (Non-Code Workflows):

text
Input from Orchestrator:
  {
    user_task: "Discuss JWT architecture decisions",
    workflow_type: "document_domain",
    retrieval_config: {...with ast_parsing: false, rag_chunk_strategy: "semantic_sections"...}
  }

Step 1: Document-Level Indexing (Non-Code Workflows Only)

  Condition: IF retrieval_config.ast_parsing == false

  Execute:
    └─ Document Structure Agent:
       For each workspace document (markdown, spec, etc.):
         1. Parse structure: sections, subsections, headings
         2. Extract semantic sections (not functions)
         3. Generate embeddings per section (not per function)
         4. Store: {section_id: {title, content, parent, embedding}}

       Time: ~2-3 seconds for document structures (much faster, no parsing)

Step 2: Task-Specific Query Generation (Non-Code Workflows)

  Retrieval Agent analyzes:
    "Task: Discuss JWT authentication architecture
     Workflow: document_domain
     Available strategies: [section_search, decision_log, web_search]

     What context would help?
     - Previous architecture decisions
     - JWT-related discussions
     - Current design rationale"

  Generates queries (using strategy from config):
    For codebase (document-level):
      - "JWT architecture decisions"
      - "authentication design patterns"

    For decision log:
      - "Previous JWT discussions"
      - "security decisions"

    For web search:
      - "JWT architecture best practices 2025"
      - "microservices authentication patterns"

Step 3: Parallel Retrieval Execution (Non-Code)

  Same pattern but document-focused:
    ├─ Semantic search on document sections
    ├─ Decision log search
    ├─ Web search for current practices
    └─ Parallel execution: ~400-500ms

Total Upfront Time: ~400ms reasoning + 500ms retrieval = 900ms total
                   (Significantly faster than code workflows, no AST parsing)

Adaptive Retrieval (Graph Edge Trigger - Workflow-Aware):

text
When conditional edge detects: stage_failure == true AND max_attempts_not_exceeded

Retrieval Agent receives (same workflow context):
  {
    trigger_mode: "adaptive",
    failure_context: {...stage failure output...},
    retry_stage: 1,
    user_task: "...",
    workflow_type: "code_domain",  # Knows workflow context
    retrieval_config: {...}  # Same config, used to guide adaptation
  }

Analyzes autonomously using workflow-aware strategy:
  "Given failure context + workflow strategy, what queries?"

  For Code Workflows:
    - "Failure: Test assertion failed"
    - "Strategy says: Use function-level search + LSP tools"
    - "Generate: Queries about test patterns, edge cases"
    - "Execute: Search AST indices for test functions + LSP queries"

  For Non-Code Workflows:
    - "Failure: Incomplete information in discussion"
    - "Strategy says: Use document search + decision log"
    - "Generate: Queries about related decisions, implications"
    - "Execute: Document search + decision log search"

Time: ~500ms adaptive retrieval per failure

Retrieval Sources (Multi-Source, Workflow-Specific):

text
Code Workflow Sources:

Codebase Semantic Search (Function-Level):
  ├─ Index: Qdrant with function-level embeddings (from AST)
  ├─ Embedding model: nomic-embed-text
  ├─ Query: Semantic search on functions (not files)
  ├─ Result: Function IDs + signatures + code snippets
  └─ Speed: ~5k queries/sec

LSP (On-Demand, MCP):
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

Document Semantic Search:
  ├─ Index: Qdrant with section-level embeddings
  ├─ Query: Semantic search on document sections
  ├─ Result: Section references + content
  └─ Speed: ~5k queries/sec

Decision Log Search:
  ├─ Index: Previous architectural decisions
  ├─ Query: Related decisions, implications
  └─ Result: Decision references + rationale

Specification Search:
  ├─ Index: Specification documents
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
  - langchain.retrievers.EnsembleRetriever (hybrid semantic + BM25)
  - langchain.vectorstores.Qdrant (vector database for AST + docs)
  - langchain.embeddings.HuggingFaceEmbeddings (nomic-embed-text)
  - langchain.tools.DuckDuckGoSearchRun (web search)
  - langchain.document_loaders.WebBaseLoader (doc retrieval)
  - langchain_experimental.text_splitter.SemanticChunker (chunk documents)
  - langchain.chains.ConversationalRetrievalChain (adaptive mode)
  - langchain.memory.ConversationBufferMemory (iteration tracking)
  - langchain.mcp.MCPToolkit (MCP integration for LSP + Tree-sitter)

Layer 2: Deterministic Execution Plan Assembly (Config-Based, No Retrieval Specs)

After Orchestrator decides stages and retrieval strategy, assemble plan:

text
Execution Plan Assembly Process:

Input:
  - selected_workflow: "feature_with_iterative_testing"
  - llm_stage_decisions: {1: INCLUDE, 2: INCLUDE, 3: INCLUDE, 4: INCLUDE}
  - retrieval_strategy_config: {...from workflow YAML...}
  - NO retrieval_queries (not generated by orchestrator)

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
  Includes: workflow_type, retrieval_strategy_config, routing_table, task_context

LangChain Integration (Layer 2):

text
Components:
  - langchain_core.graph.StateGraph (graph structure definition)
  - Custom execution state schema (Pydantic BaseModel)
  - langchain.schema.Document (execution plan structure)

Layer 2.5: LangGraph Execution Graph (Deterministic Routing with State Machine)

Execution workflow modeled as state machine with workflow-aware context:

text
Graph Architecture:

State Schema:
  - current_stage: int
  - stage_results: {stage_id: {failure, attempt, output, files_changed}}
  - enrichment_attempts: {stage_id: count}
  - enriched_context: {stage_id: context}
  - routing_table: {...from execution plan...}
  - workflow_type: "code_domain" | "document_domain" | other
  - ast_context_map: {...from AST parsing, if code workflow...}
  - mcp_tools_available: {lsp: true/false, tree_sitter: true/false}  # Based on workflow
  - iterations: []
  - retrieval_context: {stage_id: context}

Nodes (Execution Units):
  1. node_stage_1_[stage_name]
  2. node_stage_2_[stage_name]
  ... (for each planned stage)
  n. node_adaptive_retrieval (reusable, workflow-aware)
  n+1. node_workflow_done
  n+2. node_workflow_abort

Conditional Edges (Deterministic Routing, Workflow-Aware):

  After each stage execution:
    edge_stage_X_router:
      Evaluates: execution_state.stage_results[X].failure + routing_table[X]

      Condition 1: IF failure == false
        → Route to: routing_table[X].next_on_success

      Condition 2: IF failure == true AND enrichment_attempts[X] < 2 AND retrieval_config.allows_enrichment
        → Route to: node_adaptive_retrieval
           Set context: {retry_stage: X, workflow_type, retrieval_config}

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

LangChain Integration (Layer 2.5):

text
Components:
  - langchain_core.graph.StateGraph (state machine foundation)
  - langchain_core.runnables.RunnableBranch (conditional edge logic)
  - Pydantic BaseModel (execution state schema with workflow context)
  - langchain_core.runnables.RunnableGraph (compiled executable)

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
    Code workflows: Prioritize code-specific relevance
    Document workflows: Prioritize section/decision relevance

  Process: Score each chunk against query using domain context

Component 2: Workflow-Specific Deduplication

  Exact Deduplication:
    ├─ String matching across all chunks
    ├─ Remove identical content
    └─ Time: <50ms

  Semantic Deduplication (Workflow-Aware):
    ├─ For code: Compare function signatures + implementations
    ├─ For docs: Compare section summaries + topics
    ├─ Use cosine similarity > 0.95
    └─ Time: <100ms

Component 3: Token Budget Management

  Budget enforcement:
    Retrieve from: retrieval_config.retrieval_hints.token_budget
    Apply: Per-stage token limits (e.g., 30k for code_gen)

Component 4: Workflow-Specific Attribution

  For code workflows:
    ├─ Tag: function_id, file, line_number, ast_type
    ├─ Preserve: Function signatures, type info
    └─ Include: MCP-queryable references

  For document workflows:
    ├─ Tag: section_id, document, section_path
    ├─ Preserve: Document structure, hierarchy
    └─ Include: Decision references

Result: Merged, ranked, attributed context ready for agents

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
Validation Layer:

1. Grounding Check:
   For code: Is code snippet from actual codebase?
   For docs: Is section from actual document?

2. Consistency Check:
   For code: Does code contradict previous iterations?
   For docs: Does information conflict with decisions?

3. Relevance Check:
   Use cross-encoder scores (already computed)
   Workflow-specific thresholds:
     Code workflows: threshold > 0.7
     Document workflows: threshold > 0.6

LangChain Integration (Layer 4):

text
Components:
  - langchain.evaluation.qa.QAEvalChain
  - Custom workflow-aware validation logic

Layer 5: Stage Execution within LangGraph (Deterministic Graph Routing, Workflow-Aware)

Stages execute as graph nodes with workflow-specific context and tools:

text
LangGraph Execution Flow (Workflow-Aware):

Stage Execution for Code Workflows:

  Stage Node receives:
    {
      task: string,
      retrieval_context: {code snippets, function references},
      ast_context_map: {available functions, types, structure},
      enriched_context: {...if adaptive...},
      mcp_tools: {lsp_get_signature, lsp_find_definition, ...}
    }

  CodeAgent executes:
    1. Reads task + retrieval context
    2. Can call MCP tools on-demand:
       - lsp.get_signature(function_name): Get precise type signature
       - lsp.find_definition(symbol): Find where symbol defined
       - lsp.get_references(symbol): Find usages
       - tree_sitter.get_ast_node(file, line): Get AST structure
    3. Uses enriched context if retry
    4. Generates code
    5. Returns: {failure: bool, output: code}

  TestAgent, SecurityAgent: Similar, with workflow-specific tools

Stage Execution for Non-Code Workflows:

  Stage Node receives:
    {
      task: string,
      retrieval_context: {document sections, decision references},
      enriched_context: {...if adaptive...},
      mcp_tools: {} # Empty, no LSP/AST tools
    }

  AnalysisAgent executes:
    1. Reads task + retrieval context
    2. No MCP tools (not applicable)
    3. Uses retrieval context directly
    4. Generates analysis/decisions
    5. Returns: {failure: bool, output: analysis}

Conditional Routing (Same for Both):

  After stage completion:
    Edge evaluation checks:
      - failure status
      - max_attempts limit
      - enrichment_attempts limit
      - routing_table paths

    Routes to:
      - Next success stage
      - Adaptive retrieval (if applicable, workflow-aware)
      - Next failure stage
      - Abort

Total Workflow Execution:
  Planning phase: 11s (code) or 0.9s (non-code) for retrieval
  Execution phase: LangGraph traversal with workflow-specific context per stage
  Adaptive cycles: Triggered by edges, ~0.7s per cycle (workflow-aware)

LangChain Integration (Layer 5):

text
Components:
  - langchain_core.graph.StateGraph (execution graph)
  - langchain_core.runnables.RunnableBranch (conditional edges)
  - langchain.agents.AgentExecutor (stage agents)
  - langchain.tools.Tool (file operations, terminal, retrieval)
  - langchain.mcp.MCPToolkit (LSP + Tree-sitter via MCP)
  - langchain.memory.ConversationBufferMemory (iteration tracking)
  - langchain_core.runnables.RunnableGraph (compiled execution)

Messaging Schemas (Updated for Workflow-Aware Architecture)
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

  "retrieval_strategy": "code_domain",

  "retrieval_strategy_config": {
    "ast_parsing": true,
    "ast_model": "tree_sitter",
    "index_level": "function",
    "lsp_integration": true,
    "context_sources": [
      {source: "codebase_semantic_search", strategy: "function_level", priority: "HIGH"},
      {source: "lsp_tools", strategy: "on_demand", priority: "HIGH"},
      {source: "web_search", strategy: "libraries_patterns", priority: "MEDIUM"}
    ],
    "token_budget": {1: 30000, 2: 25000, 3: 20000, 4: 10000}
  },

  "tart_pattern_applied": true,
  "instructions_explicit": true
}

Autonomous Retrieval Agent Response (Code Workflow)

json
{
  "type": "autonomous_retrieval_completed",
  "correlationId": "string",
  "workflow_type": "code_domain",
  "mode": "upfront|adaptive",

  "ast_indexing": {
    "status": "completed",
    "files_parsed": 10240,
    "functions_indexed": 5847,
    "time_ms": 9200,
    "index_level": "function",
    "embeddings_generated": 5847
  },

  "retrieval_agent": {
    "model": "mistral-7b-instruct-q4",
    "strategy": "code_domain",
    "reasoning_time_ms": 400,
    "retrieval_execution_time_ms": 600
  },

  "retrieval_results": {
    "1": {
      "strategy_applied": "function_level_search",
      "sources": ["codebase_ast", "web_search", "docs"],
      "functions_retrieved": 15,
      "context_summary": "JWT auth patterns at function level",
      "token_count": 30000,
      "includes_ast_references": true
    },
    "2": {
      "strategy_applied": "function_level_search",
      "sources": ["codebase_ast", "web_search"],
      "functions_retrieved": 12,
      "context_summary": "JWT test patterns",
      "token_count": 25000
    }
  },

  "mcp_tools_prepared": {
    "lsp": ["get_signature", "find_definition", "get_references"],
    "tree_sitter": ["get_ast_node"]
  }
}

Autonomous Retrieval Agent Response (Non-Code Workflow)

json
{
  "type": "autonomous_retrieval_completed",
  "correlationId": "string",
  "workflow_type": "document_domain",
  "mode": "upfront|adaptive",

  "ast_indexing": {
    "status": "skipped",
    "reason": "non_code_workflow"
  },

  "document_indexing": {
    "status": "completed",
    "documents_processed": 12,
    "sections_indexed": 247,
    "time_ms": 2800,
    "chunk_strategy": "semantic_sections"
  },

  "retrieval_results": {
    "planning_stage": {
      "strategy_applied": "document_section_search",
      "sources": ["specification", "decision_log", "web_search"],
      "sections_retrieved": 18,
      "context_summary": "JWT architecture decisions and options",
      "token_count": 20000,
      "includes_decision_references": true
    }
  },

  "mcp_tools_prepared": {
    "lsp": [],
    "tree_sitter": []
  }
}

LangGraph Execution Progress (Workflow-Aware)

json
{
  "type": "langgraph_execution_progress",
  "correlationId": "string",
  "workflow_type": "code_domain",

  "current_node": "node_stage_1_code_generation",
  "execution_context": {
    "retrieval_context_available": true,
    "ast_context_map_available": true,
    "mcp_tools_available": ["lsp", "tree_sitter"],
    "token_budget_remaining": 5000
  },

  "stage_result": {
    "stage_id": 1,
    "failure": false,
    "tools_used_during_execution": ["lsp_get_signature", "lsp_find_definition"],
    "output_tokens": 2000
  },

  "edge_routing_decision": {
    "condition_evaluated": "stage_results[1].failure == false",
    "next_node": "node_stage_2_test_generation"
  }
}

Configuration Schemas (Updated for Workflow-Specific Strategies)
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

Autonomous Retrieval Agent Configuration

text
# retrieval_agent_config.yaml
autonomous_retrieval_agent:
  agent_type: "workflow_aware_multi_domain_retrieval"
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

    ast_parsing:
      enabled: true
      tool: "tree_sitter"
      index_level: "function"
      upfront_execution: true
      timing_ms: "5000-10000 per 10k files"
      output: "function_level_embeddings"

    lsp_integration:
      enabled: true
      protocol: "Language Server Protocol"
      integration: "MCP (Model Context Protocol)"
      execution: "on_demand_during_agent_execution"
      tools: ["get_signature", "find_definition", "get_references", "get_type"]

    rag_strategy:
      chunk_strategy: "semantic_functions"
      sources:
        - codebase_semantic_search (function_level)
        - lsp_tools (on_demand)
        - web_search (libraries_patterns)
        - doc_retrieval (framework_docs)
        - cve_database (security_stage)

  non_code_workflow_specialization:
    enabled: true

    document_indexing:
      enabled: true
      chunk_strategy: "semantic_sections"
      upfront_execution: true
      timing_ms: "1000-3000 per documents"

    lsp_integration:
      enabled: false
      reason: "not_applicable_to_documents"

    rag_strategy:
      chunk_strategy: "document_sections"
      sources:
        - document_semantic_search (section_level)
        - specification_search
        - decision_log_search
        - web_search (current_standards)

  adaptive_mode:
    enabled: true
    trigger: "langgraph_conditional_edge_on_failure"
    strategy: "workflow_aware_failure_analysis"
    max_adaptive_cycles: 2

  retrieval_execution:
    parallel_enabled: true
    max_parallel_tasks: 5
    timeout_per_source_ms: 3000

    sources_config:
      codebase_semantic_search:
        provider: "qdrant"
        embedding_model: "nomic-embed-text"
        search_type: "hybrid"
        workspace_scoping: true
        index_level_override: "from_workflow_config"

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

LangGraph Execution Configuration

text
# langgraph_execution_config.yaml
langgraph:
  workflow_name: "agentic_ide_execution"
  workflow_aware: true

  state_management:
    schema: "ExecutionState"
    persistence: "enabled"

    state_fields:
      workflow_type:
        type: "string"
        values: ["code_domain", "document_domain", "other"]
        determines: "behavior_of_all_agents_and_edges"

      ast_context_map:
        type: "dict"
        populated_if: "workflow_type == 'code_domain'"
        availability: "to_all_code_agents"

      mcp_tools_available:
        type: "dict"
        keys: ["lsp", "tree_sitter"]
        values_per_workflow: "from_retrieval_strategy_config"

      retrieval_context:
        type: "dict"
        structure: "workflow_specific"
        code_workflow: "{function_id: code + ast_metadata}"
        document_workflow: "{section_id: text + document_metadata}"

  nodes:
    stage_nodes:
      execution_context: "workflow_aware"
      tools_available: "based_on_workflow_type_and_config"
      receive: "{task, context, mcp_tools, ast_map}"

    adaptive_retrieval_node:
      workflow_aware: true
      applies_strategy: "from_retrieval_strategy_config"

  conditional_edges:
    routing_logic: "deterministic"
    uses: "routing_table + execution_state"
    workflow_awareness: "in_failure_analysis_for_enrichment"

  callbacks:
    handlers:
      - type: "WorkflowAwareProgressHandler"
        tracks: "workflow_type_specific_metrics"

  langchain_integration:
    core_modules:
      - "langchain_core.graph.StateGraph"
      - "langchain_core.runnables.RunnableBranch"
      - "langchain_core.runnables.RunnableGraph"

    mcp_modules:
      - "langchain.mcp.MCPToolkit"
      - "MCPServer (external, running separately)"

    workflow_config_loader:
      loads: "workflows/*.yaml retrieval_strategy_config"
      passes_to: "retrieval_agent at start"

Workflow Definition (Updated with Retrieval Strategy)

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
  strategy_name: "code_domain_ast_lsp"
  pattern_applied: "TART (Task-Aware Retrieval with Instructions)"

  ast_parsing:
    enabled: true
    model: "tree_sitter"
    index_level: "function"
    upfront_execution: true

  lsp_integration:
    enabled: true
    execution: "on_demand"
    tools:
      - get_signature
      - find_definition
      - get_references

  rag_strategy:
    chunk_strategy: "semantic_functions"
    sources:
      - name: "codebase_semantic_search"
        indexing: "function_level"
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

    retrieval_guidance: |
      This stage generates implementation code.

      Retrieval strategy: code_domain (AST + LSP)

      Context priorities (from retrieval_strategy_config):
      - HIGH: Existing code patterns (function-level from AST)
      - HIGH: On-demand LSP queries during generation
      - MEDIUM: Latest best practices (web)
      - MEDIUM: Framework guides (docs)

      Agent can call MCP tools:
        - lsp.get_signature(function): Get exact parameter types
        - lsp.find_definition(symbol): Find where symbol is defined
        - tree_sitter.get_ast_node(file, line): Get code structure

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

    retrieval_guidance: |
      This stage generates and runs tests.

      Retrieval strategy: code_domain (function-level patterns)

      Context priorities:
      - HIGH: Existing test functions (from AST)
      - MEDIUM: Web search for test patterns

      Can use MCP tools:
        - lsp.get_references(function): Find all usages of function

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

      Retrieval strategy: code_domain + CVE database

      Context priorities:
      - HIGH: Known vulnerabilities (CVE database)
      - HIGH: Security standards (OWASP, RFC)
      - MEDIUM: Security best practices

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
  strategy_name: "document_domain_discussion"
  pattern_applied: "TART (Task-Aware Retrieval with Instructions)"

  ast_parsing:
    enabled: false
    reason: "non_code_workflow"

  lsp_integration:
    enabled: false
    reason: "not_applicable_to_documents"

  rag_strategy:
    chunk_strategy: "semantic_sections"
    sources:
      - name: "document_semantic_search"
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
        mcp_tools: []  # No MCP tools for document analysis

    retrieval_guidance: |
      This stage analyzes architectural decisions.

      Retrieval strategy: document_domain (sections + decisions)

      Context: Previous decisions, specifications, current options
      No MCP tools available (non-code workflow)

    routing:
      next_stage_on_success: 2
      next_stage_on_failure: "ABORT"
      max_attempts: 1

    failure_criteria:
      agent_defined: true

  - stage_id: 2
    name: "decision_documentation"
    required: false

    parallel_agents:
      - agent: "documentation_agent"

    routing:
      next_stage_on_success: "DONE"
      next_stage_on_failure: "DONE"
      max_attempts: 1

Complete Workflow Execution Flow: Workflow-Aware with AST/LSP
Code Workflow Example

text
USER QUERY: "Implement JWT authentication with comprehensive tests"

    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0: PLANNING (Orchestrator - Workflow Selection)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestrator LLM (200ms):
  Selects: feature_with_iterative_testing workflow
  Decides stages: [1, 2, 3, 4] all included

Loads workflow YAML → Extracts retrieval_strategy_config:
  {
    strategy_name: "code_domain_ast_lsp",
    ast_parsing: true,
    lsp_integration: true,
    rag_strategy: [...],
    token_budget: {...}
  }

Passes to Retrieval Agent:
  {
    user_task: "Implement JWT auth with tests",
    workflow_type: "code_implementation",
    retrieval_config: {...}
  }

    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: UPFRONT RETRIEVAL (Autonomous Retrieval Agent - Code-Specialized)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Retrieval Agent reads config:
  "ast_parsing: true" → Activates AST parsing (not skipped)
  "lsp_integration: true" → Prepares LSP tools
  "rag_strategy: code_domain" → Uses function-level search

Step 1: AST Parsing & Function Indexing (10 seconds, one-time)
  Tree-sitter parses all workspace files
  Extracts function-level AST: 5,847 functions indexed
  Generates function-level embeddings
  Creates ast_context_map with function references

Step 2: Task-Specific Query Generation (Code Strategy)
  Analyzes: "JWT auth implementation"
  Strategy: function-level semantic search (not file-level)
  Generates queries:
    - Codebase (function search): "JWT authentication functions"
    - Web: "Python JWT best practices"
    - Docs: "Flask JWT guide"

Step 3: Parallel Retrieval (600ms)
  All sources execute in parallel:
    - Codebase AST search: 300ms
    - Web search: 300ms
    - Doc retrieval: 200ms

Result:
  retrieval_context[1]: 30k tokens (code + function references)
  retrieval_context[2]: 25k tokens (test patterns)
  retrieval_context[3]: 20k tokens (security)
  ast_context_map: 5,847 function references
  mcp_tools_available: ["lsp_get_signature", "lsp_find_definition", ...]

    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: LANGGRAPH EXECUTION (Deterministic Routing - Code Workflow)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LangGraph initialized with:
  execution_state.workflow_type = "code_domain"
  execution_state.ast_context_map = {...}
  execution_state.mcp_tools_available = {lsp: true, tree_sitter: true}
  execution_state.retrieval_context = {...}

    ↓
Stage 1 Node: code_generation

  CodeAgent receives:
    {
      task: "Implement JWT auth",
      retrieval_context[1]: {code patterns + function references},
      ast_context_map: {functions available in workspace},
      mcp_tools: {lsp_get_signature, lsp_find_definition, tree_sitter_get_ast}
    }

  CodeAgent executes:
    1. Reads retrieval context (JWT patterns)
    2. Analyzes: "I need JWT implementation. Let me check signature."
    3. Calls MCP LSP tool: lsp.get_signature("authenticate")
       → Returns: "def authenticate(token: str) -> Dict[str, Any]"
    4. Calls MCP LSP tool: lsp.find_definition("TokenPayload")
       → Returns: "class TokenPayload in auth_models.py"
    5. Accesses ast_context_map: Sees all available auth functions
    6. Generates code with precise type info + existing patterns
    7. Returns: {failure: false, files_changed: 1}

  Conditional edge evaluation:
    failure == false → Route to: node_stage_2

    ↓
Stage 2 Node: test_generation

  TestAgent receives same context structure
  Executes tests
  Returns: {failure: true, failed_tests: 3}

  Conditional edge evaluation:
    failure == true AND enrichment_attempts < 2
    → Route to: node_adaptive_retrieval (with workflow context)

    ↓
Adaptive Retrieval Node (Workflow-Aware)

  Receives: {failure_context, retry_stage: 1, workflow_type: "code_domain", config}

  Retrieval Agent (adaptive mode):
    Strategy from config: "code_domain"
    Analyzes: "Test failures, need edge cases"
    Generates queries (code-specific):
      - "JWT edge cases in codebase (function-level)"
      - "Token validation corner cases"
    Executes parallel retrieval: 500ms

    Result: enriched_context[1] with:
      - Edge case implementations
      - Test patterns
      - Type examples

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
    Calls MCP tools again if needed for precision
    Generates improved code (iteration 2)
    Returns: {failure: false}

  Routes to: node_stage_2 retry
    ↓
(Continue with stages 2, 3, 4...)

    ↓
WORKFLOW COMPLETE
  execution_state.iterations tracked automatically
  ast_context_map used throughout
  MCP tools called on-demand during execution

Non-Code Workflow Example

text
USER QUERY: "Let's discuss the JWT architecture decisions we made"

    ↓
PHASE 0: PLANNING

Orchestrator selects: architecture_discussion workflow
Loads config:
  {
    strategy_name: "document_domain_discussion",
    ast_parsing: false,
    lsp_integration: false,
    rag_strategy: document_sections,
    ...
  }

    ↓
PHASE 1: UPFRONT RETRIEVAL (Autonomous Retrieval Agent - Document-Specialized)

Retrieval Agent reads config:
  "ast_parsing: false" → Skips AST parsing (saves 10s!)
  "lsp_integration: false" → No LSP tools
  "rag_strategy: document_sections" → Uses section-level search

Document indexing: 2.8 seconds (sections extracted, embedded)

Query generation (document strategy):
  - "JWT architecture decisions"
  - "Authentication design rationale"
  - "Previous JWT discussions"

Parallel retrieval: 400ms
  - Document search: 250ms
  - Decision log search: 200ms
  - Web search: 300ms

Result:
  retrieval_context[planning]: 20k tokens (sections + decisions)
  No ast_context_map (not applicable)
  No mcp_tools (empty)

    ↓
PHASE 2: LANGGRAPH EXECUTION (Non-Code Workflow)

LangGraph initialized with:
  execution_state.workflow_type = "text_analysis"
  execution_state.mcp_tools_available = {}
  execution_state.retrieval_context = {...sections...}

    ↓
Stage 1: analysis

  AnalysisAgent receives:
    {
      task: "Discuss JWT architecture",
      retrieval_context: {document sections + decision references},
      mcp_tools: {} # Empty
    }

  Agent (no MCP tools available):
    Uses retrieval context directly
    Analyzes architectural decisions
    Generates discussion
    Returns: success

    ↓
WORKFLOW COMPLETE (different from code, no AST/LSP, faster planning)

Key Architectural Insights
Workflow-Aware Specialization (Not Generic)

text
Why This Avoids Generic-ness:

Code Workflows:
  ✅ AST parsing activated (expensive, worth it for code)
  ✅ LSP tools prepared (precise type info)
  ✅ Function-level indexing (not file-level)
  ✅ Security sources available (CVE database)
  → SPECIALIZED for code

Non-Code Workflows:
  ✅ AST parsing skipped (doesn't apply)
  ✅ LSP tools unavailable (no language semantics)
  ✅ Document-level indexing (not function-level)
  ✅ Decision log search available
  → SPECIALIZED for documents

Same Retrieval Agent, completely different behavior
NOT through complex logic, but through CONFIGURATION (TART pattern)

TART Pattern Application

text
Task-Aware Retrieval with Instructions:

Instead of: Retrieval Agent self-classifies workflow type
Do this: Orchestrator decides workflow → passes explicit config

Benefits:
  ✅ Orchestrator (already doing workflow selection) stays responsible
  ✅ Retrieval Agent receives instructions, doesn't self-classify
  ✅ Clear what strategy applies (visible in YAML)
  ✅ Easy to add new workflows (add YAML config, no code changes)
  ✅ Research-backed (TART outperforms generic by 3x)

Performance Impact

text
Code Workflow Planning:
  10s (AST parsing) + 0.4s (reasoning) + 0.6s (retrieval) = 11s

Non-Code Workflow Planning:
  2.8s (document indexing) + 0.4s (reasoning) + 0.4s (retrieval) = 3.6s

Savings by workflow-awareness: 7.4 seconds per non-code task
  No wasted AST parsing for documents
  Simpler indexing (sections vs. functions)

Summary of Integration

This specification incorporates:

✅ Orchestrator Focus: Strategy selection only, no retrieval queries
✅ Workflow-Specific Configuration: TART pattern (explicit instructions, not classification)
✅ Code-Specialized Strategies: AST upfront + LSP on-demand via MCP
✅ Non-Code Support: Document-level retrieval, no static analysis
✅ LangGraph Routing: Deterministic state machine, workflow-aware context
✅ Autonomous Retrieval Agent: Follows config, adapts behavior per workflow
✅ Research-Backed: TART pattern, CodeAgent findings, multi-domain specialization
✅ Modular & Extensible: Add workflows by adding YAML config, no core code changes
✅ Performance Optimized: Skips irrelevant components per workflow type
