# ai_agent_runtime/context.py
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List


class ContextSource(str, Enum):
    """Source of the agent request."""
    SHELL = "shell"
    NVIM = "nvim"
    VSCODE = "vscode"
    WEB = "web"


class AgentContext(BaseModel):
    """Context passed to agents with source and working directory."""
    source: ContextSource
    working_dir: str = Field(default_factory=lambda: str(Path.home()))

    @property
    def allowed_roots(self) -> List[str]:
        """Get allowed directory roots based on context source."""
        working_path = Path(self.working_dir).resolve()

        # Validate working_dir is absolute and exists
        if not working_path.is_dir():
            working_path = Path.home()

        if self.source == ContextSource.SHELL:
            # Shell context: allow working dir + home + tmp
            return [
                str(working_path),
            ]
        elif self.source == ContextSource.NVIM:
            # Nvim: only working directory (buffer context)
            return [str(working_path)]
        elif self.source == ContextSource.VSCODE:
            # VS Code: working dir + workspace
            return [str(working_path)]
        elif self.source == ContextSource.WEB:
            # Web: restricted to specific path only
            return [str(working_path)]
        else:
            return [str(Path.home())]

    def is_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed in this context."""
        target_path = Path(path).resolve()
        for root in self.allowed_roots:
            try:
                target_path.relative_to(root)
                return True
            except ValueError:
                continue
        return False
