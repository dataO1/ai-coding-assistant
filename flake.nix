{
  description = "AI Coding Assistant Host Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;
      flowiseVersion = "3.0.8";

      # Load Flowise config
      flowiseConfigLib = import ./flowise-config/lib.nix;

      loadFlowiseAgents = { models, urls }:
        {
          supervisor = import ./flowise-config/agents/supervisor.nix { inherit models urls; };
          codeExpert = import ./flowise-config/agents/code-expert.nix { inherit models urls; };
          knowledgeScout = import ./flowise-config/agents/knowledge-scout.nix { inherit models urls; };
        };

      generateFlowiseWorkflow = { models, urls }:
        let
          agents = loadFlowiseAgents { inherit models urls; };
        in
        import ./flowise-config/flows/main-workflow.nix {
          inherit agents models urls lib;
          flowiseLib = flowiseConfigLib;
        };

      aiCodingAssistantModule = { config, pkgs, lib, ... }:
        let
          cfg = config.aiCodingAssistant;

          # Generate Flowise workflow JSON with runtime config
          flowiseModels = {
            supervisor = cfg.supervisorAgentModel;
            codeAgent = cfg.codeAgentModel;
            codeThinking = cfg.codeThinkingAgentModel;
            knowledge = cfg.knowledgeAgentModel;
          };

          flowiseUrls = {
            ollama = "http://localhost:11434";
            chromadb = "http://localhost:8000";
          };

          mainWorkflow = generateFlowiseWorkflow { models = flowiseModels; urls = flowiseUrls; };
          workflowJson = builtins.toJSON mainWorkflow;
        in
        {
          gpuAcceleration = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable GPU acceleration for Ollama.";
            };

            flowiseEmail = lib.mkOption {
              type = lib.types.str;
              description = "Admin user email (acts as your login username).";
              example = "admin@localhost";
            };

            flowisePassword = lib.mkOption {
              type = lib.types.str;
              description = "Password for Flowise dashboard login.";
              example = "MySecure@Pass123!";
            };

          # Add assertion to validate password
            flowiseSecretKey = lib.mkOption {
              type = lib.types.str;
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

            assertions = [
              {
                assertion = builtins.stringLength cfg.flowisePassword >= 8 &&
                            builtins.match ".*[a-z].*" cfg.flowisePassword != null &&
                            builtins.match ".*[A-Z].*" cfg.flowisePassword != null &&
                            builtins.match ".*[0-9].*" cfg.flowisePassword != null &&
                            builtins.match ".*[^a-zA-Z0-9].*" cfg.flowisePassword != null;
                message = ''
                  aiCodingAssistant.flowisePassword must be at least 8 characters long
                  and contain at least one lowercase letter, one uppercase letter,
                  one digit, and one special character.

                  Example: MySecure@Pass123!
                '';
              }
            ];

            users.groups.flowise = {};

            # Setup Flowise configs directly in home
          # Setup Flowise configs AFTER PostgreSQL is ready
            system.activationScripts.setupFlowiseConfigs = lib.stringAfter [ "postgresql" "setFlowisePassword" ] ''
              FLOWISE_HOME="/var/lib/flowise"
              FLOWS_DIR="$FLOWISE_HOME/flows"
              CONFIG_SOURCE="${self}/flowise-config"

              echo "Setting up Flowise configuration..."

              ${pkgs.coreutils}/bin/install -d -m 750 -o flowise -g flowise "$FLOWS_DIR"

              # Copy JSON files
              if [ -d "$CONFIG_SOURCE" ]; then
                ${pkgs.findutils}/bin/find "$CONFIG_SOURCE" -maxdepth 1 -name '*.json' -exec \
                  ${pkgs.coreutils}/bin/install -m 644 -o flowise -g flowise {} "$FLOWS_DIR/" \;
                echo "✅ Workflow JSON files copied"
              fi

              # Import workflows into database (no public API endpoint for this)
              echo "Importing workflows into database..."

              for json_file in "$FLOWS_DIR"/*.json; do
                if [ -f "$json_file" ]; then
                  FLOW_NAME=$(basename "\'\'${json_file%.json}")
                  FLOW_DATA=$(${pkgs.jq}/bin/jq -c . "$json_file")

                  # Escape single quotes for SQL
                  FLOW_DATA_ESCAPED=$(echo "$FLOW_DATA" | sed "s/'/\'\'/g")

                  # Insert into database
                  ${pkgs.sudo}/bin/sudo -u postgres ${config.services.postgresql.package}/bin/psql -d flowise << SQL 2>/dev/null || true
                    INSERT INTO chat_flow (name, "flowData", "createdDate", "updatedDate")
                    VALUES ('$FLOW_NAME', '$FLOW_DATA_ESCAPED', NOW(), NOW())
                    ON CONFLICT (name) DO UPDATE SET
                      "flowData" = EXCLUDED."flowData",
                      "updatedDate" = NOW();
                  SQL

                  echo "✅ Imported: $FLOW_NAME"
                fi
              done
            '';

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
          # Set PostgreSQL password AFTER database is ready
            system.activationScripts.setFlowisePassword = lib.stringAfter [ "postgresql" ] ''
              echo "Setting Flowise database user password..."
              ${pkgs.sudo}/bin/sudo -u postgres ${config.services.postgresql.package}/bin/psql -c "ALTER USER flowise WITH PASSWORD '${cfg.databasePassword}';" 2>/dev/null || true
              echo "✅ Database password set"
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
              description = "Initialize Flowise Admin Account and Import Workflows";
              after = [ "flowise.service" ];
              requires = [ "flowise.service" ];
              wantedBy = [ "multi-user.target" ];

              serviceConfig = {
                Type = "oneshot";
                RemainAfterExit = true;

                ExecStart = pkgs.writeShellScript "init-flowise" ''
                  FLOWISE_URL="http://localhost:3000"
                  FLOWISE_ADMIN_USER="admin"
                  FLOWISE_ADMIN_PASS="${cfg.flowisePassword}"
                  FLOWISE_EMAIL="${cfg.flowiseEmail}"

                  echo "Waiting for Flowise to start..."
                  for i in {1..60}; do
                    if ${pkgs.curl}/bin/curl -s "$FLOWISE_URL" >/dev/null 2>&1; then
                      echo "✅ Flowise is ready"
                      break
                    fi
                    sleep 2
                  done

                  # Setup admin account if needed via API endpoint: POST /api/v1/setup
                  echo "Checking if admin account exists..."
                  VERIFY=$(${pkgs.curl}/bin/curl -s -u "$FLOWISE_ADMIN_USER:$FLOWISE_ADMIN_PASS" \
                    "$FLOWISE_URL/api/v1/verify" 2>/dev/null || echo '{"error":"failed"}')

                  if echo "$VERIFY" | grep "Unauthorized"; then
                    echo "Creating admin account via /api/v1/setup..."
                    ${pkgs.curl}/bin/curl -s -X POST "$FLOWISE_URL/api/v1/setup" \
                      -u "$FLOWISE_ADMIN_USER:$FLOWISE_ADMIN_PASS" \
                      -H "Content-Type: application/json" \
                      -d "{
                        \"existingUsername\": \"admin\",
                        \"existingPassword\": \"$FLOWISE_ADMIN_PASS\",
                        \"username\": \"Admin\",
                        \"email\": \"$FLOWISE_EMAIL\",
                        \"password\": \"$FLOWISE_ADMIN_PASS\"
                      }" >/dev/null 2>&1
                    echo "✅ Admin account created"
                    sleep 2
                  else
                    echo "✅ Admin account already exists"
                  fi

                  echo "✅ Flowise initialization complete"
                '';
              };
            };
            # Flowise Docker service with pinned version
            systemd.services.flowise = {
              description = "Flowise AI Flow Builder (Docker v${cfg.flowiseVersion})";
              after = ["flowise-image-pull.service" "network-online.target" "postgresql.service" "chromadb.service" "ollama.service" "docker.service" ];
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
                    -e FLOWISE_SECRETKEY_OVERWRITE=${cfg.flowiseSecretKey} \
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
