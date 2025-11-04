# High-Level Flow Diagrams for Agentic IDE

## FLOW 1: System Architecture Overview (Three Packages)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC IDE SYSTEM ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐
│    PACKAGE 1: GUI CLIENT     │
│    (Rust + Iced)             │
│    Independent Executable    │
└──────────────────────────────┘
         │
         │ HTTP/WebSocket
         ▼
┌──────────────────────────────────────────────────────────────────┐
│               PACKAGE 2: AGENT NETWORK BACKEND                   │
│                  (Python + LangChain + LangGraph)                │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ACP Server (Agent Client Protocol)                    │   │
│  │  - Handles GUI connections                              │   │
│  │  - Manages workflow execution                           │   │
│  │  - Streams callbacks (real-time updates)                │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │              │              │                       │
│           ▼              ▼              ▼                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │Orchestrator  │ │Code Gen Agent│ │Retrieval     │            │
│  │Agent         │ │              │ │Agent         │            │
│  │(Mistral-7B)  │ │(Mistral-7B)  │ │(Autonomous)  │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│           │              │              │                       │
│           └──────────────┴──────────────┘                       │
│                     │                                           │
│                     ▼                                           │
│           ┌─────────────────────┐                              │
│           │   Ollama Server     │                              │
│           │ Async Streaming     │                              │
│           │ (localhost:11434)   │                              │
│           └─────────────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
         ▲
         │ HTTP
         │
┌──────────────────────────────┐
│ PACKAGE 3: VECTOR DATABASE   │
│    (Qdrant)                  │
│    Collections:              │
│  - workspace_files (Phase 1) │
│  - workspace_functions       │
│    (Phase 2 AST)             │
│    (localhost:6333)          │
└──────────────────────────────┘

┌────────────────────────────────┐
│  External Services (via MCP)    │
│  - LSP Servers (Python, Rust,  │
│    JavaScript)                 │
│  - Git CLI                      │
│  - Code Formatters (Black,      │
│    autopep8, prettier)          │
└────────────────────────────────┘
```

---

## FLOW 2: Complete Feature Implementation Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│         FEATURE IMPLEMENTATION: User Request → Code Delivery            │
└─────────────────────────────────────────────────────────────────────────┘

USER INTERACTION PHASE:
━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────────────────┐
│ 1. User Types Feature Request    │
│    "Implement JWT authentication"│
│    in GUI Interaction Window     │
└──────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│ 2. GUI Sends Request via ACP                         │
│    POST /api/workflow/submit                         │
│    {                                                  │
│      workflow_type: "feature_implementation",        │
│      user_query: "Implement JWT auth",               │
│      correlation_id: "req_xyz"                       │
│    }                                                  │
└──────────────────────────────────────────────────────┘
           │
           ▼ (HTTP)
┌──────────────────────────────────────────────────────┐
│ BACKEND PHASE 1: RETRIEVAL                           │
│                                                       │
│ 3a. Autonomous Retrieval Agent                       │
│     - Generates search query from user input         │
│     - "JWT implementation patterns"                  │
│                                                       │
│ 3b. Phase 1 File-Level Retrieval                     │
│     Query Qdrant collection: workspace_files         │
│     Vector search (nomic-embed-text) on CPU          │
│     Filter: exclude tests, max_size 500KB            │
│     Returns: Top 50 files by relevance               │
│     Latency: ~1.5 seconds                            │
│                                                       │
│ 3c. Phase 2 Function-Level AST Extraction            │
│     Selective AST parsing on retrieved files         │
│     Extract functions/classes with signatures        │
│     Cross-encoder reranking (MS-MARCO-MiniLM CPU)    │
│     Returns: Top 20 functions, context ~2500 tokens  │
│     Latency: ~1 second                               │
│                                                       │
│ ✓ Context Ready: ~2500 tokens of relevant code       │
└──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│ BACKEND PHASE 2: PLANNING & WORKFLOW SELECTION       │
│                                                       │
│ 4. Orchestrator Agent (Mistral-7B Q4)                │
│    - Input: User query + retrieved context           │
│    - Reasoning: "This is a new feature implementation"
│    - Decides workflow stages to execute:             │
│      ✓ Code Generation                               │
│      ✓ Test Generation                               │
│      ✗ Security Analysis (not critical for this)     │
│    - Passes: user_query + context to code_gen        │
│    - Latency: ~45 seconds (20-30 tokens)             │
│                                                       │
│ ✓ Workflow Decided                                   │
└──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│ BACKEND PHASE 3: CODE GENERATION                     │
│                                                       │
│ 5. Code Generation Agent (Mistral-7B Q4, same model) │
│    - Ollama: keep_alive="-1" (already loaded)        │
│    - Input: context + specialized prompt             │
│    - Generation via streaming:                       │
│      • Emit token stream to GUI every 5 tokens       │
│      • GUI shows code in real-time (optimistic)      │
│                                                       │
│    Generated output:                                 │
│    ┌───────────────────────────────────┐             │
│    │ def create_jwt_token(payload):    │             │
│    │     secret = os.getenv("JWT_KEY") │             │
│    │     token = jwt.encode(           │             │
│    │         payload, secret,          │             │
│    │         algorithm="HS256"         │             │
│    │     )                             │             │
│    │     return token                  │             │
│    └───────────────────────────────────┘             │
│                                                       │
│ 6. MCP Tool: Black Formatter                         │
│    - Auto-format generated code                      │
│    - LSP Hover: Check types via Python LSP           │
│                                                       │
│ ✓ Formatted Code Ready                               │
│    Latency: ~60 seconds (2000+ tokens)               │
└──────────────────────────────────────────────────────┘
           │
           ├──────────────────────┐
           │                      │
           ▼                      ▼
┌────────────────────┐  ┌──────────────────────┐
│ PHASE 4a:          │  │ PHASE 4b:            │
│ Test Generation    │  │ GUI Display Diff     │
│                    │  │                      │
│ 7. Test Agent      │  │ • Show side-by-side  │
│    Generate tests  │  │   original vs new    │
│    for function    │  │ • Highlight changes  │
│    Latency: ~50s   │  │ • Footer: status bar │
│    Returns:        │  │ • Streaming tokens   │
│    pytest cases    │  │   as they arrive     │
└────────────────────┘  └──────────────────────┘
           │                      ▲
           └──────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│ USER REVIEW PHASE                                    │
│                                                       │
│ 8. User Reviews Generated Code in GUI                │
│    Options:                                          │
│    ┌─────────────────────────────────────────┐      │
│    │ ✓ Accept Changes                        │      │
│    │ ✗ Reject Changes                        │      │
│    │ 💭 Request Modifications (Feedback)     │      │
│    └─────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
           │
           ├─────────────────┬──────────────────┤
           ▼                 ▼                  ▼
      ACCEPT            MODIFICATIONS         REJECT
       │                    │                  │
       ▼                    ▼                  ▼
    Apply to        Restart Workflow      Discard
    Workspace       (Full Pipeline)       Changes
    + Commit        New iteration         │
    to Git          with feedback         │
                    context               ▼
                                      No Action
                                      (Back to IDE)
```

---

## FLOW 3: Real-Time Streaming (ACP Callbacks)

```
┌──────────────────────────────────────────────────────────────────────────┐
│          STREAMING UPDATES: Backend → GUI (Event-Based, No Polling)      │
└──────────────────────────────────────────────────────────────────────────┘

Backend LLM Inference (Ollama Streaming):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Token Stream:  def │ calculate │ _sum │ ( │ a │ , │ b │ ) │ : │ \n
                 T1      T2        T3    T4  T5  T6  T7  T8  T9  T10

Every 5 tokens, emit callback:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

T1-T5:
┌─────────────────────────────────────────┐
│ ACP Callback Event                       │
├─────────────────────────────────────────┤
│ {                                        │
│   "type": "agent_streaming_update",     │
│   "workflow_id": "feature_001",          │
│   "stage_id": "code_generation",         │
│   "partial_result":                      │
│     "def calculate_sum(a, b",            │
│   "tokens_so_far": 5,                    │
│   "is_final": false,                     │
│   "timestamp": 1234567890                │
│ }                                        │
└─────────────────────────────────────────┘
           │
           │ HTTP (event-based, NOT polling)
           ▼
GUI receives callback (Correlation ID req_xyz):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GUI Update (Optimistic Rendering):
┌─────────────────────────────────┐
│ Main Window (Right Pane):       │
│ ┌──────────────────────────┐   │
│ │ def calculate_sum(a, b   │   │  ← Highlight new content
│ │                          │   │
│ │                          │   │
│ └──────────────────────────┘   │
│                                │
│ Footer Status:                 │
│ "Generating... 5 tokens"       │
│ Latency: ~150ms from backend   │
└─────────────────────────────────┘


T6-T10:
Backend emits next callback:
┌─────────────────────────────────────────┐
│ {                                        │
│   "partial_result": "def calculate_sum", │
│     (a, b):",                            │
│   "tokens_so_far": 10,                   │
│   "is_final": false                      │
│ }                                        │
└─────────────────────────────────────────┘
           │
           ▼ (Latency ~100-200ms per callback)
GUI Updates:
┌─────────────────────────────────┐
│ def calculate_sum(a, b):        │
│                                │
│ Footer: "Generating... 10 tok" │
└─────────────────────────────────┘


Final Callback (is_final=true):
┌──────────────────────────────────────────────┐
│ {                                            │
│   "type": "agent_streaming_update",          │
│   "partial_result": "def calculate_sum(a,..  │
│     ...full code...",                        │
│   "tokens_so_far": 78,                       │
│   "is_final": true,                          │
│   "metrics": {                               │
│     "generation_time_sec": 3.5,              │
│     "tokens_per_sec": 22.3                   │
│   }                                          │
│ }                                            │
└──────────────────────────────────────────────┘
           │
           ▼
GUI Final Update + Ready for Review:
┌────────────────────────────────────┐
│ def calculate_sum(a, b):           │
│     return a + b                   │
│                                    │
│ Footer: "✓ Complete (3.5s, 22 tok)"│
│ Buttons: [Accept] [Reject] [Mod]   │
└────────────────────────────────────┘

Total End-to-End Latency: ~3.5 seconds (inference)
                         + 0.1-0.2s per callback (network)
                         = Smooth real-time experience
```

---

## FLOW 4: User Feedback Loop (Iterative Refinement)

```
┌────────────────────────────────────────────────────────────────────────┐
│    USER FEEDBACK: Critique → Restart Workflow → Improved Output        │
└────────────────────────────────────────────────────────────────────────┘

ITERATION 1:
━━━━━━━━━━━

User: "Implement JWT auth"
       │
       ▼ (Full pipeline: Retrieval → Planning → Generation)
Generated Code (v1):
┌─────────────────────────────────────────────────────────────────┐
│ def create_jwt_token(payload):                                  │
│     secret = os.getenv("JWT_KEY")                               │
│     token = jwt.encode(payload, secret, algorithm="HS256")      │
│     return token                                                │
│                                                                 │
│ # No error handling, no expiration!                             │
└─────────────────────────────────────────────────────────────────┘

User Reviews & Provides Feedback:
┌──────────────────────────────────────────────────────────────┐
│ ✗ Reject                                                     │
│                                                              │
│ Critique: "Add token expiration, error handling, and        │
│           validate the payload structure. Also add a        │
│           verification function."                           │
└──────────────────────────────────────────────────────────────┘
           │
           ▼ (Item 15: Restart full workflow, preserve context)

ITERATION 2:
━━━━━━━━━━━

Backend receives user_feedback:
┌──────────────────────────────────────────────────────────┐
│ 1. Restart Pipeline (Orchestrator Phase)                │
│                                                           │
│ 2. Context Preservation:                                │
│    ✓ Reuse retrieved files/functions from Phase 1       │
│    ✗ Reset code generation output                       │
│                                                           │
│ 3. Orchestrator re-analyzes:                            │
│    - Original query: "Implement JWT auth"               │
│    - User feedback: "Add expiration, error handling,    │
│      validation, verification function"                  │
│    - Enhanced reasoning: "Need production-grade JWT     │
│      with error handling, expiration, and validation"   │
│                                                           │
│ 4. Re-route to code_generation with new context        │
└──────────────────────────────────────────────────────────┘
           │
           ▼

Generated Code (v2):
┌──────────────────────────────────────────────────────────────┐
│ import jwt                                                    │
│ from datetime import datetime, timedelta                     │
│ from typing import Optional, Dict                            │
│                                                              │
│ def create_jwt_token(payload: Dict, expires_in: int = 3600):│
│     try:                                                     │
│         secret = os.getenv("JWT_KEY")                        │
│         if not secret:                                       │
│             raise ValueError("JWT_KEY not configured")       │
│         if not isinstance(payload, dict):                    │
│             raise TypeError("Payload must be a dict")        │
│                                                              │
│         payload["exp"] = datetime.utcnow() +                 │
│                          timedelta(seconds=expires_in)       │
│         token = jwt.encode(payload, secret,                  │
│                           algorithm="HS256")                 │
│         return token                                         │
│     except Exception as e:                                   │
│         raise JWTError(f"Token creation failed: {e}")        │
│                                                              │
│ def verify_jwt_token(token: str) -> Optional[Dict]:         │
│     try:                                                     │
│         secret = os.getenv("JWT_KEY")                        │
│         payload = jwt.decode(token, secret,                  │
│                             algorithms=["HS256"])            │
│         return payload                                       │
│     except jwt.ExpiredSignatureError:                        │
│         raise JWTError("Token has expired")                  │
│     except jwt.InvalidTokenError:                            │
│         raise JWTError("Invalid token")                      │
└──────────────────────────────────────────────────────────────┘

User Reviews (v2):
┌──────────────────────────────────────────────────────────┐
│ ✓ Accept Changes                                         │
└──────────────────────────────────────────────────────────┘
           │
           ▼

Apply to Workspace + Commit to Git:
┌──────────────────────────────────────────────────────────┐
│ File: src/auth/jwt_handler.py (new)                      │
│ Action: CREATE (with generated code)                     │
│                                                          │
│ Git Commit:                                              │
│ "feat: Implement JWT authentication with expiration"     │
│ "- Add token creation with expiration handling"          │
│ "- Add token verification with error handling"           │
│ "- Add payload validation"                               │
│ "- Generated via Agentic IDE"                            │
└──────────────────────────────────────────────────────────┘

SUMMARY:
━━━━━━

Iteration 1: 
  Phase 1 Retrieval: 2.5s → Context ready
  Phase 2 Planning: 45s → Workflow decided
  Phase 3 Code Gen: 60s → Basic code
  Total: ~3-4 min

User Feedback: v1 → v2 critique

Iteration 2:
  Phase 1 Retrieval: REUSED (0s)
  Phase 2 Planning: 45s → Enhanced route
  Phase 3 Code Gen: 80s → Production code
  Total: ~2-2.5 min (faster, reused context)

Total Time: ~5-6 minutes for production-quality code
```

---

## FLOW 5: Agent Failure & Retry (Orchestrator Decision Making)

```
┌───────────────────────────────────────────────────────────────────┐
│         AGENT FAILURE DETECTION & ADAPTIVE RETRIEVAL              │
└───────────────────────────────────────────────────────────────────┘

SCENARIO: Code Generation Produces Syntax Errors
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent Output:
┌────────────────────────────────────┐
│ def my_function():                 │
│     x = [1, 2, 3                   │  ← Missing closing bracket!
│     return x                       │
│                                    │
│ failure_detector():                │
│   return {                         │
│     "is_failed": True,             │
│     "reason": "SyntaxError",       │
│     "details": "Line 2: unclosed"  │
│   }                                │
└────────────────────────────────────┘
           │
           ▼
Orchestrator Receives Failure:
┌────────────────────────────────────────────────────────┐
│ Check failure_info from code_gen agent                │
│ "is_failed": True                                      │
│                                                        │
│ Decision Logic:                                        │
│ IF failed AND attempts < max_attempts:                │
│     activate_adaptive_retrieval()                      │
│ ELSE:                                                  │
│     return_error_to_user()                             │
│                                                        │
│ Current: attempts = 1, max_attempts = 3               │
│ Decision: ACTIVATE ADAPTIVE RETRIEVAL                 │
└────────────────────────────────────────────────────────┘
           │
           ▼
Adaptive Retrieval (Item 9 from spec):
┌────────────────────────────────────────────────────────┐
│ Use failure info to refine retrieval:                  │
│                                                        │
│ Original query: "Implement function"                  │
│ Failure type: "SyntaxError"                            │
│ Enhanced query: "Implement function with correct      │
│                 Python syntax"                         │
│                                                        │
│ New retrieval with modified reasoning_guidance:       │
│ "Task: Fix syntax error, focus on bracket matching"   │
│                                                        │
│ Phase 1: Re-retrieve files with syntax emphasis       │
│ Phase 2: Re-extract functions with correct syntax     │
│          (filter examples with syntax errors)         │
│                                                        │
│ New context: ~2000 tokens (more syntax examples)      │
└────────────────────────────────────────────────────────┘
           │
           ▼
Re-run Code Generation (Attempt 2):
┌────────────────────────────────────┐
│ def my_function():                 │
│     x = [1, 2, 3]  ← Now correct!  │
│     return x                       │
│                                    │
│ failure_detector():                │
│   return {                         │
│     "is_failed": False,            │
│     "reason": "Success"            │
│   }                                │
└────────────────────────────────────┘
           │
           ▼
Proceed to Next Stage (Tests, etc.)
OR
Return Success to User


RETRY LOOP VISUALIZATION:
━━━━━━━━━━━━━━━━━━━━━━━

Attempt 1: Syntax Error ──┐
                          ├──→ Orchestrator Decision ──→ Adaptive Retrieval
Attempt 2: Success! ←─────┘

Attempt 1: Bad logic ──┐
Attempt 2: Bad logic  ├──→ Adaptive Retrieval (improved query)
Attempt 3: Success! ←─┘

Attempt 1: Failed ──┐
Attempt 2: Failed  ├──→ Max retries exceeded
Attempt 3: Failed  │
                   └──→ Return Error to User
```

---

## FLOW 6: Hybrid Search (Semantic + Keyword)

```
┌──────────────────────────────────────────────────────────────────┐
│    TWO-PHASE RETRIEVAL WITH HYBRID SEARCH (Item 19)             │
└──────────────────────────────────────────────────────────────────┘

PHASE 1: FILE-LEVEL RETRIEVAL (Hybrid)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User Query: "Implement rate limiting middleware"

Step 1a: Semantic Search (Dense Vectors)
┌────────────────────────────────────────────────────────┐
│ Embedding Model: nomic-embed-text-v1.5 (CPU)          │
│ Query Vector: embed("rate limiting middleware")        │
│                                                         │
│ Qdrant Dense Vector Search:                            │
│ - Collection: workspace_files                          │
│ - Vector field: file_embedding                         │
│ - Top-k: 50                                            │
│ - Distance: Cosine                                     │
│ - Results:                                             │
│   1. auth/middleware.py (0.89)  ← Highest relevance   │
│   2. api/rate_limiter.py (0.87)                       │
│   3. config/limits.py (0.82)                          │
│   ...                                                  │
│   50. utils/logging.py (0.45)                         │
│                                                         │
│ Latency: ~800ms                                        │
└────────────────────────────────────────────────────────┘

Step 1b: Keyword Search (Sparse Vectors via BM25)
┌────────────────────────────────────────────────────────┐
│ BM25 Sparse Vector Search:                             │
│ - Query terms: ["rate", "limiting", "middleware"]      │
│ - BM25 params: k1=1.5, b=0.75                         │
│ - Results:                                             │
│   1. api/rate_limiter.py (BM25 score: 8.5)           │
│   2. tests/rate_limiter_test.py (7.2)                │
│   3. middleware.py (6.8)                              │
│   ...                                                  │
│                                                         │
│ Latency: ~200ms                                        │
└────────────────────────────────────────────────────────┘

Step 1c: Hybrid Fusion (Combine Both)
┌────────────────────────────────────────────────────────┐
│ Fusion Strategy:                                        │
│ hybrid_score = 0.7 * semantic_score +                 │
│                0.3 * keyword_score                     │
│                                                         │
│ Normalized Results:                                    │
│ 1. auth/middleware.py                                 │
│    semantic: 0.89 (rank 1) → 1.0 normalized          │
│    keyword: 0.68 (rank 3) → 0.6 normalized           │
│    hybrid = 0.7 * 1.0 + 0.3 * 0.6 = 0.88            │
│                                                         │
│ 2. api/rate_limiter.py                               │
│    semantic: 0.87 (rank 2) → 0.98 normalized         │
│    keyword: 0.85 (rank 1) → 1.0 normalized           │
│    hybrid = 0.7 * 0.98 + 0.3 * 1.0 = 0.986 ← Winner! │
│                                                         │
│ Final Hybrid Ranking:                                  │
│ 1. api/rate_limiter.py (0.986)                        │
│ 2. auth/middleware.py (0.88)                          │
│ 3. config/limits.py (0.75)                            │
│ ...                                                    │
│ 50. utils/logging.py (0.42)                           │
│                                                         │
│ Total Phase 1 Latency: ~1.5 seconds                   │
└────────────────────────────────────────────────────────┘

PHASE 2: FUNCTION-LEVEL AST RETRIEVAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From Phase 1 files, extract functions via AST:

Step 2a: Selective AST Parsing
┌────────────────────────────────────────────────────────┐
│ Parse top Phase 1 files (max 50 files)                │
│ Extract:                                               │
│   - Functions with docstrings mentioning "rate"       │
│   - Classes with "Limiter" in name                    │
│   - Methods that return/check limits                  │
│                                                         │
│ From api/rate_limiter.py:                             │
│   1. class RateLimiter                                │
│   2. def apply_rate_limit(user_id, limit)            │
│   3. def check_quota(user_id)                         │
│   4. def reset_counters()                             │
│                                                         │
│ From auth/middleware.py:                              │
│   1. def rate_limit_middleware(request)              │
│   2. def get_user_rate_limit(user_id)                │
│                                                         │
│ ~20-30 functions extracted                            │
│ Latency: ~600ms                                       │
└────────────────────────────────────────────────────────┘

Step 2b: Semantic Re-ranking (Cross-Encoder)
┌────────────────────────────────────────────────────────┐
│ Model: ms-marco-MiniLM-L12-v2 (CPU)                   │
│                                                         │
│ Score each function pair:                              │
│ Query vs Function Signature + Docstring                │
│                                                         │
│ Scores:                                                │
│ 1. class RateLimiter (0.92) ← Most relevant           │
│ 2. def apply_rate_limit() (0.89)                      │
│ 3. def rate_limit_middleware() (0.85)                 │
│ 4. def check_quota() (0.78)                           │
│ ...                                                    │
│ 28. def reset_counters() (0.52)                       │
│                                                         │
│ Keep Top-20 functions                                 │
│ Latency: ~400ms                                       │
└────────────────────────────────────────────────────────┘

Step 2c: Deduplication (Semantic)
┌────────────────────────────────────────────────────────┐
│ Remove redundant functions:                            │
│ - apply_rate_limit() and check_quota() both check    │
│   limits, keep apply_rate_limit() (higher score)      │
│                                                         │
│ Final context: 15-18 functions, ~2500 tokens          │
│ Latency: ~100ms                                       │
└────────────────────────────────────────────────────────┘

TOTAL PHASE 1 + 2 LATENCY: ~3 seconds
═══════════════════════════════════════

Result Quality Improvement:
Semantic Only (Phase 1 naive):    Precision 0.65
+ Keyword (Hybrid):               Precision 0.78
+ Function Reranking:             Precision 0.88 ← 35% better!
```

---

## FLOW 7: Model Loading & VRAM Management

```
┌──────────────────────────────────────────────────────────────────┐
│     MODEL LOADING STRATEGY: Persistent Orchestrator + Workers    │
└──────────────────────────────────────────────────────────────────┘

STARTUP PHASE:
━━━━━━━━━━━━━

Backend Boot:
    ↓
┌──────────────────────────────────────────────────────┐
│ 1. Init Ollama Connection (http://localhost:11434)   │
│    Check if Ollama is running                        │
│    if not: raise error, guide user to start Ollama  │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 2. Pre-load Orchestrator Model                       │
│    Endpoint: POST /api/generate                      │
│    Model: mistral-7b-instruct-v0.3                   │
│    Quantization: Q4_K_M                              │
│    keep_alive: "-1"  (indefinite VRAM persistence)   │
│    Warm-up: Generate 1 token to load model          │
│                                                       │
│    Response:                                         │
│    ✓ Model loaded, VRAM: 4.2GB                      │
│    ✓ Latency: 8-10 seconds (one-time only)          │
└──────────────────────────────────────────────────────┘
    ↓
Orchestrator ALWAYS LOADED ═════════════════════════


DURING WORKFLOW EXECUTION:
━━━━━━━━━━━━━━━━━━━━━━

Retrieval Phase (CPU-bound, GPU free):
┌──────────────────────────────────────────┐
│ GPU VRAM State: 4.2GB (Orchestrator)     │
│                                           │
│ Embedding: CPU (no GPU)                  │
│ Reranker: CPU (no GPU)                   │
│                                           │
│ GPU Available: 16GB - 4.2GB = 11.8GB     │
│ Safe buffer: 1-2GB                       │
│ Current Load: ~26% of GPU                │
└──────────────────────────────────────────┘

Planning Phase (Orchestrator):
┌──────────────────────────────────────────┐
│ GPU VRAM State: 4.2GB (Orchestrator)     │
│ Keep model in VRAM                       │
│ Process: Route to next stage             │
│ Latency: 45 seconds                      │
└──────────────────────────────────────────┘

Code Generation Phase (Worker Model):
┌──────────────────────────────────────────┐
│ Option A: REUSE Orchestrator             │
│   VRAM: 4.2GB (no change)                │
│   Latency: 0s (no reload)                │
│   Quality: Good (same Mistral-7B)        │
│   Recommended ✓                          │
│                                           │
│ Option B: LOAD Different Model           │
│   Unload Orchestrator: -4.2GB            │
│   Load CodeLlama-7B: +4.2GB              │
│   Latency: 5-7s (reload)                 │
│   Quality: Excellent (CodeLlama)         │
│   Cost: Extra reload latency             │
│                                           │
│ Decision: Use Option A for speed         │
│   If time permits: Can use Option B      │
└──────────────────────────────────────────┘

After Code Generation:
┌──────────────────────────────────────────┐
│ GPU VRAM State: 4.2GB (Mistral still)    │
│ (Model remains, keep_alive="-1")         │
└──────────────────────────────────────────┘

Test Generation Phase (Same Model):
┌──────────────────────────────────────────┐
│ GPU VRAM State: 4.2GB                    │
│ Reuse Mistral for test generation        │
│ Latency: ~50 seconds                     │
└──────────────────────────────────────────┘

After Test Generation:
┌──────────────────────────────────────────┐
│ GPU VRAM State: 4.2GB (Mistral persists) │
│ Ready for next user query                │
│ No reload needed!                        │
└──────────────────────────────────────────┘


VRAM OVER TIME:
━━━━━━━━━━━━━

VRAM Usage (MB)
│
│  5000 ─┐
│        │ ┌─── Orchestrator loaded (persistent)
│        │ │
│  4500 ─┼─┤
│        │ │
│  4000 ─┤ │
│        │ │ (stays loaded for all phases)
│  3500 ─┤ │
│        │ │
│  3000 ─┤ │
│        │ │
│  2500 ─┤ │
│        │ │
│  2000 ─┤ │
│        │ │
│  1500 ─┤ │
│        │ │
│  1000 ─┤ │
│        │ │
│   500 ─┤ │
│        │ │
│     0 ─┴─┴──────────────────────────────── Time
│           Phase1  Phase2  Phase3  Phase4
│        Retrieval  Plan    CodeGen  Test
│

Key: Model stays loaded, zero unload/reload cycles!


MONITORING & ALERTS:
━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────┐
│ /debug/vram endpoint provides:              │
│                                              │
│ {                                            │
│   "vram_used_mb": 4234,                     │
│   "vram_available_mb": 11766,               │
│   "percentage": 26.5,                       │
│   "peak_mb": 4234,                          │
│   "components": {                           │
│     "mistral_7b": 4200,                     │
│     "gui": 34                               │
│   }                                          │
│ }                                            │
│                                              │
│ Alert thresholds:                           │
│ - Warning: > 70% (11.2GB)                   │
│ - Critical: > 90% (14.4GB)                  │
└─────────────────────────────────────────────┘
```

---

## FLOW 8: Package Deployment (Nix Flakes - Separate Processes)

```
┌─────────────────────────────────────────────────────────────────┐
│     DEPLOYMENT: Three Independent Packages via Nix Flakes       │
└─────────────────────────────────────────────────────────────────┘

flake.nix Structure:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│ flake {                                                         │
│   outputs = { self, nixpkgs, ... }:                            │
│                                                                 │
│   packages.x86_64-linux = {                                    │
│     agentic-ide-gui = <GUI Package>                            │
│     agentic-ide-backend = <Backend Package>                    │
│     agentic-ide-vectordb = <VectorDB Package>                  │
│   };                                                           │
│                                                                 │
│ }                                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Runtime Start-Up Flow:
━━━━━━━━━━━━━━━━━━━

Terminal 1: Start Vector Database
┌──────────────────────────────────┐
│ $ nix run .#agentic-ide-vectordb │
│                                   │
│ Starting Qdrant server            │
│ Listening on: http://localhost:6333
│ Health check: ✓ OK                │
│ ✓ Ready                           │
└──────────────────────────────────┘


Terminal 2: Start Backend (Agent Network)
┌──────────────────────────────────┐
│ $ nix run .#agentic-ide-backend  │
│                                   │
│ Connecting to Qdrant...           │
│ ✓ Connected to localhost:6333    │
│                                   │
│ Initializing Ollama...            │
│ Checking http://localhost:11434  │
│ ✓ Ollama ready                   │
│                                   │
│ Pre-loading Mistral-7B...         │
│ ✓ Model loaded (4.2GB VRAM)      │
│                                   │
│ Starting ACP Server...            │
│ Listening on: http://localhost:8000
│ Endpoints:                        │
│   POST /api/workflow/submit       │
│   GET  /api/workflow/{id}/stream  │
│   GET  /debug/metrics             │
│   GET  /debug/vram                │
│ ✓ Backend ready                  │
└──────────────────────────────────┘


Terminal 3: Start GUI Client
┌──────────────────────────────────┐
│ $ nix run .#agentic-ide-gui      │
│                                   │
│ Reading config/gui_config.yaml    │
│ Backend endpoint: localhost:8000  │
│ VectorDB endpoint: localhost:6333 │
│                                   │
│ Connecting to backend...          │
│ ✓ Connected                       │
│                                   │
│ Checking version compatibility:   │
│ GUI: 1.0                          │
│ Backend: 1.0                      │
│ ✓ Compatible                      │
│                                   │
│ GUI Window Opens                  │
│ ┌────────────────────────────────┐│
│ │ Agentic IDE v1.0               ││
│ │                                ││
│ │ [Interaction Window]           ││
│ │ "Enter feature request..."     ││
│ │                                ││
│ │ [Main Diff View]               ││
│ │ (awaiting input)               ││
│ │                                ││
│ │ Footer: ✓ Backend ready        ││
│ │         ✓ Database ready       ││
│ └────────────────────────────────┘│
│ ✓ GUI ready                       │
└──────────────────────────────────┘


INTER-PROCESS COMMUNICATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━

         GUI                Backend              VectorDB
       (Rust)           (Python)               (Qdrant)
         │                  │                     │
         │  HTTP            │                     │
         ├─────────────────→ │                     │
         │  /api/workflow    │                     │
         │  submit           │                     │
         │                   │  HTTP              │
         │                   ├────────────────────→
         │                   │  /search query     │
         │                   │  retrieve files    │
         │                   │                     │
         │                   │  JSON response     │
         │  ACP Callback     │ ←────────────────────
         │  (streaming)      │  (file results)     │
         │ ←───────────────────                     │
         │  /api/.../stream  │                     │
         │  token: "def"     │                     │
         │  token: "foo"     │                     │
         │  token: "("...    │  (Ollama queries   │
         │                   │   happen locally   │
         │                   │   via stdio, not   │
         │                   │   over network)    │
         │                   │                     │
         │  Final result     │                     │
         │ ←──────────────────                     │
         │                   │                     │

Key: Each package is independent process
     GUI ← → Backend ← → VectorDB
     Packages can be updated/restarted independently


NEVERUP STATUS CHECK:
━━━━━━━━━━━━━━━━━━

All processes running:
┌──────────────────────────────────────────┐
│ $ pgrep -f nix.*agentic-ide              │
│                                           │
│ 2847  /nix/.../bin/qdrant ...            │
│ 2948  python3 -m backend.main ...        │
│ 3051  /nix/.../bin/agentic-ide-gui ...   │
│                                           │
│ ✓ All 3 processes active                 │
└──────────────────────────────────────────┘


STOPPING SERVICES:
━━━━━━━━━━━━━━━━━

Method 1: Kill each terminal
$ Ctrl+C (in each terminal)

Method 2: Create systemd units (optional)
$ nix develop  # Then use systemctl


STATE ACROSS RESTARTS:
━━━━━━━━━━━━━━━━━━━━

Qdrant: Persists data to disk
        Files: ~/.local/share/qdrant/

Backend: Restarts fresh, reloads model
         LangGraph checkpoints persisted to disk
         (Location: config/checkpoints/)

GUI: Restarts fresh, reconnects to backend
     No local state lost (backend has it)

Result: Services can be restarted anytime
        All data persisted, workflows resumable
```

---

## SUMMARY TABLE: All Flows

| Flow | Use Case | Key Components | Duration | Status |
|------|----------|---|---|---|
| Flow 1 | System Architecture | GUI ↔ Backend ↔ VectorDB | — | Overview |
| Flow 2 | Feature Implementation | 4-stage workflow | 3-8 min | Main |
| Flow 3 | Real-Time Streaming | ACP callbacks | ~100-200ms/cb | Live |
| Flow 4 | User Feedback | Iterative refinement | 2-6 min/iter | Refinement |
| Flow 5 | Agent Failure | Retry + adaptive retrieval | 30-120 sec | Recovery |
| Flow 6 | Hybrid Search | Semantic + keyword | ~3 sec | Retrieval |
| Flow 7 | Model Loading | Persistent orchestrator | ~4.2GB VRAM | Optimization |
| Flow 8 | Deployment | 3-package Nix setup | — | DevOps |

