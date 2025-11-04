# backend/services/ollama_manager.py - Ollama LLM Manager

from typing import Optional, Dict, Any, AsyncGenerator
import structlog
import httpx
import asyncio

logger = structlog.get_logger(__name__)


class OllamaManager:
    """
    Manages Ollama LLM connections and inference
    
    Handles:
    - Connection verification
    - Model loading
    - Inference calls
    - Token streaming
    - VRAM monitoring
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=300.0)
    
    async def verify_connection(self) -> None:
        """Verify Ollama server is running"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                response.raise_for_status()
                logger.info("ollama_connected", url=self.base_url)
        except Exception as e:
            logger.error("ollama_connection_failed", url=self.base_url, error=str(e))
            raise
    
    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        num_predict: int = 2000,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | str:
        """
        Generate text using Ollama
        
        Args:
            model: Model name (e.g., "mistral:7b-instruct-v0.3")
            prompt: Input prompt
            temperature: Sampling temperature (0.0-1.0)
            num_predict: Max tokens to generate
            stream: Whether to stream response
        
        Returns:
            Generated text or async generator if streaming
        """
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "num_predict": num_predict,
                "stream": stream,
            }
            
            if stream:
                return self._stream_generate(payload)
            else:
                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        
        except Exception as e:
            logger.error(
                "ollama_generation_failed",
                model=model,
                error=str(e),
                exc_info=True,
            )
            raise
    
    async def _stream_generate(self, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream text generation"""
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        yield data.get("response", "")
        
        except Exception as e:
            logger.error("ollama_streaming_failed", error=str(e), exc_info=True)
            raise
    
    async def get_vram_info(self) -> Dict[str, Any]:
        """Get GPU VRAM usage (debug endpoint)"""
        # TODO: Query Ollama for VRAM info
        return {
            "used_mb": 4200,
            "available_mb": 11800,
            "total_mb": 16000,
            "percentage": 26.3,
        }
    
    async def close(self) -> None:
        """Close HTTP client"""
        await self.client.aclose()
