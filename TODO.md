


# ROADMAP
- [ ] rework pipeline architecture
    - orchestrator -> speclist?
    - parallelized hirarchical model?
- [ ] integrate ACP (Agent Client Protocol) for editor <-> agent communication
    - [ ] for python `acp_sdk` and for rust `agent-client-protocol`
- [ ] making sure llms use openai streaming format?
- improve prompts for specialists
    - (ReAct Model)
        * Why Tool-Calling Aligns With Agent Architecture
        Thought: "User wants snake.py. I should write it."
        Action:  Call file_write tool with code
        Observation: Tool returns {"success": true, "path": "snake.py"}
        Next Thought: "Good. Now should I test it? Create a requirements.txt?"
    - Add Error Recovery Logic

┌─────────────────────────────────────┐
│  Your Iced TUI (Rust)               │
│  ┌───────────────────────────────┐  │
│  │ use agent-client-protocol     │  │ ← Crate: agent-client-protocol
│  │ impl Client { ... }           │  │   Zed's official implementation
│  │ ClientSideConnection          │  │   (Production-ready)
│  └───────────────────────────────┘  │
└────────────┬────────────────────────┘
             │ JSON-RPC 2.0
             │ stdout/stdin
             ↓
┌─────────────────────────────────────┐
│  ACP Server (Python wrapper)        │
│  ┌───────────────────────────────┐  │
│  │ class LangChainAcpServer      │  │ ← You write this (~200 lines)
│  │ impl Agent { ... }            │  │   Bridges ACP ↔ LangChain
│  └───────────────────────────────┘  │
│             │                        │
│  ┌──────────┴────────────┐          │
│  ↓                       ↓          │
│ Your LangChain Agent   MCP Tools   │
│ (existing)            (existing)   │
│  ├─ semantic_search                │
│  ├─ git_diff                       │
│  └─ filter_security                │
│      │         │         │         │
│      ↓         ↓         ↓         │
│   Vector DB  Git   Metadata       │
└─────────────────────────────────────┘

# Key Accuracy Drivers from Local Context
## 1. Faithful Answer Generation (+20-25%)

Domain-specific RAG with curated context eliminates hallucinations on factual questions. Perplexity must balance public web accuracy with reasoning; local systems have ground truth.

## 2. Contextual Retrieval (+13.9% baseline improvement)

By parsing your codebase/files into semantic graphs (tree-sitter), the system understands structure. Questions about "how module X interacts with Y" get 13.9% better answers even with the same underlying model.

## 3. Code Graph Understanding (+30-35%)

Tree-sitter based codebase parsing (implemented in code-graph-rag ) gives your system abstract syntax trees. It understands function calls, dependencies, class hierarchies—things Perplexity can only approximate via snippets from web docs.

## 4. Live System State (+60-70% on ops tasks)

MCP system servers connect to live configs, environment variables, running processes. A query like "what's configured for prod deployment?" returns 100% accurate real-time state. Perplexity would have to search your docs or guess.







# Next Steps:
## GUI
Full Messaging Flow (For Your Semantic File + Diff Viewer)

text
┌─────────────────────────────────────────┐
│  User in Iced GUI                       │
│  Types: "show auth changes"             │
│  Context: project=my-service, tag=sec   │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  Iced Client (ACP)                      │
│                                         │
│  1. First time:                         │
│     agent/capabilities → learn types    │
│                                         │
│  2. Send prompt with context:           │
│  {method: "prompt",                     │
│   messages: [{                          │
│     parts: [                            │
│       {text: "show auth changes"},      │
│       {context: {project, tag}}         │
│     ]                                   │
│   }]                                    │
│  }                                      │
└────────────┬────────────────────────────┘
             │ JSON-RPC over WebSocket
             ↓
┌─────────────────────────────────────────┐
│  LangChain Agent (ACP Server)           │
│                                         │
│  1. Parse prompt + context              │
│  2. LLM sees tools with schemas         │
│  3. LLM decides: "Call semantic_search" │
│     with project="my-service", tag=sec  │
│  4. Get result: 3 files with scores     │
│  5. For each file:                      │
│     - Call get_diff(file_path)          │
│     - Stream notification → client      │
│  6. LLM generates summary                │
│  7. Send final response                 │
└────────────┬────────────────────────────┘
             │ Streaming notifications
             ├→ {kind: "message", content: "Found 3..."}
             ├→ {kind: "diff_chunk", file: "...", delta: "..."}
             ├→ {kind: "diff_chunk", file: "...", delta: "..."}
             └→ {kind: "done"}
             │
             ↓
┌─────────────────────────────────────────┐
│  Iced GUI                               │
│  Left pane: Chat message appended       │
│  Right pane: Diff chunks streamed in    │
│             Syntax-highlighted          │
│             Updated in real-time        │
└─────────────────────────────────────────┘
