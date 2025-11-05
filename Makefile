# AG2 Agent Network Makefile

.PHONY: help install dev test format lint clean run nixbuild

help:
	@echo "AG2 Agent Network - Available Commands"
	@echo "======================================"
	@echo "  make install     - Install dependencies with pip"
	@echo "  make dev         - Setup development environment"
	@echo "  make test        - Run tests with pytest"
	@echo "  make format      - Format code with black"
	@echo "  make lint        - Check code with flake8"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make run         - Run agent network CLI"
	@echo "  make nixbuild    - Build with Nix"
	@echo "  make nixdev      - Enter Nix dev shell"

install:
	pip install -r requirements.txt

dev:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short

format:
	black *.py tests/

lint:
	flake8 *.py tests/ --max-line-length=100

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache *.egg-info dist build
	rm -rf venv/
	find . -type d -name __pycache__ -exec rm -rf {} +

run:
	python main.py "Build a REST API"

nixbuild:
	nix build .#agent-network

nixdev:
	nix flake develop

nixshell:
	nix develop

# Quick dev workflow
quick: format lint test
	@echo "✅ All checks passed!"
