{
  description = "AI Coding Assistant Host Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      aiCodingAssistantModule = { config, pkgs, lib, ... }:
        let
          cfg = config.aiCodingAssistant;
        in
        {
          options.aiCodingAssistant = {
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
            supervisorAgentModel = lib.mkOption {
              type = lib.types.str;
              default = "qwen2.5-coder:7b";
              description = "Model for Supervisor (Router) agent.";
            };
            codeAgentModel = lib.mkOption {
              type = lib.types.str;
              default = "qwen2.5-coder:14b";
              description = "Model for Code Expert agent.";
            };
            codeThinkingAgentModel = lib.mkOption {
              type = lib.types.str;
              default = "deepseek-coder:33b";
              description = "Model for Code Thinking agent.";
            };
            knowledgeAgentModel = lib.mkOption {
              type = lib.types.str;
              default = "qwen2.5-coder:70b";
              description = "Model for Knowledge Scout agent.";
            };
          };

          config = lib.mkIf true {
            users.users = {
              flowise = {
                isSystemUser = true;
                home = "/var/lib/flowise";
                group = "flowise";
              };
            };

            users.groups = {
              flowise = {};
            };

            services.ollama = {
              enable = true;
              acceleration = if cfg.gpuAcceleration then "cuda" else null;
              host = "0.0.0.0";
              port = 11434;
              environmentVariables = {
                OLLAMA_NUM_PARALLEL = "4";
                OLLAMA_MAX_LOADED_MODELS = "3";
              };
            };

            services.postgresql = {
              enable = true;
              ensureDatabases = [ "flowise" ];
              ensureUsers = [ {
                name = "flowise";
                ensureDBOwnership = true;
              }];
            };

            # Native ChromaDB service instead of Docker
            services.chromadb = {
              enable = true;
              host = "127.0.0.1";
              port = 8000;
            };

            # Only enable Docker and 32-bit graphics if GPU acceleration is enabled
            hardware.graphics = lib.mkIf cfg.gpuAcceleration {
              enable = true;
              enable32Bit = true;
            };

            virtualisation.docker = lib.mkIf cfg.gpuAcceleration {
              enable = true;
              enableNvidia = true;
            };

            systemd.services.flowise = {
              description = "Flowise AI Flow Builder";
              after = [ "network-online.target" "postgresql.service" "chromadb.service" ];
              wants = [ "network-online.target" ];
              requires = [ "postgresql.service" "chromadb.service" ];
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
              direnv
              btop
            ] ++ lib.optionals cfg.gpuAcceleration [
              docker
              nvtopPackages.full
            ];

            fileSystems = lib.listToAttrs (lib.imap0 (i: path: {
              name = "/mnt/agent-workspace-${toString i}";
              value = {
                device = path;
                fsType = "none";
                options = [ "bind" "ro" ];
              };
            }) cfg.projectsFileSystemPaths);
          };
        };
    in
    {
      nixosModules.default = aiCodingAssistantModule;
      nixosModules.ai-coding-assistant = aiCodingAssistantModule;
    };
}
