{ config, lib, pkgs, ... }:
  let
    cfg = config.programs.aiAgent;

    pipelineModule = lib.types.submodule {
      options = {
        description = lib.mkOption { type = lib.types.str; };
        model = lib.mkOption { type = lib.types.str; };

        requiredTools = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [];
          description = "Tools that MUST be available";
        };

        optionalTools = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [];
          description = "Tools that improve quality if available";
        };

        fallbackMode = lib.mkOption {
          type = lib.types.enum [ "degrade" "fail" ];
          default = "degrade";
          description = "How to handle missing tools";
        };

        systemPrompt = lib.mkOption { type = lib.types.str; };

        contexts = lib.mkOption {
          type = lib.types.listOf (lib.types.enum [ "nvim" "vscode" "shell" "web" ]);
          default = [ "nvim" "vscode" "shell" ];
          description = "Which contexts this pipeline supports";
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
        description = "AI Agent server URL";
      };

      pipelines = lib.mkOption {
        type = lib.types.attrsOf pipelineModule;
        default = {};
        description = "User-defined AI agent pipelines";
      };

      mcpServers = lib.mkOption {
        type = lib.types.attrsOf (lib.types.submodule {
          options = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = true;
            };
            command = lib.mkOption { type = lib.types.str; };
            args = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
            };
          };
        });
        default = {};
        description = "Additional MCP servers for this user";
      };

      neovimIntegration = lib.mkOption {
        type = lib.types.bool;
        default = true;
      };

      vscodeIntegration = lib.mkOption {
        type = lib.types.bool;
        default = true;
      };

      shellIntegration = lib.mkOption {
        type = lib.types.bool;
        default = true;
      };
    };

    config = lib.mkIf cfg.enable {
      # Create pipeline configuration directory
      home.file.".config/ai-agent" = {
        source = ./ai-agent-config;
        recursive = true;
      };

      # Generate manifests from Nix config
      home.file.".config/ai-agent/manifests.json".text = builtins.toJSON {
        pipelines = cfg.pipelines;
        mcpServers = cfg.mcpServers;
        serverUrl = cfg.serverUrl;
      };

      # Agent CLI tool
      home.file.".local/bin/ai".source = pkgs.writeShellScript "ai-cli" ''
        #!/usr/bin/env bash
        set -euo pipefail

        AGENT_URL="${cfg.serverUrl}"
        PIPELINE="''${1:-supervisor}"
        QUERY="''${@:2}"

        if [ -z "$QUERY" ]; then
          echo "Usage: ai [pipeline] <query...>"
          echo ""
          echo "Available pipelines:"
          curl -s "$AGENT_URL/api/pipelines" 2>/dev/null | \
            ${pkgs.jq}/bin/jq -r '.[] | "  \(.name): \(.description)"' || \
            echo "  (Unable to fetch - is server running?)"
          exit 1
        fi

        # Query with context
        curl -s -X POST "$AGENT_URL/api/query" \
          -H "Content-Type: application/json" \
          -d "{\"query\": \"$QUERY\", \"context\": \"shell\", \"pipeline\": \"$PIPELINE\"}" | \
          ${pkgs.jq}/bin/jq -r '.response // .error // "No response"'
      '';

      # Neovim configuration
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
                  model = "supervisor",
                  timeout = 30000,
                  temperature = 0.2,
                  max_tokens = 4096,
                },
                behaviour = {
                  auto_suggestions = false,
                  auto_set_highlight_group = true,
                  auto_set_keymaps = true,
                  auto_apply_diff_after_generation = false,
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

      # Shell aliases
      home.shellAliases = lib.mkIf cfg.shellIntegration {
        ai-supervisor = "ai supervisor";
        ai-code = "ai code-expert";
        ai-research = "ai knowledge-scout";
        ai-refactor = "ai refactoring";
        ai-debug = "ai debug";
      };

      # Required packages
      home.packages = with pkgs; [
        curl
        jq
      ];

      programs.neovim.enable = cfg.neovimIntegration;
    };
  };
