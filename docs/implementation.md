# Implementation Guide

## Setting Up Your First Workflow

### 1. Configure LLM Provider

```bash
# Option A: OpenAI
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4
export LLM_API_KEY=sk-...

# Option B: Local Ollama
export LLM_PROVIDER=ollama
export LLM_MODEL=mistral
export LLM_API_BASE=http://localhost:11434
```

### 2. Prepare Documentation for RAG

```
docs/
├── architecture/
│   ├── design_patterns.md
│   └── system_overview.md
├── implementation/
│   ├── code_style.md
│   └── best_practices.md
├── testing/
│   ├── unit_tests.md
│   └── integration_tests.md
└── doc_templates/
    ├── api_docs_template.md
    └── architecture_decision_record.md
```

### 3. Initialize and Run

```python
from agent_network import ParallelAgentNetwork, LLMConfig
import asyncio

async def main():
    llm_config = LLMConfig(
        model="gpt-4",
        api_key="sk-...",
    )

    network = ParallelAgentNetwork(llm_config=llm_config)
    network.setup_teams("Your task here", docs_base_path="./docs")

    # Execute parallel teams
    results = await network.execute_parallel("Your task")

    # Refine outputs
    refinement = network.execute_refinement_loop(results)

    # Generate report
    report = network.generate_report()
    print(report)

asyncio.run(main())
```

## Advanced Configuration

### Custom Agent Roles

Extend `AgentFactory` to add your own agents:

```python
class CustomAgentFactory(AgentFactory):
    def create_security_expert(self, team_id: str) -> AssistantAgent:
        return AssistantAgent(
            name=f"SecurityExpert_{team_id}",
            system_message="You are a security expert...",
            llm_config=self.llm_config,
            max_consecutive_auto_reply=3,
        )
```

### Custom RAG Contexts

Per-agent RAG filtering:

```python
team.agents["security_rag"] = self.agent_factory.create_retrieve_proxy(
    f"security_{team_id}",
    docs_path="./docs/security",
    task_type="code"
)
```

## Performance Tuning

### ThreadPoolExecutor Configuration
```python
network = ParallelAgentNetwork(
    llm_config=llm_config,
    max_workers=3,  # Adjust based on CPU cores
)
```

### Agent Configuration
```python
# In AgentFactory:
max_consecutive_auto_reply=3  # Prevent infinite loops
max_round=15  # Per team, limit conversation rounds
temperature=0.7  # Adjust for creativity vs consistency
```

### RAG Configuration
```python
retrieve_config={
    "chunk_token_size": 1500,  # Larger = more context
    "embedding_model": "all-mpnet-base-v2",  # Other options available
}
```
