{
  description = "AI Coding Assistant - Multi-agent orchestration with LangChain and MCP";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";
    mcp-hub-repo.url = github:ravitemer/mcp-hub;
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    , mcp-hub-repo
    ,
    }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      lib = nixpkgs.lib;

      # ============================================================================
      # AGENT SHELL SCRIPT
      # ============================================================================

      agent-shell = pkgs.writeShellScriptBin "agent" (builtins.readFile ./ai-agent-runtime/scripts/agent.sh);


      # ============================================================================
      # PYTHON ENVIRONMENT
      # ============================================================================

      pythonEnv = pkgs.python312.withPackages (ps: with ps; [
        langchain
        langchain-community
        langchain-core
        langgraph
        fastapi
        uvicorn
        pydantic
        pydantic-settings
        mcp
        python-dotenv
        pyyaml
        typing-extensions
        aiofiles
        httpx
        pip
        setuptools
        wheel
      ]);

      # ============================================================================
      # RUNTIME PACKAGE
      # ============================================================================

      aiAgentRuntime = pkgs.stdenv.mkDerivation {
        name = "ai-agent-runtime";
        src = ./.;

        nativeBuildInputs = [ pythonEnv ];

        installPhase = ''
          # Create output structure
          mkdir -p $out/lib
          mkdir -p $out/bin

          # Copy the entire project (preserves ai_agent_runtime module structure)
          cp -r ai-agent-runtime $out/lib/

          # Create python launcher that adds lib to path
          cat > $out/bin/ai-agent-server << 'EOF'
          #!/usr/bin/env bash
          set -e
          export PYTHONPATH="$out/lib/ai-agent-runtime:''${PYTHONPATH}"
          export PYTHONUNBUFFERED=1
          exec ${pythonEnv}/bin/python -m ai_agent_runtime.server "''$@"
          EOF
          chmod +x $out/bin/ai-agent-server

          # Copy agent shell script
          mkdir -p $out/bin
          cp -r ai-agent-runtime/scripts/* $out/bin/ || true
          chmod +x $out/bin/*.sh 2>/dev/null || true
        '';
      };

    in {
      # ============================================================================
      # PACKAGES
      # ============================================================================

      packages = {
        ai-agent-runtime = aiAgentRuntime;
        agent-shell = agent-shell;
        default = aiAgentRuntime;
        mcp-hub = mcp-hub-repo.packages."${system}".default;
      };

      # ============================================================================
      # DEV SHELL WITH UV
      # ============================================================================

      devShells.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          python312
          uv
          git
          direnv
          agent-shell
          nodejs_22  # For npm packages
          self.packages.${system}.mcp-hub
          aiAgentRuntime
        ];

        packages = [
          aiAgentRuntime
          agent-shell
        ];

        env = {
          OLLAMA_BASE_URL = "http://localhost:11434";
          AGENT_SERVER_PORT = "3000";
          PYTHONUNBUFFERED = "1";
          MCP_HUB_URL="http://localhost:37373/mcp";
        };

        shellHook = ''
          # Add current directory ai-agent-runtime to PYTHONPATH
          export PYTHONPATH="${builtins.toString ./.}/ai-agent-runtime:''${PYTHONPATH}"

          # Initialize or activate venv
          if [ ! -d ".venv" ]; then
            ${pkgs.uv}/bin/uv venv .venv --python ${pkgs.python312}/bin/python3.12
          fi
          source .venv/bin/activate

          # Install dependencies from requirements.txt (cached, fast)
          ${pkgs.uv}/bin/uv sync

          echo "╭──────────────────────────────────────────────────────────╮"
          echo "│  AI Agent Runtime Development Environment                │"
          echo "├──────────────────────────────────────────────────────────┤"
          echo "│ Python: $(python --version)                             │"
          echo "│ PYTHONPATH: $PYTHONPATH"
          echo "│ Package Manager: uv (fast, deterministic)               │"
          echo "│ FastAPI Server: http://localhost:3000                   │"
          echo "│ Ollama: http://localhost:11434                          │"
          echo "│                                                          │"
          echo "│ MCP Servers Available:                                  │"
          echo "│  ✓ Git MCP - Version control context                    │"
          echo "│  ✓ LSP MCP - Semantic code understanding               │"
          echo "│  ✓ Filesystem MCP - Secure file operations             │"
          echo "│  ✓ Docs RAG MCP - Local documentation retrieval        │"
          echo "│  ✓ Web Search MCP - Self-hosted web search             │"
          echo "│                                                          │"
          echo "│ Quick Start:                                             │"
          echo "│  python -m ai_agent_runtime.server                      │"
          echo "│  or: agent                                               │"
          echo "│                                                          │"
          echo "╰──────────────────────────────────────────────────────────╯"
        '';
      };

      # ============================================================================
      # NIXOS MODULE
      # ============================================================================

      nixosModules.default = { config, pkgs, lib, ... }:
        let
          cfg = config.services.aiAgent;
        in
        {
          options.services.aiAgent = {
            enable = lib.mkEnableOption "AI Agent Server with MCP";
            gpuAcceleration = lib.mkOption { type = lib.types.boolesn; default =
              false; description = "GPU Acceleration"; };
            port = lib.mkOption { type = lib.types.port; default = 3000; description = "Agent server port"; };
            ollamaHost = lib.mkOption { type = lib.types.str; default = "127.0.0.1"; description = "Ollama server host"; };
            ollamaPort = lib.mkOption { type = lib.types.port; default = 11434; description = "Ollama server port"; };
            models = lib.mkOption {
              type = lib.types.attrsOf lib.types.str;
              default = {
                supervisor = "deepseek-coder:7b-instruct";
                code-expert = "deepseek-coder:7b-instruct";
                knowledge-scout = "deepseek-coder:7b-instruct";
              };
              description = "Models to preload in Ollama";
            };
          };

          config = lib.mkIf cfg.enable {
            services.ollama = {
              enable = true;
              acceleration = cfg.gpuAcceleration;

              host = cfg.ollamaHost;
              port = cfg.ollamaPort;
              loadModels = lib.attrValues cfg.models;
            };

            networking.firewall.allowedTCPPorts = [ cfg.port ];
            environment.systemPackages = with pkgs; [ git curl aiAgentRuntime agent-shell ];
          };
        };

      # ============================================================================
      # HOME-MANAGER MODULE
      # ============================================================================

      homeManagerModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.aiAgent;

          mcpServersModule = lib.types.submodule {
            options = {
              command = lib.mkOption { type = lib.types.str; };
              transport = lib.mkOption { type = lib.types.str; default = "stdio"; };
              args = lib.mkOption {
                type = lib.types.listOf lib.types.str;
                default = [];
                description = "Command args";
              };
            };
          };
          pipelineModule = lib.types.submodule {
            options = {
              name = lib.mkOption { type = lib.types.str; };
              description = lib.mkOption { type = lib.types.str; };
              model = lib.mkOption { type = lib.types.str; };
              systemPrompt = lib.mkOption { type = lib.types.str; };
              requiredTools = lib.mkOption {
                type = lib.types.listOf lib.types.str;
                default = [];
                description = "Required MCP tools";
              };
              optionalTools = lib.mkOption {
                type = lib.types.listOf lib.types.str;
                default = [];
                description = "Optional MCP tools";
              };
              contexts = lib.mkOption {
                type = lib.types.listOf (lib.types.enum [ "nvim" "vscode" "shell" "web" ]);
                default = [ "shell" ];
              };
            };
          };
        in
        {
          options.programs.aiAgent = {
            enable = lib.mkEnableOption "AI Agent user configuration";
            serverUrl = lib.mkOption { type = lib.types.str; default = "http://localhost:3000"; };
            pipelines = lib.mkOption { type = lib.types.attrsOf pipelineModule; default = {}; };
            mcpServers = lib.mkOption { type = lib.types.attrsOf mcpServersModule; default = {}; };
            enableUserService = lib.mkOption { type = lib.types.bool; default = true; };
          };

          config = lib.mkIf cfg.enable {
            home.file.".config/ai-agent/manifests.json".text = builtins.toJSON { pipelines = cfg.pipelines; };
            home.sessionVariables = {
              AI_AGENT_MANIFESTS = "${config.home.homeDirectory}/.config/ai-agent/manifests.json";
              AI_AGENT_SERVER_URL = cfg.serverUrl;
              OLLAMA_BASE_URL = "http://localhost:11434";
            };

            systemd.user.services.ai-agent-server = lib.mkIf cfg.enableUserService {
              Unit = {
                Description = "AI Agent Server with MCP (user service)";
                After = [ "network-online.target" ];
                Wants = [ "network-online.target" ];
              };

              Service = {
                Type = "simple";
                ExecStart = "${self.packages.${system}.agent-shell}/bin/agent";
                Restart = "on-failure";
                RestartSec = "10s";
                Environment = [
                  "OLLAMA_BASE_URL=http://localhost:11434"
                  "AGENT_SERVER_PORT=3000"
                  "AI_AGENT_MANIFESTS=%h/.config/ai-agent/manifests.json"
                  "PYTHONUNBUFFERED=1"
                ];
                StandardOutput = "journal";
                StandardError = "journal";
              };

              Install.WantedBy = [ "default.target" ];
            };

            home.packages = with pkgs; [ curl jq git agent-shell ];
          };
        };
    }
    );
}
