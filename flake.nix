{
  description = "AI Coding Assistant Host Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      # Define Flowise version here (update this and run nix flake update)
      # flowiseVersion = "2.1.3";  # ← Change this to update Flowise
      flowiseVersion = "3.0.8";  # ← Change this to update Flowise

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
            flowiseVersion = lib.mkOption {
              type = lib.types.str;
              default = flowiseVersion;
              description = "Flowise Docker image version.";
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
            databasePassword = lib.mkOption {
              type = lib.types.str;
              default = "flowise_default_password";
              description = "Password for Flowise PostgreSQL database user.";
            };
          };

          config = lib.mkIf true {
            users.users.flowise = {
              isSystemUser = true;
              home = "/var/lib/flowise";
              group = "flowise";
            };

            users.groups.flowise = {};

            environment.sessionVariables = {
              SUPERVISOR_AGENT_MODEL = cfg.supervisorAgentModel;
              CODE_AGENT_MODEL = cfg.codeAgentModel;
              CODE_THINKING_AGENT_MODEL = cfg.codeThinkingAgentModel;
              KNOWLEDGE_AGENT_MODEL = cfg.knowledgeAgentModel;
              FLOWISE_BASE_URL = "http://localhost:3000";
              OLLAMA_BASE_URL = "http://localhost:11434";
              CHROMADB_URL = "http://localhost:8000";
              FLOWISE_VERSION = cfg.flowiseVersion;
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
              loadModels = [
                cfg.supervisorAgentModel
                cfg.codeAgentModel
                cfg.codeThinkingAgentModel
                cfg.knowledgeAgentModel
                "nomic-embed-text"
              ];
            };

            # Update PostgreSQL configuration
            services.postgresql = {
              enable = true;
              ensureDatabases = [ "flowise" ];
              ensureUsers = [{
                name = "flowise";
                ensureDBOwnership = true;
              }];

              # Enable password authentication for localhost
              authentication = lib.mkOverride 10 ''
                local all all peer
                host flowise flowise 127.0.0.1/32 scram-sha-256
                host flowise flowise ::1/128 scram-sha-256
              '';
            };

            services.chromadb = {
              enable = true;
              host = "127.0.0.1";
              port = 8000;
            };

            hardware.graphics = lib.mkIf cfg.gpuAcceleration {
              enable = true;
              enable32Bit = true;
            };

            virtualisation.docker = {
              enable = true;
              enableNvidia = cfg.gpuAcceleration;
            };

            # Add activation script to set PostgreSQL password
            system.activationScripts.setFlowisePassword = lib.stringAfter [ "users" ] ''
              # Set password for flowise user
              ${pkgs.sudo}/bin/sudo -u postgres ${config.services.postgresql.package}/bin/psql -c "ALTER USER flowise WITH PASSWORD '${cfg.databasePassword}';" || true
            '';

            # Add this service before the flowise service
            systemd.services.flowise-image-pull = {
              description = "Pre-pull Flowise Docker Image";
              after = [ "docker.service" ];
              requires = [ "docker.service" ];
              wantedBy = [ "multi-user.target" ];

              serviceConfig = {
                Type = "oneshot";
                RemainAfterExit = true;
                TimeoutStartSec = "10min";  # Generous timeout for slow connections
                ExecStart = "${pkgs.docker}/bin/docker pull flowiseai/flowise:${cfg.flowiseVersion}";
              };
            };

            systemd.services.flowise-init = {
              description = "Initialize Flowise Admin Account";
              after = [ "flowise-image-pull.service" "postgresql.service" ];
              requires = [ "flowise-image-pull.service" "postgresql.service" ];
              wantedBy = [ "multi-user.target" ];

              serviceConfig = {
                Type = "oneshot";
                RemainAfterExit = true;

                ExecStart = pkgs.writeShellScript "init-flowise" ''
                  # Wait for Flowise to be ready
                  for i in {1..30}; do
                    if ${pkgs.curl}/bin/curl -s http://localhost:3000 >/dev/null 2>&1; then
                      echo "Flowise is ready, checking if setup is needed..."

                      # Check if setup page is showing (indicates no account exists)
                      RESPONSE=$(${pkgs.curl}/bin/curl -s http://localhost:3000/api/v1/verify)

                      if echo "$RESPONSE" | grep -q "error\|unauthorized"; then
                        echo "Creating admin account..."

                        # Create account via API
                        ${pkgs.curl}/bin/curl -X POST http://localhost:3000/api/v1/setup \
                          -H "Content-Type: application/json" \
                          -d '{
                            "existingUsername": "admin",
                            "existingPassword": "${cfg.flowisePassword}",
                            "username": "Admin",
                            "email": "admin@localhost",
                            "password": "${cfg.flowisePassword}"
                          }'

                        echo "Admin account created"
                      else
                        echo "Account already exists, skipping setup"
                      fi

                      exit 0
                    fi
                    sleep 2
                  done

                  echo "Warning: Could not connect to Flowise for initialization"
                  exit 0  # Don't fail, user can setup manually
                '';
              };
            };

            # Flowise Docker service with pinned version
            systemd.services.flowise = {
              description = "Flowise AI Flow Builder (Docker v${cfg.flowiseVersion})";
              after = [ "flowise-init.service" "flowise-image-pull.service" "network-online.target" "postgresql.service" "chromadb.service" "ollama.service" "docker.service" ];
              wants = [ "network-online.target" ];
              requires = [ "flowise-image-pull.service" "postgresql.service" "chromadb.service" "ollama.service" "docker.service" ];

              serviceConfig = {
                Type = "simple";
                TimeoutStartSec = "2min";

                ExecStartPre = [
                  "-${pkgs.docker}/bin/docker rm -f flowise"
                ];

                ExecStart = pkgs.writeShellScript "start-flowise" ''
                  ${pkgs.docker}/bin/docker run --rm \
                    --name flowise \
                    --network host \
                    -e PORT=3000 \
                    -e FLOWISE_USERNAME=admin \
                    -e FLOWISE_PASSWORD=${cfg.flowisePassword} \
                    -e FLOWISE_SECRETKEY_OVERWRITE=${if cfg.flowiseSecretKey == "" then "change_me_random_secret_key" else cfg.flowiseSecretKey} \
                    -e DATABASE_TYPE=postgres \
                    -e DATABASE_HOST=127.0.0.1 \
                    -e DATABASE_PORT=5432 \
                    -e DATABASE_NAME=flowise \
                    -e DATABASE_USER=flowise \
                    -e DATABASE_PASSWORD=${cfg.databasePassword} \
                    -e APIKEY_PATH=/root/.flowise \
                    -e SECRETKEY_PATH=/root/.flowise \
                    -e LOG_PATH=/root/.flowise/logs \
                    -e BLOB_STORAGE_PATH=/root/.flowise/storage \
                    -e DISABLE_FLOWISE_TELEMETRY=true \
                    -e OLLAMA_BASE_URL=http://localhost:11434 \
                    -e CHROMADB_URL=http://localhost:8000 \
                    -e SUPERVISOR_AGENT_MODEL=${cfg.supervisorAgentModel} \
                    -e CODE_AGENT_MODEL=${cfg.codeAgentModel} \
                    -e CODE_THINKING_AGENT_MODEL=${cfg.codeThinkingAgentModel} \
                    -e KNOWLEDGE_AGENT_MODEL=${cfg.knowledgeAgentModel} \
                    -v flowise-data:/root/.flowise \
                    flowiseai/flowise:${cfg.flowiseVersion}
                '';

                ExecStop = "${pkgs.docker}/bin/docker stop flowise";
                Restart = "on-failure";
                RestartSec = "30s";
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

      # Export version for inspection
      version = flowiseVersion;
    };
}
