{ config, lib, pkgs, aiAgentRuntime ... }:

let
  cfg = config.programs.aiAgent;
  inherit system;
  pkgs = nixpkgs.legacyPackages.${system};

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
}
