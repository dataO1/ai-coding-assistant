# AG2 Parallel Agent Network

Production-grade multi-agent orchestration system for software development using AG2 (formerly AutoGen) with advanced RAG and parallel execution.

## 🚀 Features

- **Parallel Team Execution**: Three specialized teams (Architecture, Implementation, Documentation) running simultaneously
- **Agent-Specific RAG**: Each team gets isolated HelixDB vector database context for reduced noise
- **Factory Pattern**: Clean agent instantiation with proper isolation
- **Async/Await Support**: Modern async execution with ThreadPoolExecutor optimization
- **Refinement Loop**: Conversational refinement of parallel outputs in shared GroupChat
- **NixOS Integration**: Full flake support with systemd service module
- **Production Ready**: Error handling, logging, resource limits, security hardening

## 📋 Architecture

```
┌─────────────────────────────────────────────────────┐
│         Cline (VS Code or CLI)                      │
│         Task Orchestrator                            │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Team A      │ │  Team B      │ │  Team C      │
│Architecture  │ │Implementation│ │Documentation│
├──────────────┤ ├──────────────┤ ├──────────────┤
│Architect     │ │CodeWriter    │ │DocWriter     │
│CodeReviewer  │ │TestWriter    │ │Validator     │
│RAG (Arch)    │ │RAG (Code)    │ │RAG (Docs)    │
└────────┬─────┘ └────────┬─────┘ └────────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                  ▼
         ┌─────────────────────┐
         │   Refinement Loop   │
         │  (GroupChat)        │
         │  Combines + Refines │
         └─────────────────────┘
                  │
         ┌────────▼────────┐
         │  HelixDB        │
         │  (Vector DB)    │
         │  Per-team RAG   │
         └─────────────────┘
```

## 🛠️ Installation

### Option 1: Traditional Python

```bash
# Clone repository
git clone https://github.com/your-org/agent-network
cd agent-network

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or \`venv\Scripts\activate\` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy config
cp .env.example .env
# Edit .env with your API keys and settings
```

### Option 2: NixOS with Flake

```bash
# Development shell
nix flake develop

# Build package
nix build .#agent-network

# Run with NixOS service
sudo nixos-rebuild switch --flake .#

# Configure in configuration.nix:
services.agent-network = {
  enable = true;
  llmProvider = "openai";
  llmModel = "gpt-4";
  llmApiKey = "sk-...";
};
```

### Option 3: Docker

```dockerfile
FROM nixos/nix as builder
RUN nix flake init -t github:nixos/templates#flake-utils
# ... build process
```

## 🚀 Quick Start

### CLI Usage

```bash
# Run a simple task
python main.py "Implement a REST API for user authentication"

# With custom options
python main.py "Build a chat application" \
  --workers 3 \
  --docs-path ./docs \
  --output report.json

# Via NixOS service (after enabling in configuration.nix)
systemctl start agent-network
systemctl status agent-network
```

### Python API

```python
import asyncio
from agent_network import ParallelAgentNetwork, LLMConfig

async def main():
    llm_config = LLMConfig(
        model="gpt-4",
        api_key="sk-...",
        temperature=0.7,
    )

    network = ParallelAgentNetwork(llm_config=llm_config)
    network.setup_teams("Build a REST API", docs_base_path="./docs")

    results = await network.execute_parallel("Build a REST API")

    for result in results:
        print(f"{result.team_name}: {result.success}")

    refinement = network.execute_refinement_loop(results)
    print(refinement["refinement_output"])

asyncio.run(main())
```

## 📁 Project Structure

```
agent-network/
├── agent_network.py           # Core orchestration engine
├── config.py                  # Configuration management
├── main.py                    # CLI entry point
├── setup.py                   # Python packaging
├── requirements.txt           # Python dependencies
├── flake.nix                  # NixOS flake
├── modules/
│   └── nixos-agent-network.nix  # NixOS service module
├── docs/
│   ├── architecture/          # Architecture docs for RAG
│   ├── implementation/        # Implementation patterns
│   ├── testing/              # Testing guidelines
│   ├── doc_templates/        # Documentation templates
│   └── examples/             # Usage examples
├── .env.example              # Example configuration
└── README.md                 # This file
```

## ⚙️ Configuration

### Environment Variables

```bash
# LLM Provider
LLM_PROVIDER=openai              # openai, anthropic, ollama
LLM_MODEL=gpt-4                  # Model identifier
LLM_API_KEY=sk-...               # API key
LLM_TEMPERATURE=0.7              # Sampling temperature

# Database
DB_TYPE=chromadb                 # chromadb, qdrant
DB_PATH=./data/vectordb         # Vector database path

# Network
MAX_WORKERS=3                    # Parallel workers
DOCS_PATH=./docs                # Documentation base path
ENABLE_CODE_EXEC=false          # Enable code execution
```

### Using with Local Models (Ollama)

```bash
# 1. Install and run Ollama
ollama run mistral

# 2. Configure agent network
LLM_PROVIDER=ollama
LLM_MODEL=mistral
LLM_API_BASE=http://localhost:11434
```

## 🔍 How It Works

### Team Execution

1. **Parallel Teams**: Three teams execute simultaneously with ThreadPoolExecutor
2. **Isolated Contexts**: Each team accesses its own HelixDB RAG context
3. **Team Workflows**:
   - **Team A (Architecture)**: Architect → CodeReviewer → Orchestrator
   - **Team B (Implementation)**: CodeWriter → TestWriter → Orchestrator
   - **Team C (Documentation)**: DocWriter → Validator → Orchestrator

### Context Management

Each team's RAG is filtered to relevant documents:
- Team A: Architecture patterns, design documents
- Team B: Implementation guides, code examples, testing frameworks
- Team C: Documentation templates, style guides, examples

### Refinement Loop

After parallel execution:
1. Combine all team outputs
2. Run shared GroupChat with Architect, Reviewer, DocWriter
3. Identify conflicts and improvements
4. Generate unified, refined output

## 📊 Performance

Expected speedup with 3 parallel teams:
- Sequential (traditional): ~58 minutes
- Parallel execution: ~15 minutes
- **Efficiency gain: 70-75% reduction in processing time**

## 🔐 Security (NixOS)

The systemd service includes:
- User/group isolation
- Strict read-only filesystem (except state dir)
- Memory and CPU limits (2GB RAM, 80% CPU)
- No elevated privileges
- Private /tmp filesystem

## 📝 Logging

```bash
# Check systemd logs
journalctl -u agent-network -f

# With verbosity
journalctl -u agent-network -f --output=verbose
```

## 🐛 Troubleshooting

### "API key not found"
```bash
# Set in environment
export LLM_API_KEY="your-key-here"

# Or in .env
echo "LLM_API_KEY=sk-..." >> .env
```

### HelixDB connection issues
```bash
# Check if service is running
systemctl status agent-network

# Verify database path exists
ls -la /var/lib/agent-network/vectordb
```

### Out of memory
```bash
# Increase memory limit in NixOS
services.agent-network.memoryLimit = "4G";

# Or in .env
MAX_WORKERS=2  # Reduce parallelism
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: \`git checkout -b feature/my-feature\`
3. Commit changes: \`git commit -am "Add feature"\`
4. Push to branch: \`git push origin feature/my-feature\`
5. Open Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built on [AG2](https://github.com/microsoft/autogen) (formerly AutoGen)
- Vector DB: [HelixDB](https://www.helix-db.com/) / ChromaDB
- NixOS patterns from nixpkgs community

## 📞 Support

- GitHub Issues: [Report bugs](https://github.com/your-org/agent-network/issues)
- Discussions: [Ask questions](https://github.com/your-org/agent-network/discussions)
- Docs: [Read documentation](./docs/)
