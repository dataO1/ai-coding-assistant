{
  description = "AI Coding Assistant Host Configuration with Configurable Options";

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
                  description = "Set to false if host has no GPU or GPU acceleration should be disabled.";
                };
                flowisePassword = lib.mkOption {
                  type = lib.types.str;
                  default = "changeme";  # Encourage user to override
                  description = "Password for Flowise dashboard login.";
                };
                flowiseSecretKey = lib.mkOption {
                  type = lib.types.str;
                  default = ""; # Empty by default, generate or override recommended
                  description = "Secret key to secure Flowise dashboard; should be random hex string.";
                };
                projectsFileSystemPaths = lib.mkOption {
                  type = lib.types.listOf lib.types.str;
                  default = [];
                  example = [ "/home/user/projects" ];
                  description = ''List of host directories to be exposed as read-only bind mounts for MCP servers.
                                  This avoids hardcoding any specific directory.
                                  Can be extended by users or other NixOS modules.'';
                };
              };
            };

            config = lib.mkIf true {
              # Define users for services
              users.users = {
                flowise = { isSystemUser = true; home = "/var/lib/flowise"; };
                chromadb = { isSystemUser = true; home = "/var/lib/chromadb"; };
              };

              # Ollama service with configurable GPU acceleration
              services.ollama = {
                enable = true;
                acceleration = if cfg.gpuAcceleration then "cuda" else "none";
                listenAddress = "0.0.0.0:11434";
                environmentVariables = {
                  OLLAMA_NUM_PARALLEL = "4";
                  OLLAMA_MAX_LOADED_MODELS = "3";
                };
              };

              # PostgreSQL database service for Flowise and LangGraph
              services.postgresql = {
                enable = true;
                ensureDatabases = [ "flowise" ];
                ensureUsers = [ { name = "flowise"; ensureDBOwnership = true; } ];
              };

              # Docker service, GPU passthrough conditional
              virtualisation.docker = {
                enable = true;
                enableNvidia = cfg.gpuAcceleration;
              };

              # ChromaDB service as docker container
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

              # Flowise service with configurable credentials
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
                  ];
                  StateDirectory = "flowise";
                  StateDirectoryMode = "0750";
                };
                wantedBy = [ "multi-user.target" ];
              };

              # Global environment packages present for MCP tooling
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

              # Dynamic bind mounts for MCP servers based on option
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
