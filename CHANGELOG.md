# Changelog

## [0.1.0] - 2025-11-05

### Added
- Initial release of AG2 Parallel Agent Network
- Parallel execution of three specialized teams (Architecture, Implementation, Documentation)
- Per-team RAG context isolation via HelixDB
- Factory pattern for clean agent instantiation
- Async/await support with ThreadPoolExecutor
- Refinement loop for output consolidation
- NixOS flake with systemd service module
- Comprehensive documentation and examples
- Docker and docker-compose support
- GitHub Actions CI/CD workflow

### Features
- Multiple team parallel execution
- Agent-specific RAG filtering
- HelixDB vector database integration
- Production-ready error handling
- Security hardening (NixOS service)
- CLI and programmatic APIs
- Comprehensive logging

### Security
- NixOS service includes filesystem isolation
- Memory and CPU limits
- Process-level privilege separation
- No network isolation for now (future enhancement)

### Known Limitations
- Requires valid LLM API key
- HelixDB requires initialization
- No built-in clustering (single-machine only)
