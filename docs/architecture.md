# Architecture & Design Patterns

## System Architecture

The AG2 Parallel Agent Network uses a three-tier architecture:

### Tier 1: Orchestration Layer (Cline)
- User interface and task acceptance
- Plan review and approval
- File I/O operations
- MCP server coordination

### Tier 2: Agent Orchestration (AG2)
- Parallel team execution via ThreadPoolExecutor
- GroupChat for within-team communication
- Swarm for complex agent handoffs

### Tier 3: Knowledge Layer (HelixDB)
- Vector embeddings for semantic search
- Graph relationships for structural understanding
- Per-team context isolation

## Design Patterns

### Factory Pattern
Used for clean agent instantiation with proper isolation:
- `AgentFactory.create_architect_expert(team_id)`
- `AgentFactory.create_code_writer(team_id)`
- Ensures each agent has isolated state

### Team Pattern
Three specialized teams work in parallel:
- Team A: Architecture & Review
- Team B: Implementation & Testing
- Team C: Documentation & Validation

### RAG Pattern
Retrieval-Augmented Generation with team-specific contexts:
- Team A accesses architecture docs
- Team B accesses code examples and testing guides
- Team C accesses documentation templates

## Parallel Execution Strategy

ThreadPoolExecutor with proper concurrency:
```
┌─ Main Thread
│
├─ Worker 1: Team A ──────────────┐
├─ Worker 2: Team B ──────────────┤ Execute in parallel
└─ Worker 3: Team C ──────────────┘
                │
                └─► Gather results
                    ├─► Refinement loop
                    └─► Output
```

Expected performance: 70-75% time reduction vs sequential.
