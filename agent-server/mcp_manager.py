import subprocess
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    name: str
    command: str
    args: List[str]
    process: Optional[subprocess.Popen] = None

    def start(self):
        """Start MCP server process"""
        full_cmd = [self.command] + self.args
        logger.info(f"Starting MCP server: {self.name} -> {' '.join(full_cmd)}")

        self.process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info(f"Started MCP server: {self.name} (PID: {self.process.pid})")

    def stop(self):
        """Stop MCP server process"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info(f"Stopped MCP server: {self.name}")

class MCPManager:
    def __init__(self, servers_config: Dict[str, Dict]):
        self.servers: Dict[str, MCPServer] = {}
        self._load_servers(servers_config)

    def _load_servers(self, servers_config: Dict[str, Dict]):
        """Load MCP server configs"""
        for name, config in servers_config.items():
            if config.get("enabled", True):
                server = MCPServer(
                    name=name,
                    command=config["command"],
                    args=config.get("args", []),
                )
                self.servers[name] = server

    def start_all(self):
        """Start all MCP servers"""
        for server in self.servers.values():
            server.start()

    def stop_all(self):
        """Stop all MCP servers"""
        for server in self.servers.values():
            server.stop()

    def get_server(self, name: str) -> Optional[MCPServer]:
        return self.servers.get(name)
