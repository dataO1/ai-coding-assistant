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
      # Python environment for the runtime
      pythonEnv = pkgs: pkgs.python311.withPackages (ps: with ps; [
        langchain
        langchain-community
        langchain-openai
        fastapi
        uvicorn
        pydantic
        pydantic-settings
        langgraph
      ]);
      lib = nixpkgs.lib;

      # Build the runtime package
      aiAgentRuntime = pkgs.stdenv.mkDerivation {
        name = "ai-agent-runtime";
        src = ./ai-agent-runtime;

        buildInputs = [ (pythonEnv pkgs) ];

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
          exec ${(pythonEnv pkgs)}/bin/python -m ai_agent_runtime.server "\$@"
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
        buildinputs = with pkgs; [
          python311
          nodejs_22
          git
        ];

        shellhook = ''
          echo "install python deps with: pip install langchain langchain-community langchain-openai fastapi uvicorn pydantic langgraph"
        '';
      };

      # ========================================================================
      # NixOS Module (top-level exports)
      # ========================================================================

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.services.aiAgent;
          system = "x86_64-linux";
          pkgs = nixpkgs.legacyPackages.${system};
          lib = nixpkgs.lib;
          aiAgentRuntime = self.packages.${pkgs.system}.ai-agent-runtime;
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

      # ========================================================================
      # Home Manager Module
      # ========================================================================

    # Fix here: call the import with required params
    homeManagerModules.default = (import ./home-manager-module/default.nix) {
      inherit pkgs lib aiAgentRuntime;
    };

  });
}
