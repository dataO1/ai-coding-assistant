# Example NixOS configuration using agent-network service

# In your /etc/nixos/configuration.nix or a flake module:

{
  # Enable the service
  services.agent-network = {
    enable = true;

    # LLM Configuration
    llmProvider = "openai";
    llmModel = "gpt-4";
    llmApiKey = "sk-..."; # Better: use sops-nix or similar

    # Database
    databaseType = "chromadb";
    databasePath = /var/lib/agent-network/vectordb;

    # Resources
    maxWorkers = 3;

    # State
    stateDir = /var/lib/agent-network;
    docsPath = /var/lib/agent-network/docs;
  };

  # Optional: Monitor service health
  systemd.timers.agent-network-health-check = {
    enable = true;
    timerConfig = {
      OnBootSec = "5m";
      OnUnitActiveSec = "5m";
    };
    wantedBy = [ "timers.target" ];
  };

  systemd.services.agent-network-health-check = {
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.curl}/bin/curl -f http://localhost:8000/health";
      OnFailure = "agent-network.service";
    };
  };
}
