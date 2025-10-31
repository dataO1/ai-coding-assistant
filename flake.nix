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
              chromadb = {
                isSystemUser = true;
                home = "/var/lib/chromadb";
                group = "chromadb";
              };
            };

            users.groups = {
              flowise = {};
              chromadb = {};
            };

            # Fixed: Use host and port instead of listenAddress
            services.ollama = {
              enable = true;
              acceleration = if cfg.gpuAcceleration then "cuda" else null;
              host = "0.0.0.0";  # ← Changed from listenAddress
              port = 11434;     # ← Split into separate option
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

            # Fixed: Enable 32-bit support libraries for NVIDIA
            hardware.graphics = lib.mkIf cfg.gpuAcceleration {
              enable = true;
              enable32Bit = true;  # ← Required for enableNvidia
            };

            virtualisation.docker = {
              enable = true;
              enableNvidia = cfg.gpuAcceleration;
            };

            systemd.services.chromadb = {
              description = "Chroma Vector Database";
              after = [ "network-online.target" "docker.service" ];
              wants = [ "network-online.target" ];
              requires = [ "docker.service" ];
              serviceConfig = {
                Type = "simple";
                User = "chromadb";
                Group = "chromadb";
                ExecStart = "${pkgs.docker}/bin/docker run --rm --name chromadb --network=host chromadb/chroma:latest";
                ExecStop = "${pkgs.docker}/bin/docker stop chromadb";
                Restart = "on-failure";
                StateDirectory = "chromadb";
                StateDirectoryMode = "0750";
              };
              wantedBy = [ "multi-user.target" ];
            };

            systemd.services.flowise = {
              description = "Flowise AI Flow Builder";
              after = [ "network-online.target" "postgresql.service" ];
              wants = [ "network-online.target" ];
              requires = [ "postgresql.service" ];
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
              docker
              direnv
              btop
              nvtop
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
