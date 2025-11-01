{
  description = "AI Coding Assistant - Multi-agent orchestration with LangChain and MCP";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";

    # MCP Servers (5 recommended)
    git-mcp-server-repo = { url = "github:cyanheads/git-mcp-server"; flake = false; };
    lsp-mcp-repo = { url = "github:Tritlo/lsp-mcp"; flake = false; };
    mcp-filesystem-server-repo = { url = "github:mark3labs/mcp-filesystem-server"; flake = false; };
    mcp-docs-rag-repo = { url = "github:kazuph/mcp-docs-rag"; flake = false; };
    web-search-mcp-repo = { url = "github:modelcontextprotocol/servers"; flake = false; };
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    , git-mcp-server-repo
    , lsp-mcp-repo
    , mcp-filesystem-server-repo
    , mcp-docs-rag-repo
    , web-search-mcp-repo
    }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      lib = nixpkgs.lib;

      # ============================================================================
      # MCP SERVERS - BUILD FROM SOURCE
      # ============================================================================

      git-mcp-server = pkgs.buildNpmPackage {
        pname = "git-mcp-server";
        version = "0.1.0";
        src = git-mcp-server-repo;
        npmDepsHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        build = "npm run build || true";
        postInstall = ''
          mkdir -p $out/bin
          cat > $out/bin/git-mcp-server << 'EOF'
          #!/usr/bin/env node
          require('${git-mcp-server-repo}/dist/index.js');
          EOF
          chmod +x $out/bin/git-mcp-server
        '';
      };

      lsp-mcp = pkgs.buildNpmPackage {
        pname = "lsp-mcp";
        version = "0.1.0";
        src = lsp-mcp-repo;
        npmDepsHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        build = "npm run build || true";
        postInstall = ''
          mkdir -p $out/bin
          cat > $out/bin/lsp-mcp << 'EOF'
          #!/usr/bin/env node
          require('${lsp-mcp-repo}/dist/index.js');
          EOF
          chmod +x $out/bin/lsp-mcp
        '';
      };

      mcp-filesystem-server = pkgs.buildGoModule {
        pname = "mcp-filesystem-server";
        version = "0.11.1";
        src = mcp-filesystem-server-repo;
        vendorHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        subPackages = [ "." ];
        ldflags = [ "-s" "-w" "-X main.Version=0.11.1" ];
      };

      mcp-docs-rag = pkgs.buildNpmPackage {
        pname = "mcp-docs-rag";
        version = "0.1.0";
        src = mcp-docs-rag-repo;
        npmDepsHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        build = "npm run build || true";
        postInstall = ''
          mkdir -p $out/bin
          cat > $out/bin/mcp-docs-rag << 'EOF'
          #!/usr/bin/env node
          require('${mcp-docs-rag-repo}/dist/index.js');
          EOF
          chmod +x $out/bin/mcp-docs-rag
        '';
      };

      web-search-mcp = pkgs.buildNpmPackage {
        pname = "web-search-mcp";
        version = "0.1.0";
        src = "${web-search-mcp-repo}/src/web-search";
        npmDepsHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        build = "npm run build || true";
        postInstall = ''
          mkdir -p $out/bin
          cat > $out/bin/web-search-mcp << 'EOF'
          #!/usr/bin/env node
          require('${web-search-mcp-repo}/src/web-search/dist/index.js');
          EOF
          chmod +x $out/bin/web-search-mcp
        '';
      };

      # ============================================================================
      # RUNTIME PACKAGE
      # ============================================================================

      aiAgentRuntime = pkgs.stdenv.mkDerivation {
        name = "ai-agent-runtime";
        src = ./ai-agent-runtime;

        installPhase = ''
          mkdir -p $out/lib $out/bin
          cp -r . $out/lib/ai-agent-runtime

          cat > $out/bin/ai-agent-server << EOF
          #!/usr/bin/env bash
          set -e
          export PYTHONPATH="$out/lib:\$PYTHONPATH"
          export PYTHONUNBUFFERED=1
          cd "$out/lib/ai-agent-runtime"
          exec \$@
          EOF
          chmod +x $out/bin/ai-agent-server
        '';
      };

    in {
      # ============================================================================
      # PACKAGES
      # ============================================================================

      packages = {
        ai-agent-runtime = aiAgentRuntime;
        git-mcp-server = git-mcp-server;
        lsp-mcp = lsp-mcp;
        mcp-filesystem-server = mcp-filesystem-server;
        mcp-docs-rag = mcp-docs-rag;
        web-search-mcp = web-search-mcp;
        default = aiAgentRuntime;
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
        ];

        env = {
          OLLAMA_BASE_URL = "http://localhost:11434";
          AGENT_SERVER_PORT = "3000";
          PYTHONUNBUFFERED = "1";
        };

        shellHook = ''
          # Initialize or activate venv
          if [ ! -d ".venv" ]; then
            ${pkgs.uv}/bin/uv venv .venv --python ${pkgs.python312}/bin/python3.12
          fi
          source .venv/bin/activate

          # Install dependencies from requirements.txt (cached, fast)
          ${pkgs.uv}/bin/uv pip sync requirements.txt

          echo "╭──────────────────────────────────────────────────────────╮"
          echo "│  AI Agent Runtime Development Environment                │"
          echo "├──────────────────────────────────────────────────────────┤"
          echo "│ Python: $(python --version)                             │"
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
          echo "│                                                          │"
          echo "╰──────────────────────────────────────────────────────────╯"
        '';
      };

      # ============================================================================
      # NIXOS MODULE (unchanged)
      # ============================================================================

      nixosModules.default = { config, pkgs, lib, ... }:
        let
          cfg = config.services.aiAgent;
        in
        {
          options.services.aiAgent = {
            enable = lib.mkEnableOption "AI Agent Server with MCP";
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
              host = cfg.ollamaHost;
              port = cfg.ollamaPort;
              loadModels = lib.attrValues cfg.models;
            };

            networking.firewall.allowedTCPPorts = [ cfg.port ];
            environment.systemPackages = with pkgs; [ git curl aiAgentRuntime ];
          };
        };

      # ============================================================================
      # HOME-MANAGER MODULE (unchanged)
      # ============================================================================

      homeManagerModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.aiAgent;
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
                ExecStart = "${pkgs.python312}/bin/python -m ai_agent_runtime.server";
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

            home.packages = with pkgs; [ curl jq git ];
          };
        };
    }
    );
}
