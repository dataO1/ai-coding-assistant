# backend/models.py - Pydantic Data Models

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class ChangeType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class WorkflowStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class StreamUpdateType(str, Enum):
    STATUS_UPDATE = "status_update"
    COMMIT_CREATED = "commit_created"
    WORKFLOW_COMPLETE = "workflow_complete"
    ERROR = "error"


# ============================================================================
# Request Models
# ============================================================================

class WorkspaceContext(BaseModel):
    """Workspace context provided by GUI"""
    workspace_id: str
    working_dir: str
    language: str
    framework: str


class WorkflowSubmitRequest(BaseModel):
    """Complete workflow submission request from GUI"""
    workflow_id: str
    workflow_type: str
    user_query: str
    
    # Complete configs from GUI
    workflow_config: Dict[str, Any]
    agents_config: Dict[str, Any]
    retrieval_config: Dict[str, Any]
    mcp_config: Dict[str, Any]
    
    workspace_context: WorkspaceContext
    correlation_id: str


# ============================================================================
# Response Models
# ============================================================================

class WorkflowSubmitResponse(BaseModel):
    """Response to workflow submission"""
    execution_id: str
    workflow_id: str
    status: str
    message: str
    streaming_url: str


class StatusMetrics(BaseModel):
    """Metrics sent with status updates"""
    tokens_generated: Optional[int] = None
    inference_speed_tokens_per_sec: Optional[float] = None
    elapsed_seconds: Optional[int] = None
    estimated_remaining_seconds: Optional[int] = None


class StatusUpdate(BaseModel):
    """Status update stream message"""
    type: str = StreamUpdateType.STATUS_UPDATE
    correlation_id: str
    workflow_id: str
    stage_id: str
    timestamp: str
    status: str
    progress_percent: int
    metrics: Optional[StatusMetrics] = None


class HunkMetadata(BaseModel):
    """Metadata for a hunk (changed section)"""
    hunk_id: str
    lines_start: int
    lines_end: int
    summary: str


class FileChange(BaseModel):
    """File change metadata"""
    file_path: str
    change_type: ChangeType
    additions: int
    deletions: int
    hunks: List[HunkMetadata]


class CommitMetadata(BaseModel):
    """Commit metadata (NO CODE CONTENT)"""
    commit_id: str
    agent: str
    message: str
    files_changed: int
    additions: int
    deletions: int
    files: List[FileChange]
    timestamp: Optional[str] = None


class TotalChanges(BaseModel):
    """Aggregated change statistics"""
    files: int
    additions: int
    deletions: int


class WorkflowCompleteUpdate(BaseModel):
    """Workflow complete stream message"""
    type: str = StreamUpdateType.WORKFLOW_COMPLETE
    correlation_id: str
    workflow_id: str
    status: str
    timestamp: str
    commits: List[CommitMetadata]
    total_changes: TotalChanges


class ErrorUpdate(BaseModel):
    """Error stream message"""
    type: str = StreamUpdateType.ERROR
    correlation_id: str
    error_code: str
    message: str
    details: Optional[str] = None


# ============================================================================
# Internal State Models
# ============================================================================

@dataclass
class WorkflowState:
    """
    LangGraph workflow state
    
    Represents complete execution state for orchestration
    """
    # Input
    user_query: str
    workflow_id: str
    workflow_config: Dict[str, Any]
    agents_config: Dict[str, Any]
    retrieval_config: Dict[str, Any]
    workspace_context: WorkspaceContext
    
    # Execution tracking
    execution_id: str
    correlation_id: str
    current_stage: str
    stage_results: Dict[str, Any] = field(default_factory=dict)
    
    # Retrieval & context
    retrieved_context: Optional[str] = None
    retrieval_needs: List[str] = field(default_factory=list)
    enrichment_context: Dict[str, Any] = field(default_factory=dict)
    
    # Git operations
    workflow_branch: str = ""
    commits: List[Dict[str, Any]] = field(default_factory=list)
    
    # Error tracking
    failures: Dict[str, Any] = field(default_factory=dict)
    attempt_count: Dict[str, int] = field(default_factory=dict)
    
    # Output
    is_success: bool = False
    final_message: str = ""


class DiffContent(BaseModel):
    """Unified diff content (lazy-loaded by GUI)"""
    commit_id: str
    file_path: str
    change_type: ChangeType
    additions: int
    deletions: int
    diff: str  # Unified diff format
    hunks: List[Dict[str, Any]] = []


# ============================================================================
# Configuration Models
# ============================================================================

class AgentRetrievalNeeds(BaseModel):
    """Per-stage retrieval needs"""
    file_level_semantic: bool = True
    function_ast_selective: bool = True
    lsp_integration: bool = False
    test_examples_only: bool = False


class DebugVRAMInfo(BaseModel):
    """GPU VRAM information for debugging"""
    used_mb: int
    available_mb: int
    total_mb: int
    percentage: float
    peak_mb: int
    components: Dict[str, int] = {}
