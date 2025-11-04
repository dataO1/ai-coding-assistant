# backend/services/qdrant_manager.py - Qdrant Vector Database Manager

from typing import List, Dict, Optional, Any
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = structlog.get_logger(__name__)


class QdrantManager:
    """
    Manages Qdrant vector database connections and operations
    
    Handles:
    - Connection management
    - Collection initialization
    - Two-phase retrieval (file-level + function-level)
    - Workspace scoping (workspace_id filtering)
    """
    
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key
        self.client: Optional[QdrantClient] = None
    
    async def connect(self) -> None:
        """Connect to Qdrant server"""
        try:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
            )
            
            # Verify connection
            info = self.client.get_collections()
            logger.info("qdrant_connected", collections=len(info.collections))
            
        except Exception as e:
            logger.error("qdrant_connection_failed", error=str(e), exc_info=True)
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Qdrant"""
        if self.client:
            self.client.close()
            logger.info("qdrant_disconnected")
    
    async def initialize_collections(self) -> None:
        """Initialize required collections"""
        if not self.client:
            raise RuntimeError("Not connected to Qdrant")
        
        # TODO: Create workspace_files and workspace_functions collections
        # with appropriate vector params and payload schemas
        
        logger.info("qdrant_collections_initialized")
    
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        query_filter: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search in Qdrant collection
        
        Args:
            collection_name: Name of collection to search
            query_vector: Query embedding vector
            query_filter: Qdrant filter (e.g., workspace_id scoping)
            limit: Max results to return
        
        Returns:
            List of search results
        """
        if not self.client:
            raise RuntimeError("Not connected to Qdrant")
        
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
            
            logger.info(
                "qdrant_search_completed",
                collection=collection_name,
                results=len(results),
            )
            
            return [
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload,
                }
                for r in results
            ]
        
        except Exception as e:
            logger.error(
                "qdrant_search_failed",
                collection=collection_name,
                error=str(e),
                exc_info=True,
            )
            raise
    
    async def upsert_points(
        self,
        collection_name: str,
        points: List[PointStruct],
    ) -> None:
        """Upsert points into collection"""
        if not self.client:
            raise RuntimeError("Not connected to Qdrant")
        
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(
                "qdrant_upsert_completed",
                collection=collection_name,
                count=len(points),
            )
        except Exception as e:
            logger.error("qdrant_upsert_failed", error=str(e), exc_info=True)
            raise
