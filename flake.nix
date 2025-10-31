{
  description = "AI Coding Assistant Host Configuration with Model Options";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; config.allowUnfree = true; };
        lib = pkgs.lib;
      in
      {
        nixosModules.ai-coding-assistant = { config, pkgs, lib, ... }:
          let
            cfg = config.aiCodingAssistant;
          in
          {
            options = {
              aiCodingAssistant = {
                gpuAcceleration = lib.mkOption {
                  type = lib.types.bool;
                  default = true;
                  description = "Enable GPU acceleration for Ollama.";
                };
                flowisePassword = lib.mkOption {
                  type = lib.types.str;
                  default = "changeme";
                  description = "Password for Flowise dashboard login.";
                };
                flowiseSecretKey = lib.mkOption {
                  type = lib.types.str;
                  default = "";
                  description = "Secret key for Flowise dashboard security.";
                };
                projectsFileSystemPaths = lib.mkOption {
                  type = lib.types.listOf lib.types.str;
                  default = [];
                  example = [ "/home/user/projects" ];
                  description = "List of directories exposed via bind mount to MCP tools.";
                };

                # New model mapping options
                supervisorAgentModel = lib.mkOption {
                  type = lib.types.str;
                  default = "qwen2.5-coder:7b";
                  description = "Model name for the Supervisor (Router) agent.";
                };
                codeAgentModel = lib.mkOption {
                  type = lib.types.str;
                  default = "qwen2.5-coder:14b";
                  description = "Model name for the Code Expert agent (fast path).";
                };
                codeThinkingAgentModel = lib.mkOption {
                  type = lib.types.str;
                  default = "deepseek-coder:33b";
                  description = "Model name for the Code Thinking agent (complex refactoring).";
                };
                knowledgeAgentModel = lib.mkOption {
                  type = lib.types.str;
                  default = "qwen2.5-coder:70b";
                  description = "Model name for the Knowledge Scout agent (research and synthesis).";
                };
              };
            };

            config = lib.mkIf true {
              users.users = {
                flowise = { isSystemUser = true; home = "/var/lib/flowise"; };
                chromadb = { isSystemUser = true; home = "/var/lib/chromadb"; };
              };

              services.ollama = {
                enable = true;
                acceleration = if cfg.gpuAcceleration then "cuda" else "none";
                listenAddress = "0.0.0.0:11434";
                environmentVariables = {
                  OLLAMA_NUM_PARALLEL = "4";
                  OLLAMA_MAX_LOADED_MODELS = "3";
                };
              };

              services.postgresql = {
                enable = true;
                ensureDatabases = [ "flowise" ];
                ensureUsers = [ { name = "flowise"; ensureDBOwnership = true; } ];
              };

              virtualisation.docker = {
                enable = true;
                enableNvidia = cfg.gpuAcceleration;
              };

              systemd.services.chromadb = {
                description = "Chroma Vector Database";
                after = [ "network-online.target" ];
                wants = [ "network-online.target" ];
                serviceConfig = {
                  Type = "simple";
                  User = "chromadb";
                  ExecStart = "${pkgs.docker}/bin/docker run --rm --network=host ghcr.io/chroma-core/chroma:latest";
                  Restart = "on-failure";
                  StateDirectory = "chromadb";
                  StateDirectoryMode = "0750";
                };
                wantedBy = [ "multi-user.target" ];
              };

              systemd.services.flowise = {
                description = "Flowise AI Flow Builder";
                after = [ "network-online.target" ];
                wants = [ "network-online.target" ];
                serviceConfig = {
                  Type = "simple";
                  User = "flowise";
                  Group = "flowise";
                  ExecStart = "${pkgs.nodejs_22}/bin/npx flowise start";
                  WorkingDirectory = "/var/lib/flowise";
                  Restart = "on-failure";
                  Environment = [
                    "FLOWISE_USERNAME=admin"
                    "FLOWISE_PASSWORD=${cfg.flowisePassword}"
                    "FLOWISE_SECRETKEY_OVERWRITE=${if cfg.flowiseSecretKey == "" then "change_me_random_secret_key" else cfg.flowiseSecretKey}"
                    "DATABASE_TYPE=postgres"
                    "DATABASE_HOST=/run/postgresql"
                    "DATABASE_PORT=5432"
                    "DATABASE_NAME=flowise"
                    "DATABASE_USER=flowise"
                    "OLLAMA_BASE_URL=http://localhost:11434"
                    "CHROMADB_URL=http://localhost:8000"
                    # Model assignments for agents
                    "SUPERVISOR_AGENT_MODEL=${cfg.supervisorAgentModel}"
                    "CODE_AGENT_MODEL=${cfg.codeAgentModel}"
                    "CODE_THINKING_AGENT_MODEL=${cfg.codeThinkingAgentModel}"
                    "KNOWLEDGE_AGENT_MODEL=${cfg.knowledgeAgentModel}"
                  ];
                  StateDirectory = "flowise";
                  StateDirectoryMode = "0750";
                };
                wantedBy = [ "multi-user.target" ];
              };

              environment.systemPackages = with pkgs; [
                nodejs_22
                python311
                python311Packages.pip
                git
                gh
                git-lfs
                ollama
                docker
                direnv
                btop
                nvtop
              ];

              fileSystems = lib.mkMerge (map (path: {
                key = "/mnt/agent-workspace-" + (lib.substring 0 6 (lib.baseNameOf path));
                value = {
                  device = path;
                  fsType = "none";
                  options = [ "bind" "ro" ];
                };
              }) cfg.projectsFileSystemPaths);
            };
          };
      }
    );
}
