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

      devShells = flake-utils.lib.eachDefaultSystem (system: let
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
      });

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

      homeManagerModules = {
        default = (import ./home-manager-module/default.nix) {
          inherit pkgs lib;
          aiAgentRuntime = aiAgentRuntime;
        };
      };
    };
}
