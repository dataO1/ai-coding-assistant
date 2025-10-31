# Architecture

┌─────────────────────────────────────────────────────────────┐
│ NixOS Host Configuration │
│ (System-level: Ollama, PostgreSQL, base MCP servers) │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ Home Manager User Configuration │
│ (User-level: Agent pipelines, custom MCPs, API keys) │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ LangChain Agent Server │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Pipeline Registry (declarative Python configs) │ │
│ │ ├── coding.py (code generation + LSP) │ │
│ │ ├── research.py (web + docs search) │ │
│ │ ├── refactor.py (tree-sitter + git history) │ │
│ │ └── debug.py (LSP diagnostics + logs) │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ MCP Tool Providers │
│ ┌─────────────┬──────────────┬───────────────┬─────────┐ │
│ │ tree-sitter │ lsp-mcp │ nvim-mcp │ git │ │
│ │ (AST parse) │ (LSP bridge) │ (editor ctx) │ (hist) │ │
│ └─────────────┴──────────────┴───────────────┴─────────┘ │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ Client Integrations │
│ ┌──────────────┬────────────────┬─────────────────────┐ │
│ │ Neovim │ VS Code │ Shell │ │
│ │ (Avante) │ (Continue.dev) │ (curl/CLI) │ │
│ │ Context: │ Context: │ Context: │ │
│ │ - Buffers │ - Open files │ - CWD │ │
│ │ - LSP diag │ - Git changes │ - Args │ │
│ │ - Cursor pos │ - Terminal out │ - Env vars │ │
│ └──────────────┴────────────────┴─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

# Implementation structure

ai-coding-assistant/
├── flake.nix # System-level config
├── agent-server/
│ ├── main.py # FastAPI server
│ ├── pipeline_loader.py # Load pipelines from Nix config
│ ├── mcp_registry.py # MCP server manager
│ └── pipelines/
│ ├── base.py # Base pipeline class
│ ├── coding.py # Code generation pipeline
│ ├── refactor.py # Refactoring pipeline
│ └── debug.py # Debugging pipeline
├── home-manager-module/
│ └── default.nix # Home Manager module
└── clients/
├── nvim/
│ └── avante-config.lua # Avante.nvim integration
├── vscode/
│ └── continue-config.json # Continue.dev integration
└── shell/
└── ai-cli.sh # Shell wrapper
