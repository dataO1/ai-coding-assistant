# home-manager-module/default.nix - USER LEVEL

{ config, lib, pkgs, ... }:

let
  cfg = config.programs.aiAgent;

  # Pipeline discovery: scan user's pipeline directory
  pipelineDir = "${config.home.configHome}/ai-agent/pipelines";

  # Pipeline module
  pipelineModule = lib.types.submodule {
    options = {
      description = lib.mkOption { type = lib.types.str; };
      model = lib.mkOption { type = lib.types.str; };

      # Context requirements
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

      # Context sources this pipeline works with
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
    };

    # User-defined pipelines (ONLY at user level)
    pipelines = lib.mkOption {
      type = lib.types.attrsOf pipelineModule;
      default = {};
      description = "User-defined AI agent pipelines";
    };

    # Local MCP servers (extend system MCPs)
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
    home.file = {
      # Create pipeline directory
      ".config/ai-agent/pipelines/.gitkeep".text = "";

      # Pipeline manifests (generated from Nix config)
      ".config/ai-agent/manifests.json".text = builtins.toJSON {
        pipelines = cfg.pipelines;
        mcpServers = cfg.mcpServers;
      };

      # Agent CLI
      ".local/bin/ai".source = pkgs.writeShellScript "ai-cli" ''
        #!/usr/bin/env bash
        AGENT_URL="${cfg.serverUrl}"
        PIPELINE="''${1:-coding}"
        QUERY="''${@:2}"

        if [ -z "$QUERY" ]; then
          echo "Usage: ai <pipeline> <query...>"
          curl -s "$AGENT_URL/api/pipelines" | ${pkgs.jq}/bin/jq -r '.[] | "  - \(.name): \(.description)"'
          exit 1
        fi

        curl -s -X POST "$AGENT_URL/api/query" \
          -H "Content-Type: application/json" \
          -d "{\"pipeline\": \"$PIPELINE\", \"query\": \"$QUERY\", \"context\": \"shell\"}" | \
          ${pkgs.jq}/bin/jq -r '.response // .error'
      '';

      # Neovim config
      ".config/nvim/lua/plugins/ai-agent.lua" = lib.mkIf cfg.neovimIntegration {
        text = ''
          return {
            {
              "yetone/avante.nvim",
              event = "VeryLazy",
              opts = {
                provider = "openai",
                openai = {
                  endpoint = "${cfg.serverUrl}/v1",
                  model = "local",
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
    };

    programs.neovim.enable = cfg.neovimIntegration;
    programs.vscode.enable = cfg.vscodeIntegration;
  };
}
