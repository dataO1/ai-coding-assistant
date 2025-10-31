# flake.nix - SYSTEM LEVEL ONLY

nixosModules.aiCodingAssistant = { config, lib, pkgs, ... }:
  let
    cfg = config.aiCodingAssistant;

    pythonEnv = pkgs.python311.withPackages (ps: with ps; [
      langchain
      langchain-community
      langchain-openai
      fastapi
      uvicorn
      langgraph
      pydantic
      pydantic-settings
    ]);
  in
  {
    options.aiCodingAssistant = {
      enable = lib.mkEnableOption "AI Agent base infrastructure";

      gpuAcceleration = lib.mkOption {
        type = lib.types.bool;
        default = true;
      };

      ollamaHost = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
      };

      ollamaPort = lib.mkOption {
        type = lib.types.port;
        default = 11434;
      };

      agentServerPort = lib.mkOption {
        type = lib.types.port;
        default = 8080;
      };

      models = lib.mkOption {
        type = lib.types.attrsOf lib.types.str;
        description = "Base models available to all users";
        default = {
          supervisor = "qwen2.5-coder:7b";
          code = "qwen2.5-coder:14b";
          research = "qwen2.5-coder:70b";
        };
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
        description = "Global MCP servers (can be extended per-user)";
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
      };

      # Agent server systemd service
      systemd.services.ai-agent-server = {
        description = "AI Agent Server (Pipeline runtime)";
        after = [ "ollama.service" "network-online.target" ];
        wants = [ "network-online.target" ];
        requires = [ "ollama.service" ];
        wantedBy = [ "multi-user.target" ];

        environment = {
          OLLAMA_BASE_URL = "http://${cfg.ollamaHost}:${toString cfg.ollamaPort}";
          AGENT_SERVER_PORT = toString cfg.agentServerPort;
          PYTHONUNBUFFERED = "1";
        };

        serviceConfig = {
          Type = "simple";
          # Load pipelines from user's .config/ai-agent/pipelines/
          ExecStart = "${pythonEnv}/bin/python /etc/ai-agent/runtime/server.py";
          Restart = "on-failure";
          RestartSec = "10s";
        };
      };

      networking.firewall.allowedTCPPorts = [ cfg.agentServerPort ];

      environment.systemPackages = with pkgs; [
        nodejs
        git
        curl
        pythonEnv
      ];
    };
  };
