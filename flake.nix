{
  description = "AI Coding Assistant - Multi-agent orchestration with LangChain";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
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
            mkdir -p $out/lib/ai-agent
            mkdir -p $out/bin

            # Copy all runtime code
            cp -r . $out/lib/ai-agent/

            # Create launcher script
            cat > $out/bin/ai-agent-server << 'EOF'
            #!/usr/bin/env bash
            export PYTHONPATH="$out/lib/ai-agent:$PYTHONPATH"
            exec ${pythonEnv}/bin/python "$out/lib/ai-agent/server.py" "$@"
            EOF
            chmod +x $out/bin/ai-agent-server
          '';
        };
      in
      {
        # Export the runtime package
        packages.ai-agent-runtime = aiAgentRuntime;
        packages.default = aiAgentRuntime;

        # Development shell
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            python311Packages.black
            python311Packages.pylint
            python311Packages.pytest
          ];
        };
      }
    ) // {
      # ========================================================================
      # NixOS Module (exported at top level for easy import)
      # ========================================================================

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.services.aiAgent;

          # Get the runtime package for this system
          aiAgentRuntime = self.packages.${pkgs.system}.ai-agent-runtime;

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

            # AI Agent systemd service
            systemd.services.ai-agent-server = {
              description = "AI Agent Server (Multi-agent Orchestrator)";
              after = [ "ollama.service" "network-online.target" ];
              wants = [ "network-online.target" ];
              requires = [ "ollama.service" ];
              wantedBy = [ "multi-user.target" ];

              environment = {
                OLLAMA_BASE_URL = "http://${cfg.ollamaHost}:${toString cfg.ollamaPort}";
                AGENT_SERVER_PORT = toString cfg.port;
                # User manifests come from Home Manager
                AI_AGENT_MANIFESTS = "%h/.config/ai-agent/manifests.json";
                PYTHONUNBUFFERED = "1";
              };

              serviceConfig = {
                Type = "simple";
                ExecStart = "${aiAgentRuntime}/bin/ai-agent-server";
                Restart = "on-failure";
                RestartSec = "10s";
                StartLimitBurst = 5;
                StartLimitInterval = "60s";
                StandardOutput = "journal";
                StandardError = "journal";
              };
            };

            # Firewall
            networking.firewall.allowedTCPPorts = [ cfg.port ];

            # System packages
            environment.systemPackages = with pkgs; [
              nodejs
              git
              curl
              aiAgentRuntime
              pythonEnv
            ] ++ lib.optionals cfg.gpuAcceleration [
              nvtopPackages.full
            ];
          };
        };
        aiAgentUserModule = import ./home-manager-module/default.nix;

    in
    {
      packages.${system}.ai-agent-runtime = aiAgentRuntime;

      nixosModules.default = aiCodingAssistantModule;
      nixosModules.aiCodingAssistant = aiCodingAssistantModule;

      homeManagerModules.default = aiAgentUserModule;
      homeManagerModules.aiAgent = aiAgentUserModule;
    };
}
