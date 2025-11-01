{
  description = "AI Coding Assistant - Multi-agent orchestration with LangChain and MCP";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";

    # Official MCP Servers Repository
    mcp-servers-repo = {
      url = "github:modelcontextprotocol/servers";
      flake = false;
    };

    # GitHub Official MCP Server
    github-mcp-server-repo = {
      url = "github:github/github-mcp-server";
      flake = false;
    };

    # LangChain MCP Adapters
    langchain-mcp-adapters-repo = {
      url = "github:langchain-ai/langchain-mcp-adapters";
      flake = false;
    };
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    , mcp-servers-repo
    , github-mcp-server-repo
    , langchain-mcp-adapters-repo
    , ...
    }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      lib = nixpkgs.lib;

      agent-shell = pkgs.writeShellScriptBin "agent" (
        builtins.readFile ./ai-agent-runtime/scripts/agent.sh
      );

      # ============================================================================
      # MCP SERVER BUILDS FROM SOURCE
      # ============================================================================

      # Build langchain-mcp-adapters from source
      langchain-mcp-adapters = pkgs.python311Packages.buildPythonPackage {
        pname = "langchain-mcp-adapters";
        version = "0.1.0";
        src = langchain-mcp-adapters-repo;
        format = "pyproject";

        nativeBuildInputs = with pkgs.python311Packages; [
          poetry-core
          setuptools
          wheel
        ];

        propagatedBuildInputs = with pkgs.python311Packages; [
          langchain-core
          pydantic
          typing-extensions
          aiofiles
          httpx
        ];

        doCheck = false;

        meta = {
          description = "LangChain MCP Adapters";
          homepage = "https://github.com/langchain-ai/langchain-mcp-adapters";
        };
      };

      # Build Filesystem MCP Server from official repository
      mcp-server-filesystem = pkgs.python311Packages.buildPythonPackage {
        pname = "mcp-server-filesystem";
        version = "0.5.0";
        src = "${mcp-servers-repo}/src/filesystem";
        format = "pyproject";

        nativeBuildInputs = with pkgs.python311Packages; [
          poetry-core
          setuptools
          wheel
        ];

        propagatedBuildInputs = with pkgs.python311Packages; [
          mcp
          pydantic
          typing-extensions
        ];

        doCheck = false;

        meta = {
          description = "MCP Server for filesystem operations";
          homepage = "https://github.com/modelcontextprotocol/servers";
        };
      };

      # Build Git MCP Server from official repository
      mcp-server-git = pkgs.python311Packages.buildPythonPackage {
        pname = "mcp-server-git";
        version = "0.5.0";
        src = "${mcp-servers-repo}/src/git";
        format = "pyproject";

        nativeBuildInputs = with pkgs.python311Packages; [
          poetry-core
          setuptools
          wheel
        ];

        propagatedBuildInputs = with pkgs.python311Packages; [
          mcp
          pydantic
          typing-extensions
          gitpython
        ];

        doCheck = false;

        meta = {
          description = "MCP Server for git operations";
          homepage = "https://github.com/modelcontextprotocol/servers";
        };
      };

      # Build Web Search MCP Server from official repository
      mcp-server-web-search = pkgs.python311Packages.buildPythonPackage {
        pname = "mcp-server-web-search";
        version = "0.5.0";
        src = "${mcp-servers-repo}/src/web-search";
        format = "pyproject";

        nativeBuildInputs = with pkgs.python311Packages; [
          poetry-core
          setuptools
          wheel
        ];

        propagatedBuildInputs = with pkgs.python311Packages; [
          mcp
          pydantic
          typing-extensions
          httpx
          beautifulsoup4
        ];

        doCheck = false;

        meta = {
          description = "MCP Server for web search";
          homepage = "https://github.com/modelcontextprotocol/servers";
        };
      };

      # Build GitHub Official MCP Server
      github-mcp-server = pkgs.buildGoModule {
        pname = "github-mcp-server";
        version = "1.0.0";
        src = github-mcp-server-repo;

        vendorHash = null;  # Let it auto-detect

        subPackages = [ "." ];

        meta = {
          description = "GitHub's official MCP Server for repository access";
          homepage = "https://github.com/github/github-mcp-server";
        };
      };

      # ============================================================================
      # PYTHON ENVIRONMENT WITH MCP SERVERS
      # ============================================================================

      pythonEnv = pkgs.python311.withPackages (ps: with ps; [
        # Core LLM framework
        langchain
        langchain-community
        langchain-core
        langgraph

        # Web framework
        fastapi
        uvicorn
        pydantic
        pydantic-settings

        # MCP integration (built from source above)
        langchain-mcp-adapters
        mcp

        # MCP server implementations (built from source above)
        mcp-server-filesystem
        mcp-server-git
        mcp-server-web-search

        # Supporting libraries
        python-dotenv
        pyyaml
        typing-extensions
        aiofiles
        httpx
        gitpython
        beautifulsoup4

        # Development tools
        pip
        setuptools
        wheel
      ]);

      # ============================================================================
      # RUNTIME PACKAGE
      # ============================================================================

      aiAgentRuntime = pkgs.stdenv.mkDerivation {
        name = "ai-agent-runtime";
        src = ./ai-agent-runtime;

        buildInputs = [ pythonEnv ];

        installPhase = ''
          mkdir -p $out/lib
          mkdir -p $out/bin

          # Copy the entire ai-agent-runtime as a package
          cp -r . $out/lib/ai-agent-runtime

          # Create launcher script with MCP environment
          cat > $out/bin/ai-agent-server << EOF
          #!/usr/bin/env bash
          set -e

          export PYTHONPATH="$out/lib:\$PYTHONPATH"
          export PYTHONUNBUFFERED=1

          cd "$out/lib/ai-agent-runtime"
          exec ${pythonEnv}/bin/python -m aiagentruntime.server "\$@"
          EOF
          chmod +x $out/bin/ai-agent-server
        '';
      };

    in
    {
      packages.${system} = {
        ai-agent-runtime = aiAgentRuntime;

        # Export MCP servers and adapters
        langchain-mcp-adapters = langchain-mcp-adapters;
        mcp-server-filesystem = mcp-server-filesystem;
        mcp-server-git = mcp-server-git;
        mcp-server-web-search = mcp-server-web-search;
        github-mcp-server = github-mcp-server;

        default = aiAgentRuntime;
      };

      packages = {
        ai-agent-runtime = aiAgentRuntime;
        langchain-mcp-adapters = langchain-mcp-adapters;
        mcp-server-filesystem = mcp-server-filesystem;
        mcp-server-git = mcp-server-git;
        mcp-server-web-search = mcp-server-web-search;
        github-mcp-server = github-mcp-server;
        default = aiAgentRuntime;
      };

      devShells.${system}.default =
        pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            git
            go
            tree-sitter
            pkg-config
            libgit2
            ruff
            black
            mypy
            pytest
          ];

          OLLAMA_BASE_URL = "http://localhost:11434";
          AGENT_SERVER_PORT = "3000";
          PYTHONUNBUFFERED = "1";

          packages = [
            aiAgentRuntime
            agent-shell
          ];

          shellHook = ''
            echo "╭──────────────────────────────────────────────────────────╮"
            echo "│  AI Agent Runtime Development Environment                │"
            echo "├──────────────────────────────────────────────────────────┤"
            echo "│ Python: $(python --version)                             │"
            echo "│ Go: $(go version)                                       │"
            echo "│                                                          │"
            echo "│ FastAPI Server: http://localhost:3000                   │"
            echo "│ Ollama: http://localhost:11434                          │"
            echo "│                                                          │"
            echo "│ MCP Servers Enabled:                                    │"
            echo "│  ✓ Filesystem - File operations                         │"
            echo "│  ✓ Git - Repository operations                          │"
            echo "│  ✓ GitHub - Code context from GitHub                   │"
            echo "│  ✓ Web Search - Research capabilities                  │"
            echo "│                                                          │"
            echo "│ Quick Start:                                             │"
            echo "│  python -m aiagentruntime.server                        │"
            echo "│                                                          │"
            echo "╰──────────────────────────────────────────────────────────╯"
          '';
        };

      nixosModules.default = { config, pkgs, lib, ... }:
        let
          system = "x86_64-linux";
          aiAgentRuntime = self.packages.${system}.ai-agent-runtime;
          cfg = config.services.aiAgent;
        in
        {
          options.services.aiAgent = {
            enable = lib.mkEnableOption "AI Agent Server with MCP";

            port = lib.mkOption {
              type = lib.types.port;
              default = 3000;
              description = "Agent server port";
            };

            ollamaHost = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1";
              description = "Ollama server host";
            };

            ollamaPort = lib.mkOption {
              type = lib.types.port;
              default = 11434;
              description = "Ollama server port";
            };

            githubToken = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "GitHub token for GitHub MCP Server (optional)";
            };

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

            environment.systemPackages = with pkgs; [
              git
              curl
              tree-sitter
              aiAgentRuntime
              github-mcp-server
            ];

            environment.variables = lib.optionalAttrs (cfg.githubToken != null) {
              GITHUB_TOKEN = cfg.githubToken;
            };
          };
        };

      homeManagerModules.default = { nixpkgs, config, lib, pkgs, ... }:
        let
          cfg = config.programs.aiAgent;
          system = "x86_64-linux";
          aiAgentRuntime = self.packages.${system}.ai-agent-runtime;

          pipelineModule = lib.types.submodule {
            options = {
              name = lib.mkOption { type = lib.types.str; };
              description = lib.mkOption { type = lib.types.str; };
              model = lib.mkOption { type = lib.types.str; };
              systemPrompt = lib.mkOption { type = lib.types.str; };
              requiredTools = lib.mkOption {
                type = lib.types.listOf lib.types.str;
                default = [];
                description = "Required MCP tools: filesystem, git, github, web-search";
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

            serverUrl = lib.mkOption {
              type = lib.types.str;
              default = "http://localhost:3000";
            };

            pipelines = lib.mkOption {
              type = lib.types.attrsOf pipelineModule;
              default = {};
              description = "Agent pipelines with MCP tool configuration";
              example = {
                code-expert = {
                  name = "code-expert";
                  description = "Expert code generator";
                  model = "deepseek-coder:7b-instruct";
                  systemPrompt = "You are an expert code generator...";
                  requiredTools = [ "filesystem" "git" ];
                  optionalTools = [ "github" "web-search" ];
                };
              };
            };

            enableUserService = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Run as user systemd service";
            };

            githubToken = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "GitHub token for GitHub MCP Server (read from ~/.config/ai-agent/github_token if not set)";
            };
          };

          config = lib.mkIf cfg.enable {
            home.file.".config/ai-agent/manifests.json".text =
              builtins.toJSON { pipelines = cfg.pipelines; };

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
                ExecStart = "${aiAgentRuntime}/bin/ai-agent-server";
                Restart = "on-failure";
                RestartSec = "10s";

                Environment = [
                  "OLLAMA_BASE_URL=http://localhost:11434"
                  "AGENT_SERVER_PORT=3000"
                  "AI_AGENT_MANIFESTS=%h/.config/ai-agent/manifests.json"
                  "PYTHONUNBUFFERED=1"
                ] ++ lib.optionals (cfg.githubToken != null) [
                  "GITHUB_TOKEN=${cfg.githubToken}"
                ];

                StandardOutput = "journal";
                StandardError = "journal";
              };

              Install.WantedBy = [ "default.target" ];
            };

            home.packages = with pkgs; [ curl jq git ];
          };
        };
    };
}
