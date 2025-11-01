{
  description = "AI Coding Assistant - Multi-agent orchestration with LangChain";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      lib = nixpkgs.lib;

      # Python environment for the runtime
      pythonEnv = pkgs.python311.withPackages (ps: with ps; [
        langchain
        langchain-community
        langchain-openai
        fastapi
        uvicorn
        pydantic
        pydantic-settings
        langgraph
      ]);

      # Build the runtime package
      aiAgentRuntime = pkgs.stdenv.mkDerivation {
        name = "ai-agent-runtime";
        src = ./ai-agent-runtime;

        buildInputs = [ pythonEnv ];

        installPhase = ''
          mkdir -p $out/lib
          mkdir -p $out/bin

          # Copy entire ai-agent-runtime as a package
          cp -r . $out/lib/ai-agent-runtime

          # Create launcher script
          cat > $out/bin/ai-agent-server << EOF
#!/usr/bin/env bash
export PYTHONPATH="$out/lib:\$PYTHONPATH"
cd "$out/lib/ai-agent-runtime"
exec ${pythonEnv}/bin/python -m ai_agent_runtime.server "\$@"
EOF
          chmod +x $out/bin/ai-agent-server
        '';
      };
    in
    {
      packages = {
        ai-agent-runtime = aiAgentRuntime;
        default = aiAgentRuntime;
      };

      devShells = let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      pkgs.mkShell {
        buildInputs = with pkgs; [
          pythonEnv
          nodejs_22
          git
        ];

        shellHook = ''
          echo "Install Python deps with: pip install langchain langchain-community langchain-openai fastapi uvicorn pydantic langgraph"
        '';
      };

      nixosModules = {
        default = { config, pkgs, lib, ... }:
          let
            system = config.system;
            aiAgentRuntime = self.packages.${system}.ai-agent-runtime;
            cfg = config.services.aiAgent;
          in
          {
            options.services.aiAgent = {
              enable = lib.mkEnableOption "AI Agent Server";

              gpuAcceleration = lib.mkOption {
                type = lib.types.bool;
                default = true;
                description = "Enable GPU acceleration for Ollama";
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

              port = lib.mkOption {
                type = lib.types.port;
                default = 8080;
                description = "Agent server port";
              };

              models = lib.mkOption {
                type = lib.types.attrsOf lib.types.str;
                default = {
                  supervisor = "qwen2.5-coder:7b";
                  code = "qwen2.5-coder:14b";
                  research = "qwen2.5-coder:70b";
                };
                description = "Models to load in Ollama";
              };

              mcpServers = lib.mkOption {
                type = lib.types.attrsOf (lib.types.submodule {
                  options = {
                    enable = lib.mkOption { type = lib.types.bool; default = true; };
                    command = lib.mkOption { type = lib.types.str; };
                    args = lib.mkOption {
                      type = lib.types.listOf lib.types.str;
                      default = [];
                    };
                  };
                });
                default = {
                  filesystem = {
                    enable = true;
                    command = "${pkgs.nodejs}/bin/npx";
                    args = [ "-y" "@modelcontextprotocol/server-filesystem" "/home" ];
                  };
                  git = {
                    enable = true;
                    command = "${pkgs.nodejs}/bin/npx";
                    args = [ "-y" "@modelcontextprotocol/server-git" ];
                  };
                };
                description = "MCP servers configuration";
              };
            };

            config = lib.mkIf cfg.enable {
              services.ollama = {
                enable = true;
                acceleration = if cfg.gpuAcceleration then "cuda" else null;
                host = cfg.ollamaHost;
                port = cfg.ollamaPort;
                loadModels = lib.attrValues cfg.models;
                environmentVariables = {
                  OLLAMA_NUM_PARALLEL = "4";
                  OLLAMA_MAX_LOADED_MODELS = "3";
                };
              };

              networking.firewall.allowedTCPPorts = [ cfg.port ];

              environment.systemPackages = with pkgs; [
                nodejs
                git
                curl
                aiAgentRuntime
              ] ++ lib.optionals cfg.gpuAcceleration [
                nvtopPackages.full
              ];
            };
          };
      };

      homeManagerModules.default = { config, system, lib, pkgs, ... }:
        let
          cfg = config.programs.aiAgent;
          aiAgentRuntime = self.packages.${system}.ai-agent-runtime;

          pipelineModule = lib.types.submodule {
            options = {
              description = lib.mkOption { type = lib.types.str; };
              model = lib.mkOption { type = lib.types.str; };
              requiredTools = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
              optionalTools = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
              fallbackMode = lib.mkOption { type = lib.types.enum [ "degrade" "fail" ]; default = "degrade"; };
              systemPrompt = lib.mkOption { type = lib.types.str; };
              contexts = lib.mkOption {
                type = lib.types.listOf (lib.types.enum [ "nvim" "vscode" "shell" "web" ]);
                default = [ "nvim" "vscode" "shell" ];
              };
            };
          };
        in
        {
          options.programs.aiAgent = {
            enable = lib.mkEnableOption "AI Agent user configuration";
            serverUrl = lib.mkOption {
              type = lib.types.str;
              default = "http://localhost:8080";
            };
            pipelines = lib.mkOption {
              type = lib.types.attrsOf pipelineModule;
              default = {};
              description = "User-defined agent pipelines";
            };
            enableUserService = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Run AI Agent as user systemd service";
            };
            neovimIntegration = lib.mkOption { type = lib.types.bool; default = true; };
            vscodeIntegration = lib.mkOption { type = lib.types.bool; default = true; };
            shellIntegration = lib.mkOption { type = lib.types.bool; default = true; };
          };

          config = lib.mkIf cfg.enable {
            # Create manifests file
            home.file.".config/ai-agent/manifests.json".text = builtins.toJSON {
              pipelines = cfg.pipelines;
            };

            # Environment variables
            home.sessionVariables = {
              AI_AGENT_MANIFESTS = "${config.home.homeDirectory}/.config/ai-agent/manifests.json";
              AI_AGENT_SERVER_URL = cfg.serverUrl;
            };

            systemd.user.services.ai-agent-server = lib.mkIf cfg.enableUserService {
              Unit = {
                Description = "AI Agent Server (user service)";
                After = [ "network-online.target" ];
              };

              Service = {
                Type = "simple";

                # Use absolute path to ai-agent-server binary from package
                ExecStart = "${aiAgentRuntime}/bin/ai-agent-server";

                Restart = "on-failure";
                RestartSec = "10s";

                Environment = [
                  "OLLAMA_BASE_URL=http://localhost:11434"
                  "AGENT_SERVER_PORT=8080"
                  "AI_AGENT_MANIFESTS=%h/.config/ai-agent/manifests.json"
                  "PYTHONUNBUFFERED=1"
                ];
              };

              Install = {
                WantedBy = [ "default.target" ];
              };
            };
            home.file.".local/bin/ai".source = pkgs.writeShellScript "ai-cli" ''
              #!/usr/bin/env bash
              AGENT_URL="''${AI_AGENT_SERVER_URL:-http://localhost:8080}"
              PIPELINE="''${1:-supervisor}"
              QUERY="''${@:2}"

              if [ -z "$QUERY" ]; then
                echo "Usage: ai [pipeline] <query...>"
                curl -s "$AGENT_URL/api/pipelines" 2>/dev/null | ${pkgs.jq}/bin/jq -r '.[] | "  \(.name): \(.description)"' || true
                exit 1
              fi

              curl -s -X POST "$AGENT_URL/api/query" \
                -H "Content-Type: application/json" \
                -d "{\"query\": \"$QUERY\", \"context\": \"shell\", \"pipeline\": \"$PIPELINE\"}" | \
                ${pkgs.jq}/bin/jq -r '.response // .error'
            '';

            home.shellAliases = lib.mkIf cfg.shellIntegration {
              ai = "ai supervisor";
              ai-code = "ai code-expert";
              ai-research = "ai knowledge-scout";
              ai-refactor = "ai refactoring";
              ai-debug = "ai debug";
            };

            home.packages = with pkgs; [ curl jq ];
          };
        };
    };
}
