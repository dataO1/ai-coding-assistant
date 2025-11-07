{
  description = "AG2 Parallel Agent Network - Production-grade Multi-Agent Orchestration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python311;
        pythonPackages = python.pkgs;
      in
      {
        # Development shell
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python311
            python311Packages.pip
            python311Packages.virtualenv
            poetry
            pyright
            black
            python311Packages.flake8
            self.packages.${system}.agent-network
          ];

          shellHook = ''
            echo "🤖 AG2 Agent Network Development Environment"
            echo "Python version: $(python --version)"
          '';
        };

        # Main package
        packages.agent-network = python.pkgs.buildPythonApplication {
          pname = "agent-network";
          version = "0.1.0";
          src = ./.;

          propagatedBuildInputs = with pythonPackages; [
            ag2
            openai
            chromadb
            pydantic
            pyyaml
            python-dotenv
          ];

          meta = with pkgs.lib; {
            description = "AG2 Parallel Agent Network for Software Development";
            license = licenses.mit;
          };
        };

        packages.default = self.packages.${system}.agent-network;
      }
    );
}
