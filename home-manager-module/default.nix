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
      };
      optionalTools = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [];
      };
      fallbackMode = lib.mkOption {
        type = lib.types.enum [ "degrade" "fail" ];
        default = "degrade";
      };
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
    neovimIntegration = lib.mkOption { type = lib.types.bool; default = true; };
    vscodeIntegration = lib.mkOption { type = lib.types.bool; default = true; };
    shellIntegration = lib.mkOption { type = lib.types.bool; default = true; };
  };

  config = lib.mkIf cfg.enable {
    home.file.".config/ai-agent/manifests.json".text = builtins.toJSON {
      pipelines = cfg.pipelines;
    };

    home.file.".local/bin/ai".source = pkgs.writeShellScript "ai-cli" ''
      #!/usr/bin/env bash
      AGENT_URL="${cfg.serverUrl}"
      PIPELINE="''${1:-supervisor}"
      QUERY="''${@:2}"

      if [ -z "$QUERY" ]; then
        echo "Usage: ai [pipeline] <query...>"
        curl -s "$AGENT_URL/api/pipelines" | ${pkgs.jq}/bin/jq -r '.[] | "  \(.name): \(.description)"' 2>/dev/null || true
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
}
