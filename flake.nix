# flake.nix - Nix Flakes Configuration for Agentic IDE Backend

{
  description = "Agentic IDE Backend - LLM-orchestrated multi-agent code generation system";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        poetry2nix-lib = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
      in
      {
        packages = {
          agentic-ide-backend = poetry2nix-lib.mkPoetryApplication {
            projectDir = ./.;
            python = pkgs.python311;
            
            # Runtime dependencies
            propagatedBuildInputs = with pkgs; [
              # System dependencies
              git
              libsodium
              
              # Language servers for MCP integration
              python311Packages.pylsp
              nodePackages.typescript-language-server
              rust-analyzer
            ];
            
            # Build-time dependencies
            buildInputs = with pkgs; [
              python311
              poetry
              git
            ];
            
            # Environment variables for build
            PYTHONPATH = "$PWD:$PYTHONPATH";
          };
          
          agentic-ide-backend-dev = pkgs.mkShell {
            buildInputs = with pkgs; [
              python311
              poetry
              git
              gcc
              pkg-config
              
              # For local development
              redis  # For testing/local dev
              docker-compose
              
              # CLI tools
              curl
              jq
              
              # Optional: debugging
              python311Packages.ipython
              python311Packages.pdbpp
            ];
            
            shellHook = ''
              # Python environment setup
              export PYTHONPATH="$PWD:$PYTHONPATH"
              
              # Poetry configuration
              export POETRY_VIRTUALENVS_IN_PROJECT=true
              export POETRY_NO_INTERACTION=1
              
              # Development environment
              echo "Agentic IDE Backend Dev Environment"
              echo "====================================="
              python --version
              poetry --version
              
              # Create .env if not exists
              if [ ! -f .env ]; then
                cat > .env << 'EOF'
              ENVIRONMENT=development
              LOG_LEVEL=debug
              OLLAMA_BASE_URL=http://localhost:11434
              QDRANT_URL=http://localhost:6333
              BACKEND_PORT=8000
              BACKEND_HOST=0.0.0.0
              EOF
                echo "Created .env file"
              fi
            '';
          };
        };

        devShells.default = self.devShells.${system}.agentic-ide-backend-dev;
        
        defaultPackage = self.packages.${system}.agentic-ide-backend;

        # Docker image definition (optional)
        packages.docker-image = pkgs.dockerTools.buildLayeredImage {
          name = "agentic-ide-backend";
          tag = "latest";
          
          contents = [
            self.packages.${system}.agentic-ide-backend
            pkgs.cacert  # SSL certificates
          ];
          
          config = {
            Cmd = [ "uvicorn" "backend.main:app" "--host" "0.0.0.0" "--port" "8000" ];
            Env = [
              "PYTHONUNBUFFERED=1"
              "PYTHONPATH=/app"
            ];
            WorkingDir = "/app";
            ExposedPorts = {
              "8000/tcp" = {};
            };
          };
        };

        # Apps for easy running
        apps = {
          dev = {
            type = "app";
            program = "${pkgs.writeShellScript "dev" ''
              ${pkgs.poetry}/bin/poetry install
              ${pkgs.poetry}/bin/poetry run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
            ''}";
          };
          
          test = {
            type = "app";
            program = "${pkgs.writeShellScript "test" ''
              ${pkgs.poetry}/bin/poetry run pytest tests/ -v --cov=backend
            ''}";
          };
        };

        # Default app
        defaultApp = self.apps.${system}.dev;
      }
    );
}
