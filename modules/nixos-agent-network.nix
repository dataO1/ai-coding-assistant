"""
NixOS module for AG2 Agent Network service.
Usage: services.agent-network in your NixOS configuration.
"""

{ config, lib, pkgs, ... }:

with lib;

{
  options.services.agent-network = {
    enable = mkEnableOption "AG2 Parallel Agent Network Service";

    user = mkOption {
      type = types.str;
      default = "agent-network";
      description = "User to run the service as";
    };

    group = mkOption {
      type = types.str;
      default = "agent-network";
      description = "Group to run the service as";
    };

    llmProvider = mkOption {
      type = types.enum [ "openai" "anthropic" "ollama" ];
      default = "openai";
      description = "LLM provider to use";
    };

    llmModel = mkOption {
      type = types.str;
      default = "gpt-4";
      description = "LLM model identifier";
    };

    llmApiKey = mkOption {
      type = types.str;
      default = "";
      description = "API key for LLM provider";
    };

    databaseType = mkOption {
      type = types.enum [ "chromadb" "qdrant" ];
      default = "chromadb";
      description = "Vector database type";
    };

    databasePath = mkOption {
      type = types.path;
      default = /var/lib/agent-network/vectordb;
      description = "Path to vector database";
    };

    docsPath = mkOption {
      type = types.path;
      default = /var/lib/agent-network/docs;
      description = "Path to documentation for RAG";
    };

    maxWorkers = mkOption {
      type = types.int;
      default = 3;
      description = "Maximum parallel workers";
    };

    port = mkOption {
      type = types.port;
      default = 8000;
      description = "Port for agent network API";
    };

    stateDir = mkOption {
      type = types.path;
      default = /var/lib/agent-network;
      description = "State directory for agent network";
    };

    logLevel = mkOption {
      type = types.enum [ "DEBUG" "INFO" "WARNING" "ERROR" ];
      default = "INFO";
      description = "Logging level";
    };
  };

  config = mkIf config.services.agent-network.enable {
    # Create user and group
    users.users.agent-network = mkIf (config.services.agent-network.user == "agent-network") {
      group = config.services.agent-network.group;
      home = config.services.agent-network.stateDir;
      createHome = true;
      isSystemUser = true;
    };

    users.groups.agent-network = mkIf (config.services.agent-network.group == "agent-network") { };

    # Create systemd service
    systemd.services.agent-network = {
      description = "AG2 Parallel Agent Network";
      documentation = [ "https://github.com/your-org/agent-network" ];

      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];

      serviceConfig = {
        Type = "simple";
        User = config.services.agent-network.user;
        Group = config.services.agent-network.group;
        WorkingDirectory = config.services.agent-network.stateDir;

        # Security hardening
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        NoNewPrivileges = true;
        RestrictRealtime = true;

        # Resource limits
        LimitNOFILE = 65536;
        MemoryLimit = "2G";
        CPUQuota = "80%";

        # Restart policy
        Restart = "on-failure";
        RestartSec = 5;
        StartLimitBurst = 5;
        StartLimitIntervalSec = 300;

        # Environment
        Environment = [
          "LLM_PROVIDER=${config.services.agent-network.llmProvider}"
          "LLM_MODEL=${config.services.agent-network.llmModel}"
          "DB_TYPE=${config.services.agent-network.databaseType}"
          "DB_PATH=${config.services.agent-network.databasePath}"
          "DOCS_PATH=${config.services.agent-network.docsPath}"
          "MAX_WORKERS=${toString config.services.agent-network.maxWorkers}"
          "LOG_LEVEL=${config.services.agent-network.logLevel}"
        ];

        # Start command
        ExecStart = """${pkgs.python311}/bin/python /opt/agent-network/agent_network.py""";
      };
    };

    # Ensure state directories exist
    systemd.tmpfiles.rules = [
      "d ${config.services.agent-network.stateDir} 0700 ${config.services.agent-network.user} ${config.services.agent-network.group} - -"
      "d ${config.services.agent-network.databasePath} 0700 ${config.services.agent-network.user} ${config.services.agent-network.group} - -"
      "d ${config.services.agent-network.docsPath} 0755 ${config.services.agent-network.user} ${config.services.agent-network.group} - -"
    ];
  };
}
