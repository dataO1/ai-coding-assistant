{
  description = "AI Coding Assistant with LangChain + MCP";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, home-manager, ... }:
    let
      lib = nixpkgs.lib;
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # Python environment with all dependencies
      pythonEnv = pkgs.python311.withPackages (ps: with ps; [
        langchain
        langchain-community
        langchain-openai
        fastapi
        uvicorn
        httpx
        pydantic
        pydantic-settings
        pytest
        black
        pylint
      ]);

      # Agent server package
      agentServer = pkgs.stdenv.mkDerivation {
        name = "ai-agent-server";
        src = ./agent-server;

        buildInputs = [ pythonEnv ];
        installPhase = ''
          mkdir -p $out/bin
          mkdir -p $out/lib
          cp -r . $out/lib/

          cat > $out/bin/ai-agent-server << EOF
          #!/usr/bin/env bash
          export PYTHONPATH="$out/lib:\$PYTHONPATH"
          exec ${pythonEnv}/bin/python $out/lib/main.py "\$@"
          EOF
          chmod +x $out/bin/ai-agent-server
        '';
      };

      aiCodingAssistantModule = { config, pkgs, lib, ... }:
        let
          cfg = config.aiCodingAssistant;

          # Convert pipeline configs to JSON for agent server
          pipelineConfig = builtins.toJSON (
            lib.mapAttrs (name: pipeline: {
              inherit name;
              description = pipeline.description;
              model = pipeline.model;
              tools = pipeline.tools;
              systemPrompt = pipeline.systemPrompt;
            }) cfg.pipelines
          );

          mcpServersJson = builtins.toJSON (
            lib.mapAttrs (name: server: {
              inherit name;
              enabled = server.enable;
              command = server.command;
              args = server.args;
            }) cfg.mcpServers
          );
        in
        {
          options.aiCodingAssistant = {
            enable = lib.mkEnableOption "AI Coding Assistant with LangChain + MCP";

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

            agentServerPort = lib.mkOption {
              type = lib.types.port;
              default = 8080;
              description = "Agent server API port";
            };

            models = lib.mkOption {
              type = lib.types.attrsOf lib.types.str;
              default = {
                supervisor = "qwen2.5-coder:7b";
                code = "qwen2.5-coder:14b";
                research = "qwen2.5-coder:70b";
              };
              description = "Ollama models to load";
              example = {
                supervisor = "qwen2.5-coder:7b";
                code = "qwen2.5-coder:14b";
              };
            };

            pipelines = lib.mkOption {
              type = lib.types.attrsOf (lib.types.submodule {
                options = {
                  description = lib.mkOption {
                    type = lib.types.str;
                    description = "Pipeline description";
                  };
                  model = lib.mkOption {
                    type = lib.types.str;
                    description = "Model to use";
                  };
                  tools = lib.mkOption {
                    type = lib.types.listOf lib.types.str;
                    default = [];
                    description = "MCP tools to enable";
                  };
                  systemPrompt = lib.mkOption {
                    type = lib.types.str;
                    description = "System prompt for agent";
                  };
                };
              });
              default = {};
              description = "Pipeline definitions";
            };

            mcpServers = lib.mkOption {
              type = lib.types.attrsOf (lib.types.submodule {
                options = {
                  enable = lib.mkOption {
                    type = lib.types.bool;
                    default = true;
                  };
                  command = lib.mkOption {
                    type = lib.types.str;
                    description = "Command to run MCP server";
                  };
                  args = lib.mkOption {
                    type = lib.types.listOf lib.types.str;
                    default = [];
                    description = "Arguments for MCP server";
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
            # Ollama service
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

            # Agent server systemd service
            systemd.services.ai-agent-server = {
              description = "AI Agent Server with LangChain + MCP";
              after = [ "ollama.service" "network-online.target" ];
              wants = [ "network-online.target" ];
              requires = [ "ollama.service" ];
              wantedBy = [ "multi-user.target" ];

              environment = {
                OLLAMA_BASE_URL = "http://${cfg.ollamaHost}:${toString cfg.ollamaPort}";
                AGENT_SERVER_PORT = toString cfg.agentServerPort;
                MODELS_CONFIG = pipelineConfig;
                MCP_SERVERS_CONFIG = mcpServersJson;
                PYTHONUNBUFFERED = "1";
              };

              serviceConfig = {
                Type = "simple";
                ExecStart = "${agentServer}/bin/ai-agent-server";
                Restart = "on-failure";
                RestartSec = "10s";
                StartLimitBurst = 5;
                StartLimitInterval = "60s";
                StandardOutput = "journal";
                StandardError = "journal";
              };
            };

            # Enable networking
            networking.firewall.allowedTCPPorts = [ cfg.agentServerPort ];

            # System packages
            environment.systemPackages = with pkgs; [
              nodejs
              git
              curl
              agentServer
              pythonEnv
            ] ++ lib.optionals cfg.gpuAcceleration [
              nvtopPackages.full
              cudaPackages.cudatoolkit
            ];
          };
        };
    in
    {
      nixosModules.default = aiCodingAssistantModule;

      homeManagerModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.aiAgent;
        in
        {
          options.programs.aiAgent = {
            enable = lib.mkEnableOption "AI Agent user configuration";

            serverUrl = lib.mkOption {
              type = lib.types.str;
              default = "http://localhost:8080";
              description = "AI Agent server URL";
            };

            pipelines = lib.mkOption {
              type = lib.types.attrsOf (lib.types.submodule {
                options = {
                  description = lib.mkOption { type = lib.types.str; };
                  model = lib.mkOption { type = lib.types.str; };
                  tools = lib.mkOption {
                    type = lib.types.listOf lib.types.str;
                    default = [];
                  };
                  systemPrompt = lib.mkOption { type = lib.types.str; };
                };
              });
              default = {};
              description = "User-defined pipelines";
            };

            neovimIntegration = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Configure Neovim integration";
            };

            vscodeIntegration = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Configure VS Code integration";
            };

            shellIntegration = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Configure shell integration";
            };
          };

          config = lib.mkIf cfg.enable {
            # Create agent CLI wrapper
            home.packages = with pkgs; [
              curl
              jq
            ];

            # Agent CLI tool
            home.file.".local/bin/ai".source = pkgs.writeShellScript "ai-cli" ''
              #!/usr/bin/env bash
              set -euo pipefail

              AGENT_URL="${cfg.serverUrl}"
              PIPELINE="''${1:-coding}"
              QUERY="''${2:-}"

              if [ -z "$QUERY" ]; then
                echo "Usage: ai <pipeline> <query>"
                echo "Available pipelines: $(curl -s $AGENT_URL/api/pipelines | ${pkgs.jq}/bin/jq -r '.[] | .name' | tr '\n' ' ')"
                exit 1
              fi

              echo "🤖 Querying $PIPELINE pipeline..."
              curl -s -X POST "$AGENT_URL/api/query" \
                -H "Content-Type: application/json" \
                -d "{\"pipeline\": \"$PIPELINE\", \"query\": \"$QUERY\"}" | \
                ${pkgs.jq}/bin/jq -r '.response // .error'
            '';

            # Neovim configuration
            # programs.neovim.enable = true;
            # programs.neovim.extraConfig = lib.mkIf cfg.neovimIntegration ''
            #   " AI Agent integration
            #   let g:ai_agent_url = "${cfg.serverUrl}"
            #   let g:ai_agent_pipeline = "coding"
            #
            #   function! AIQuery(query)
            #     let cmd = printf(
            #       \ 'curl -s -X POST "%s/api/query" -H "Content-Type: application/json" -d ''{"pipeline": "%s", "query": "%s"}''',
            #       \ g:ai_agent_url, g:ai_agent_pipeline, a:query
            #     \)
            #     let result = system(cmd)
            #     echo result
            #   endfunction
            #
            #   command! -nargs=+ AI :call AIQuery(<q-args>)
            # '';

            # Avante.nvim configuration (if using lazy.nvim)
            xdg.configHome = "${config.home.homeDirectory}/.config";

            home.file.".config/nvim/lua/plugins/ai-agent.lua" = lib.mkIf cfg.neovimIntegration {
              text = ''
                return {
                  {
                    "yetone/avante.nvim",
                    event = "VeryLazy",
                    lazy = false,
                    opts = {
                      provider = "openai",
                      openai = {
                        endpoint = "${cfg.serverUrl}/v1",
                        model = "local",
                        timeout = 30000,
                        temperature = 0.2,
                        max_tokens = 4096,
                      },
                      behaviour = {
                        auto_suggestions = true,
                        auto_set_highlight_group = true,
                        auto_set_keymaps = true,
                        auto_apply_diff_after_generation = false,
                        support_paste_from_clipboard = false,
                      },
                    },
                    build = "make",
                    dependencies = {
                      "stevearc/dressing.nvim",
                      "nvim-lua/plenary.nvim",
                      "MunifTanjim/nui.nvim",
                    },
                  },
                }
              '';
            };

            # VS Code Continue.dev configuration
            home.file.".continue/config.json" = lib.mkIf cfg.vscodeIntegration {
              text = builtins.toJSON {
                models = [
                  {
                    title = "Local Supervisor";
                    provider = "openai";
                    model = "supervisor";
                    apiBase = "${cfg.serverUrl}/v1";
                    apiKey = "local";
                  }
                  {
                    title = "Local Code";
                    provider = "openai";
                    model = "code";
                    apiBase = "${cfg.serverUrl}/v1";
                    apiKey = "local";
                  }
                ];
                system = "You are an expert programmer. Help the user write and refactor code.";
              };
            };

            # Shell aliases
            home.shellAliases = lib.mkIf cfg.shellIntegration {
              ai-code = "ai coding";
              ai-research = "ai research";
              ai-refactor = "ai refactoring";
              ai-debug = "ai debugging";
            };
          };
        };
    };
}
