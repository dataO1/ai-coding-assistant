# backend/api/routes/workflow_routes.py - Workflow Endpoints

from fastapi import APIRouter, Request, WebSocket, HTTPException, status
from fastapi.responses import StreamingResponse
import json
import uuid
from datetime import datetime
import structlog

from backend.models import WorkflowSubmitRequest, WorkflowSubmitResponse
from backend.services.workflow_executor import WorkflowExecutor
from backend.config.settings import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

# Store active connections for streaming
active_connections: dict = {}


@router.post("/workflow/submit")
async def submit_workflow(request: Request, payload: WorkflowSubmitRequest) -> WorkflowSubmitResponse:
    """
    Submit a workflow request
    
    Receives complete workflow config from GUI, queues execution, returns execution_id
    """
    
    # Generate execution ID
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        "workflow_submitted",
        execution_id=execution_id,
        workflow_id=payload.workflow_id,
        workflow_type=payload.workflow_type,
        correlation_id=payload.correlation_id,
        workspace_id=payload.workspace_context.workspace_id,
    )
    
    try:
        # Validate request
        if not payload.user_query:
            raise ValueError("user_query is required")
        
        if not payload.workflow_config or "stages" not in payload.workflow_config:
            raise ValueError("workflow_config missing 'stages'")
        
        # TODO: Queue workflow for execution
        # In Phase 1, we'll use a simple queue; later use Redis/RabbitMQ
        
        # Return response with streaming URL
        streaming_url = f"ws://localhost:{settings.BACKEND_PORT}/api/workflow/{execution_id}/stream"
        
        return WorkflowSubmitResponse(
            execution_id=execution_id,
            workflow_id=payload.workflow_id,
            status="accepted",
            message="Workflow queued for execution",
            streaming_url=streaming_url,
        )
    
    except ValueError as e:
        logger.error(
            "workflow_validation_error",
            error=str(e),
            correlation_id=payload.correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "workflow_submission_error",
            error=str(e),
            exc_info=True,
            correlation_id=payload.correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/workflow/{execution_id}/status")
async def get_workflow_status(request: Request, execution_id: str):
    """Get current workflow status"""
    
    logger.info("workflow_status_requested", execution_id=execution_id)
    
    # TODO: Query workflow status from queue/store
    
    return {
        "execution_id": execution_id,
        "status": "running",
        "current_stage": "code_generation",
        "progress_percent": 45,
    }


@router.websocket("/api/workflow/{execution_id}/stream")
async def stream_workflow_updates(websocket: WebSocket, execution_id: str):
    """
    WebSocket endpoint for real-time workflow updates
    
    Streams status_update, workflow_complete, and error messages
    """
    
    await websocket.accept()
    
    logger.info("stream_connected", execution_id=execution_id)
    
    active_connections[execution_id] = websocket
    
    try:
        # TODO: Stream workflow updates
        # This will be called by WorkflowExecutor as it progresses
        
        # Keep connection open
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            
    except Exception as e:
        logger.error("stream_error", execution_id=execution_id, error=str(e))
    
    finally:
        active_connections.pop(execution_id, None)
        logger.info("stream_disconnected", execution_id=execution_id)


@router.get("/workflow/{execution_id}/commit/{commit_id}/diff")
async def get_commit_diff(request: Request, execution_id: str, commit_id: str):
    """
    Lazy-load: Get unified diff for specific commit
    
    Called when user clicks "Show code" in GUI
    """
    
    logger.info(
        "diff_requested",
        execution_id=execution_id,
        commit_id=commit_id,
    )
    
    # TODO: Retrieve diff from git repo
    
    return {
        "commit_id": commit_id,
        "file_path": "src/example.py",
        "change_type": "created",
        "additions": 42,
        "deletions": 0,
        "diff": "unified diff content here...",
    }


async def broadcast_to_stream(execution_id: str, message: dict):
    """
    Broadcast message to connected WebSocket client
    
    Called by WorkflowExecutor to send status updates
    """
    
    if execution_id in active_connections:
        try:
            websocket = active_connections[execution_id]
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(
                "broadcast_failed",
                execution_id=execution_id,
                error=str(e),
            )
