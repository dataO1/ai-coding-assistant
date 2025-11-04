# DETAILED FLOW DIAGRAMS: Server & UI Architecture

**Complete Request/Response & State Flows**

---

## FLOW 1: Complete Workflow Execution (Server-Side State Machine)

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER SUBMITS WORKFLOW                        │
│  GUI → POST /api/workflow/submit with complete config payload   │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ API GATEWAY: Request Validation & Initialization               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Validate schema (workflow_config, agents_config, etc)       │
│ 2. Check workspace_id is valid                                 │
│ 3. Verify version compatibility                                │
│ 4. Generate execution_id & correlation_id                      │
│ 5. Create LangGraph WorkflowState                               │
│ 6. Return: {execution_id, streaming_url}                       │
│                                                                 │
│ Response: 202 Accepted                                         │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ LANGGRAPH STATE MACHINE: Begin Execution                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ START → orchestrator_node                                       │
│   ├─ Input: user_query + workspace_context                     │
│   ├─ LLM: Route to workflow type                               │
│   ├─ Set state.current_stage = first_stage_from_workflow      │
│   ├─ Emit: status_update("Orchestrator routing...")           │
│   └─ Output: state with selected_workflow                      │
│                                                                 │
│ LOOP: For Each Enabled Stage                                   │
│   │                                                             │
│   ├─ retrieval_node                                            │
│   │  ├─ Input: state.current_stage                            │
│   │  ├─ Load agent's retrieval_needs                          │
│   │  ├─ Load workspace config from working_dir                │
│   │  ├─ Check retrieval.enabled                                │
│   │  ├─ Execute Phase 1: file-level semantic search           │
│   │  ├─ Execute Phase 2: function-level AST + reranking       │
│   │  ├─ Check cache (key: query + workspace_id + stage_id)    │
│   │  ├─ Emit: status_update("Retrieving context...")         │
│   │  └─ Output: state.retrieved_context                        │
│   │                                                             │
│   ├─ execution_node                                            │
│   │  ├─ Input: state.retrieved_context + user_query           │
│   │  ├─ Load specialist agent (Code Gen / Test Gen / etc)      │
│   │  ├─ Agent executes LLM inference                           │
│   │  ├─ Extract SUMMARY line from agent output                │
│   │  ├─ Run failure_detector (is_failed boolean)              │
│   │  ├─ Emit: status_update("Generating code... 60%")        │
│   │  └─ Output: state.stage_results[stage_id]                 │
│   │                                                             │
│   ├─ CONDITIONAL EDGE: Check failure_detector                 │
│   │  │                                                          │
│   │  ├─ If is_failed=false                                     │
│   │  │  └─ Continue to git_commit                              │
│   │  │                                                          │
│   │  ├─ If is_failed=true && attempt < 3                      │
│   │  │  │                                                       │
│   │  │  └─ adaptive_retrieval_node                             │
│   │  │     ├─ Enhanced query: original + failure_reason       │
│   │  │     ├─ Re-execute retrieval with enriched context      │
│   │  │     ├─ Retry execution_node (same stage)               │
│   │  │     └─ Emit: status_update("Retrying with context...")│
│   │  │                                                          │
│   │  └─ If is_failed=true && attempt >= 3                     │
│   │     └─ error_node: Return error to user                   │
│   │                                                             │
│   ├─ git_commit_node                                           │
│   │  ├─ Extract SUMMARY from agent output                      │
│   │  ├─ Determine commit message prefix (feat:/test:/etc)     │
│   │  ├─ Write generated files to workspace working_dir        │
│   │  ├─ Scope: Only within working_dir (security)             │
│   │  ├─ Git: Stage files → Commit                              │
│   │  ├─ Get commit_id, add to state.commits[]                 │
│   │  └─ Emit: status_update("Committed {agent_name}")         │
│   │                                                             │
│   └─ LOOP DECISION: Next stage or aggregation?                │
│      ├─ If more stages enabled: Set state.current_stage = next
│      │  └─ Loop back to retrieval_node                         │
│      └─ If no more stages: Continue to aggregation             │
│                                                                 │
│ aggregation_node                                                │
│  ├─ Collect all commits from state.commits[]                   │
│  ├─ Generate metadata:                                         │
│  │  ├─ Total files changed                                     │
│  │  ├─ Total additions/deletions                              │
│  │  └─ Per-commit stats                                        │
│  ├─ Emit: workflow_complete(commits_metadata)                 │
│  └─ Do NOT send code content, only metadata                   │
│                                                                 │
│ END: State machine completes                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ ACP STREAMING: Emit Events to GUI                              │
├─────────────────────────────────────────────────────────────────┤
│ All status_update() calls stream to GUI via WebSocket:         │
│                                                                 │
│ {type: "status_update", stage_id, status, progress, metrics}  │
│ {type: "workflow_complete", commits, total_changes}           │
│ {type: "error", error_code, message}                          │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ GUI: User Reviews Diff & Decides                               │
├─────────────────────────────────────────────────────────────────┤
│ ✓ Accept → POST /api/workflow/{execution_id}/apply            │
│   └─ Backend: Merge branch to main                             │
│                                                                 │
│ ✗ Reject → POST /api/workflow/{execution_id}/discard          │
│   └─ Backend: Delete branch, no changes applied                │
│                                                                 │
│ 📝 Feedback → POST /api/workflow/{execution_id}/restart        │
│   └─ Backend: Loop back to orchestrator with feedback context  │
└─────────────────────────────────────────────────────────────────┘
```

---

## FLOW 2: Failure & Adaptive Retrieval (Detailed)

```
Agent Execution
    │
    ▼
┌─────────────────────────────┐
│ Failure Detector            │
├─────────────────────────────┤
│ Check: is_failed boolean    │
│ Check: failure_info dict    │
│ Example: {                  │
│   is_failed: True,          │
│   reason: "SyntaxError",    │
│   details: "line 5: ..."    │
│ }                           │
└──┬────────────────────────┬─┘
   │ is_failed=False        │ is_failed=True
   │                        │
   ▼                        ▼
┌──────────────┐      ┌──────────────────┐
│ Success!     │      │ Retry Count?     │
│ Continue to  │      └──┬─────────────┬─┘
│ git_commit   │         │             │
└──────────────┘    attempt<3      attempt>=3
                     │                 │
                     ▼                 ▼
              ┌────────────────┐  ┌──────────────┐
              │ Adaptive       │  │ Error Return │
              │ Retrieval      │  │ to User      │
              └────┬───────────┘  └──────────────┘
                   │
┌──────────────────┴─────────────────────────────┐
│ Enhanced Retrieval Process                     │
├───────────────────────────────────────────────┤
│                                               │
│ Enrichment Context:                          │
│  {                                            │
│    "original_query": "Implement JWT",        │
│    "failure_reason": "SyntaxError in line 5",│
│    "failed_code_snippet": "def create_jwt..." │
│  }                                            │
│                                               │
│ New Query to Qdrant:                         │
│  "JWT implementation avoiding SyntaxError    │
│   with proper Python syntax"                 │
│                                               │
│ Phase 1: File-level (with semantic boost)   │
│  ├─ keyword: "syntax", "error handling"     │
│  └─ top_k: 50 (same as before)              │
│                                               │
│ Phase 2: Function-level (reranked)          │
│  ├─ Focus on examples with good syntax      │
│  └─ Avoid files that failed before          │
│                                               │
│ Result: Enhanced context_2                   │
│  (More syntax-focused, error examples)       │
│                                               │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
            ┌─────────────────────────┐
            │ Retry Same Agent        │
            │ Input: enhanced_context │
            │                         │
            │ Output: code v2         │
            │ SUMMARY: v2             │
            └──┬────────────┬─────────┘
               │            │
           Success       Failure Again
               │            │
               ▼            ▼
           Commit        Return Error
           to Git        to User
               │            │
               └────┬───────┘
                    ▼
         Ready for git_commit_node
         (or error_node if max retries)
```

---

## FLOW 3: GUI Lifecycle & State Management

```
┌────────────────────────────────────────────┐
│ APPLICATION START                          │
├────────────────────────────────────────────┤
│ 1. Iced app initializes                    │
│ 2. Load config/ files from GUI's config dir│
│ 3. Parse YAML (agents, workflows, etc)     │
│ 4. Show: "Select Workspace" screen         │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ USER OPENS WORKSPACE                       │
├────────────────────────────────────────────┤
│ Message: WorkspaceSelected(path)           │
│ State Update:                              │
│  ├─ state.current_workspace = context      │
│  ├─ Load .agentic-ide/config.yaml          │
│  └─ state.workspace_config = config        │
│                                            │
│ UI Renders: Workflow selector + input      │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ USER FILLS IN WORKFLOW DETAILS             │
├────────────────────────────────────────────┤
│ Message: WorkflowSelected(workflow_type)   │
│ Message: QueryInput(text)                  │
│                                            │
│ State Update:                              │
│  ├─ state.selected_workflow = type         │
│  └─ state.user_query = text                │
│                                            │
│ UI Enables: Submit button                  │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ USER SUBMITS WORKFLOW                      │
├────────────────────────────────────────────┤
│ Message: SubmitWorkflow                    │
│                                            │
│ Update Function:                           │
│  1. Build WorkflowSubmitRequest            │
│  2. Set state.is_loading = True            │
│  3. Return Command::perform(async submit)  │
│                                            │
│ UI Shows: Loading indicator                │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ ASYNC: Submit HTTP Request                 │
├────────────────────────────────────────────┤
│ ApiClient::submit_workflow()               │
│  ├─ POST /api/workflow/submit              │
│  ├─ Payload: complete configs              │
│  └─ Return: execution_id + streaming_url   │
│                                            │
│ Message: WorkflowSubmitted(result)         │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ OPEN WEBSOCKET STREAM                      │
├────────────────────────────────────────────┤
│ Message: WorkflowSubmitted(Ok(response))   │
│                                            │
│ Update Function:                           │
│  1. Store execution_id                     │
│  2. Extract streaming_url                  │
│  3. Return Command::perform(connect WS)    │
│                                            │
│ UI Shows: "Connecting to stream..."        │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ ASYNC: Connect WebSocket                   │
├────────────────────────────────────────────┤
│ StreamHandler::connect(streaming_url)      │
│  ├─ tokio_tungstenite::connect_async()     │
│  ├─ WebSocket established                  │
│  └─ Spawn message reader task              │
│                                            │
│ Message: StreamConnected(ws_stream)        │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ REAL-TIME UPDATE LOOP                      │
├────────────────────────────────────────────┤
│ Backend sends stream of updates:           │
│                                            │
│ 1. {type: "status_update",                 │
│     stage: "orchestrator",                 │
│     status: "Routing..."}                  │
│                                            │
│    Message: StreamMessage(update)          │
│    Update: state.latest_update = update    │
│    UI renders: Footer shows status         │
│                                            │
│ 2. {type: "status_update",                 │
│     stage: "retrieval",                    │
│     status: "Retrieving context...",       │
│     progress: "45%"}                       │
│                                            │
│    Message: StreamMessage(update)          │
│    Update: state.latest_update = update    │
│    UI renders: Progress bar                │
│                                            │
│ 3. {type: "status_update",                 │
│     stage: "code_generation",              │
│     status: "Generating code...",          │
│     progress: "70%",                       │
│     metrics: {tokens_per_sec: 22}}         │
│                                            │
│    Message: StreamMessage(update)          │
│    Update: state.latest_update = update    │
│    UI renders: Metrics display             │
│                                            │
│ 4. {type: "workflow_complete",             │
│     commits: [...],                        │
│     total_changes: {...}}                  │
│                                            │
│    Message: WorkflowComplete               │
│    Update:                                 │
│     ├─ state.diff_view.commits = commits   │
│     ├─ state.is_loading = False            │
│     └─ Display diff view                   │
│                                            │
│ LOOP continues until workflow_complete     │
│                                            │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ DISPLAY HIERARCHICAL DIFF VIEW             │
├────────────────────────────────────────────┤
│ Level 1: Commits Summary                   │
│  ├─ Commit 1: "feat: JWT auth"             │
│  │  ├─ Files: 1, +142, -0                  │
│  │  └─ [▶ Expand] [✓] [✗] [💬]            │
│  │                                         │
│  └─ Commit 2: "test: JWT tests"            │
│     ├─ Files: 1, +85, -0                   │
│     └─ [▶ Expand] [✓] [✗] [💬]            │
│                                            │
│ User Interaction: Toggle expand             │
│  Message: ToggleCommit(commit_id)          │
│  Update: Add to state.expanded_commits     │
│  UI renders: Files for this commit         │
│                                            │
│ Level 2: Files in Commit (if expanded)     │
│  ├─ src/auth/jwt_handler.py                │
│  │  ├─ Status: ✨ Created                  │
│  │  ├─ +142 lines                          │
│  │  └─ [▶ Show hunks]                      │
│  │                                         │
│  └─ [Action buttons per file]              │
│                                            │
│ Level 3: Hunks (if expanded)               │
│  ├─ Hunk 1: "Adds create_jwt_token()"      │
│  │  ├─ Lines 1-25                          │
│  │  └─ [▶ Show code]                       │
│  │                                         │
│  └─ Hunk 2: "Adds verify_jwt_token()"      │
│     ├─ Lines 27-50                         │
│     └─ [▶ Show code]                       │
│                                            │
│ Level 4: Code (if user clicks "Show")      │
│  Message: ToggleHunk(hunk_id)              │
│  Async: GET /api/workflow/{id}/commit/diff │
│  Message: DiffLoaded(diff_content)         │
│  Update:                                   │
│   ├─ state.loaded_diffs[key] = content     │
│   └─ Cache the diff                        │
│  UI renders: Actual code with syntax hl    │
│                                            │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ USER PROVIDES FEEDBACK                     │
├────────────────────────────────────────────┤
│ Option 1: ✓ ACCEPT ALL                     │
│  Message: AcceptAll                        │
│  Async: POST /api/workflow/{id}/apply      │
│  Backend: Merge branch                     │
│  UI shows: "✓ Changes applied"             │
│                                            │
│ Option 2: ✗ REJECT ALL                     │
│  Message: RejectAll                        │
│  Async: POST /api/workflow/{id}/discard    │
│  Backend: Delete branch                    │
│  UI shows: "✗ Changes discarded"           │
│                                            │
│ Option 3: 📝 FEEDBACK (selective)          │
│  Message: ToggleFile(...) for selective    │
│  Then: SubmitFeedback(critique)            │
│  Async: POST /api/workflow/{id}/restart    │
│  Backend: Restart with feedback context    │
│  Loop: Goto REAL-TIME UPDATE LOOP          │
│                                            │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ WORKFLOW COMPLETE                          │
├────────────────────────────────────────────┤
│ Changes applied / Discarded / Restarting   │
│                                            │
│ UI Back to: Workflow selector screen       │
│ Ready for next workflow                    │
└────────────────────────────────────────────┘
```

---

## FLOW 4: Request Payload Structure

```
┌─────────────────────────────────────────────────────────────┐
│ GUI Creates WorkflowSubmitRequest                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ POST /api/workflow/submit                                   │
│                                                             │
│ {                                                           │
│   "workflow_id": "workflow_feature_001",                   │
│   "workflow_type": "feature_implementation",               │
│   "user_query": "Implement JWT auth with 1hr expiration",  │
│   "correlation_id": "req_uuid_xyz",                        │
│                                                             │
│   "workflow_config": {  ← From GUI's workflows.yaml        │
│     "stages": [                                            │
│       {                                                    │
│         "id": "code_generation",                           │
│         "agent": "code_generation",                        │
│         "enabled": true                                   │
│       },                                                   │
│       {                                                    │
│         "id": "test_generation",                           │
│         "agent": "test_generation",                        │
│         "enabled": true                                   │
│       }                                                    │
│     ]                                                      │
│   },                                                       │
│                                                             │
│   "agents_config": {  ← From GUI's agents.yaml             │
│     "code_generation": {                                   │
│       "model": "primary",                                  │
│       "role": "code_generation",                           │
│       "retrieval_needs": [                                 │
│         "file_level_semantic",                            │
│         "function_ast_selective",                         │
│         "lsp_integration"                                 │
│       ],                                                   │
│       "context_limits": {                                  │
│         "max_tokens": 3000                                │
│       }                                                    │
│     },                                                     │
│     "test_generation": {                                   │
│       "model": "primary",                                  │
│       "role": "test_generation",                           │
│       "retrieval_needs": [                                 │
│         "test_examples_only"                              │
│       ],                                                   │
│       "context_limits": {                                  │
│         "max_tokens": 2000                                │
│       }                                                    │
│     }                                                      │
│   },                                                       │
│                                                             │
│   "retrieval_config": {  ← From GUI's retrieval.yaml       │
│     "enabled": true,                                       │
│     "strategy": "TART_code_generation",                    │
│     "phase_1": {                                           │
│       "method": "semantic_search",                         │
│       "top_k": 50                                          │
│     },                                                     │
│     "phase_2": {                                           │
│       "method": "cross_encoder_reranking",                 │
│       "top_k": 20                                          │
│     }                                                      │
│   },                                                       │
│                                                             │
│   "mcp_config": {  ← From GUI's mcp_integration.yaml       │
│     "python_tools": {"enabled": true},                     │
│     "language_servers": {                                  │
│       "python": {"enabled": true}                          │
│     }                                                      │
│   },                                                       │
│                                                             │
│   "workspace_context": {  ← From GUI's workspace selection │
│     "workspace_id": "ws_jwt_feature_abc123",               │
│     "working_dir": "/home/user/my-project",               │
│     "language": "python",                                  │
│     "framework": "fastapi"                                 │
│   }                                                        │
│ }                                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend Receives & Validates                                │
├─────────────────────────────────────────────────────────────┤
│ ✓ Schema validation passed                                 │
│ ✓ workspace_id resolved                                    │
│ ✓ Config versions compatible                               │
│ → Initiate LangGraph execution                              │
└─────────────────────────────────────────────────────────────┘
```

---

## FLOW 5: Real-Time Streaming Events

```
Backend emits stream of JSON events:

┌──────────────────────────────────────────────────────┐
│ Event 1: Status Update (Orchestrator)                │
├──────────────────────────────────────────────────────┤
│ {                                                    │
│   "type": "status_update",                           │
│   "correlation_id": "req_xyz",                       │
│   "workflow_id": "workflow_001",                     │
│   "timestamp": "2025-11-04T18:35:22Z",              │
│   "stage_id": "orchestrator",                        │
│   "status": "Routing workflow...",                   │
│   "progress_percent": 5                              │
│ }                                                    │
│                                                      │
│ GUI Update:                                          │
│  footer.status = "Routing workflow..."               │
│  footer.progress = 5%                                │
└──────────────────────────────────────────────────────┘
                      │
                      ▼ (2 seconds later)
┌──────────────────────────────────────────────────────┐
│ Event 2: Status Update (Retrieval)                   │
├──────────────────────────────────────────────────────┤
│ {                                                    │
│   "type": "status_update",                           │
│   "correlation_id": "req_xyz",                       │
│   "stage_id": "retrieval",                           │
│   "status": "Retrieving context for code generation" │
│   "progress_percent": 15                             │
│ }                                                    │
│                                                      │
│ GUI Update:                                          │
│  footer.status = "Retrieving context for code gen"   │
│  footer.progress = 15%                               │
└──────────────────────────────────────────────────────┘
                      │
                      ▼ (3 seconds later)
┌──────────────────────────────────────────────────────┐
│ Event 3: Status Update (Code Generation)             │
├──────────────────────────────────────────────────────┤
│ {                                                    │
│   "type": "status_update",                           │
│   "correlation_id": "req_xyz",                       │
│   "stage_id": "code_generation",                     │
│   "status": "Generating code...",                    │
│   "progress_percent": 40,                            │
│   "metrics": {                                       │
│     "tokens_generated": 450,                         │
│     "inference_speed_tokens_per_sec": 22.5,         │
│     "elapsed_seconds": 20,                           │
│     "estimated_remaining_seconds": 25                │
│   }                                                  │
│ }                                                    │
│                                                      │
│ GUI Update:                                          │
│  footer.status = "Generating code..."                │
│  footer.progress = 40%                               │
│  footer.metrics = "22.5 tokens/sec"                  │
│                                                      │
│ Multiple events stream continuously                  │
│ (progress: 40% → 50% → 60% → ... → 100%)            │
└──────────────────────────────────────────────────────┘
                      │
                      ▼ (60 seconds total)
┌──────────────────────────────────────────────────────┐
│ Event 4: Commit Message                              │
├──────────────────────────────────────────────────────┤
│ {                                                    │
│   "type": "commit_created",                          │
│   "correlation_id": "req_xyz",                       │
│   "stage_id": "code_generation",                     │
│   "commit_id": "abc1234567890",                      │
│   "message": "feat: Implement JWT authentication..." │
│ }                                                    │
│                                                      │
│ GUI Update:                                          │
│  (Optional: show commit notification)                │
└──────────────────────────────────────────────────────┘
                      │
                      ▼ (more stages...)
┌──────────────────────────────────────────────────────┐
│ Event N: Workflow Complete                           │
├──────────────────────────────────────────────────────┤
│ {                                                    │
│   "type": "workflow_complete",                       │
│   "correlation_id": "req_xyz",                       │
│   "workflow_id": "workflow_001",                     │
│   "timestamp": "2025-11-04T18:36:50Z",              │
│   "status": "success",                               │
│   "commits": [                                       │
│     {                                                │
│       "commit_id": "abc1234567890",                  │
│       "agent": "code_generation",                    │
│       "message": "feat: JWT auth with expiration",   │
│       "files_changed": 1,                            │
│       "additions": 142,                              │
│       "deletions": 0,                                │
│       "files": [                                     │
│         {                                            │
│           "file_path": "src/auth/jwt_handler.py",   │
│           "change_type": "created",                  │
│           "additions": 142,                          │
│           "hunks": [                                 │
│             {                                        │
│               "hunk_id": "hunk_1",                   │
│               "lines_start": 1,                      │
│               "lines_end": 25,                       │
│               "summary": "Adds create_jwt_token()"  │
│             }                                        │
│           ]                                          │
│         }                                            │
│       ]                                              │
│     },                                               │
│     {                                                │
│       "commit_id": "def9876543210",                  │
│       "agent": "test_generation",                    │
│       "message": "test: Add JWT tests",              │
│       "files_changed": 1,                            │
│       "additions": 85,                               │
│       "deletions": 0,                                │
│       ...                                            │
│     }                                                │
│   ],                                                 │
│   "total_changes": {                                 │
│     "files": 2,                                      │
│     "additions": 227,                                │
│     "deletions": 0                                   │
│   }                                                  │
│ }                                                    │
│                                                      │
│ GUI Update:                                          │
│  state.diff_view.commits = commits (METADATA ONLY!)  │
│  state.is_loading = False                            │
│  UI renders: Hierarchical diff view                  │
│  (Code NOT loaded yet, only on user click)           │
└──────────────────────────────────────────────────────┘
```

---

## FLOW 6: Lazy-Load Code on Demand

```
User in Diff View sees:

┌──────────────────────────────┐
│ Commit: JWT Authentication   │
├──────────────────────────────┤
│ ▶ src/auth/jwt_handler.py    │
│   +142 lines                 │
│                              │
│   [Click to expand code]     │
└──────────────────────────────┘

User clicks "[Click to expand code]"
                │
                ▼
        ┌──────────────┐
        │ Toggle Hunk  │
        │ Send Message │
        │ ToggleHunk   │
        └──────┬───────┘
               │
               ▼
       ┌──────────────────┐
       │ Check cache      │
       │ (loaded_diffs)   │
       └────┬──────┬──────┘
            │      │
    Cached  │      │ Not cached
            ▼      ▼
         Use    Make Async
         from   API Call
         cache
            │      │
            └──┬───┘
               │
               ▼
      ┌─────────────────────────┐
      │ GET /api/workflow/      │
      │   {exec_id}/commit/     │
      │   {commit_id}/diff      │
      └──────────┬──────────────┘
                 │
                 ▼
      ┌──────────────────────────┐
      │ Backend returns diff:    │
      │ {                        │
      │   diff: "--- /dev/null"  │
      │   "+ def create_jwt()..  │
      │   hunks: [...]           │
      │ }                        │
      └──────────┬───────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ GUI Message: DiffLoaded    │
    │ Update State:              │
    │  loaded_diffs[key] = diff  │
    │  (Cache the diff)          │
    │                            │
    │ UI Re-renders:             │
    │  Expand hunk → Show code   │
    │  Syntax highlight enabled  │
    └────────────────────────────┘

Result: Code displayed only when user needs it
→ Faster initial rendering
→ Reduced bandwidth
→ Better UX
```

---

**END OF FLOW DIAGRAMS**

These diagrams complement the README files and show the complete request/response flows, state transitions, and user interactions.

