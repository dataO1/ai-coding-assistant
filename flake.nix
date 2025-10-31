{
  nixosModules.aiCodingAssistant = { config, lib, pkgs, ... }: {
    options.aiCodingAssistant = {
      enable = lib.mkEnableOption "AI Coding Assistant";

      models = lib.mkOption {
        type = lib.types.attrsOf lib.types.str;
        default = {
          supervisor = "qwen2.5-coder:7b";
          code = "qwen2.5-coder:14b";
          research = "qwen2.5-coder:70b";
        };
      };

      mcpServers = lib.mkOption {
        type = lib.types.attrsOf (lib.types.submodule {
          options = {
            enable = lib.mkEnableOption "MCP Server";
            command = lib.mkOption { type = lib.types.str; };
            args = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
          };
        });
        default = {
          tree-sitter = {
            enable = true;
            command = "${pkgs.python311Packages.mcp-server-tree-sitter}/bin/mcp-server-tree-sitter";
          };
          lsp = {
            enable = true;
            command = "${pkgs.nodejs}/bin/npx";
            args = [ "tritlo/lsp-mcp" "python" "pylsp" ];
          };
          git = {
            enable = true;
            command = "${pkgs.nodejs}/bin/npx";
            args = [ "@modelcontextprotocol/server-git" ];
          };
        };
      };
    };

    config = lib.mkIf config.aiCodingAssistant.enable {
      # Ollama with models
      services.ollama = {
        enable = true;
        loadModels = lib.attrValues config.aiCodingAssistant.models;
      };

      # Agent server systemd service
      systemd.services.ai-agent-server = {
        description = "LangChain Agent Server";
        after = [ "ollama.service" ];
        wantedBy = [ "multi-user.target" ];

        environment = {
          MCP_SERVERS_CONFIG = builtins.toJSON config.aiCodingAssistant.mcpServers;
          MODELS_CONFIG = builtins.toJSON config.aiCodingAssistant.models;
        };

        serviceConfig = {
          ExecStart = "${pkgs.python311}/bin/python ${./agent-server}/main.py";
          Restart = "on-failure";
        };
      };
    };
  };
}
