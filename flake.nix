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
        pydantic
        pydantic-settings
        langgraph
        pytest
        black
        pylint
        httpx
        aiohttp
      ]);

      # ========================================================================
      # NixOS Module (System Level)
      # ========================================================================

      aiCodingAssistantModule = { config, lib, pkgs, ... }:
        let
          cfg = config.aiCodingAssistant;
        in
        {
          options.aiCodingAssistant = {
            enable = lib.mkEnableOption "AI Agent base infrastructure";

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
              description = "Base models available to all users";
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
              description = "Global MCP servers";
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
              description = "AI Agent Server (Multi-agent Orchestrator)";
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
                ExecStart = "${pythonEnv}/bin/python /etc/ai-agent/runtime/server.py";
                Restart = "on-failure";
                RestartSec = "10s";
                StandardOutput = "journal";
                StandardError = "journal";
              };
            };

            # Allow firewall access
            networking.firewall.allowedTCPPorts = [ cfg.agentServerPort ];

            # System packages
            environment.systemPackages = with pkgs; [
              nodejs
              git
              curl
              pythonEnv
            ] ++ lib.optionals cfg.gpuAcceleration [
              nvtopPackages.full
            ];
          };
        };

      # ========================================================================
      # Home Manager Module (User Level)
      # ========================================================================

      aiAgentUserModule = import ./home-manager-module/default.nix;

    in
    {
      nixosModules.default = aiCodingAssistantModule;
      nixosModules.aiCodingAssistant = aiCodingAssistantModule;

      homeManagerModules.default = aiAgentUserModule;
      homeManagerModules.aiAgent = aiAgentUserModule;
    };
}
