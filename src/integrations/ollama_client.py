"""
Ollama client wrapper with health checks, retry logic, and structured responses.
"""

import json
import time
from typing import Any, Dict, List, Literal, Optional, Union
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog

logger = structlog.get_logger()


@dataclass
class OllamaResponse:
    """Structured response from Ollama."""
    content: str
    model: str
    created_at: str
    done: bool
    total_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    
    @property
    def parsed_json(self) -> Optional[Dict[str, Any]]:
        """Parse content as JSON if possible."""
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return None


class OllamaClient:
    """Client for interacting with Ollama local models."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,  # Reduced from 300 to 120 seconds
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.Client(timeout=timeout)
        self._health_checked = False
    
    def health_check(self) -> bool:
        """
        Check if Ollama is running and accessible.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                self._health_checked = True
                logger.info("ollama_health_check_passed")
                return True
            else:
                logger.error("ollama_health_check_failed", status_code=response.status_code)
                return False
        except Exception as e:
            logger.error("ollama_health_check_exception", error=str(e))
            return False
    
    def list_models(self) -> List[str]:
        """Get list of available models."""
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.error("failed_to_list_models", error=str(e))
            return []
    
    def ensure_model_available(self, model: str) -> bool:
        """Check if a model is available, pull if not."""
        models = self.list_models()
        if model in models:
            return True
        
        logger.info("pulling_model", model=model)
        try:
            # Pull model (streaming)
            with self.client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model},
                timeout=3600,  # Longer timeout for pulling
            ) as response:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("status") == "success":
                            logger.info("model_pulled_successfully", model=model)
                            return True
            return False
        except Exception as e:
            logger.error("failed_to_pull_model", model=model, error=str(e))
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
    )
    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        format: Optional[Literal["json"]] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,  # Allow per-request timeout override
    ) -> OllamaResponse:
        """
        Generate completion using Ollama.
        
        Args:
            model: Model name (e.g., "llama3:70b")
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature (0.0-1.0)
            format: Response format ("json" for structured output)
            stream: Whether to stream response
            options: Additional model options
        
        Returns:
            OllamaResponse: Structured response
        
        Raises:
            httpx.RequestError: If request fails after retries
            ValueError: If response is invalid
        """
        if not self._health_checked and not self.health_check():
            raise ConnectionError("Ollama is not available")
        
        # Ensure model is available
        if not self.ensure_model_available(model):
            raise ValueError(f"Model {model} is not available and could not be pulled")
        
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                **(options or {}),
            },
        }
        
        if system:
            payload["system"] = system
        
        if format:
            payload["format"] = format
        
        start_time = time.time()
        
        # Use custom timeout if provided, otherwise use instance timeout
        request_timeout = timeout if timeout is not None else self.timeout
        
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=request_timeout,  # Use the timeout value
            )
            response.raise_for_status()
            
            data = response.json()
            duration = time.time() - start_time
            
            logger.info(
                "ollama_generate_success",
                model=model,
                duration=duration,
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            )
            
            return OllamaResponse(
                content=data["response"],
                model=data["model"],
                created_at=data["created_at"],
                done=data["done"],
                total_duration=data.get("total_duration"),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "ollama_http_error",
                status_code=e.response.status_code,
                detail=e.response.text,
            )
            raise
        except Exception as e:
            logger.error("ollama_generate_failed", error=str(e))
            raise
    
    def generate_structured(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.
        
        Args:
            model: Model name
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature
            expected_schema: Optional JSON schema for validation
        
        Returns:
            Dict: Parsed JSON response
        
        Raises:
            ValueError: If response is not valid JSON
        """
        # Add JSON format instruction to prompt
        json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        
        response = self.generate(
            model=model,
            prompt=json_prompt,
            system=system,
            temperature=temperature,
            format="json",
        )
        
        parsed = response.parsed_json
        if parsed is None:
            # Try to extract JSON from markdown code blocks
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            try:
                parsed = json.loads(content.strip())
            except json.JSONDecodeError as e:
                logger.error("failed_to_parse_json", content=content[:500], error=str(e))
                raise ValueError(f"Invalid JSON response: {str(e)}")
        
        return parsed
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client(
    base_url: str = "http://localhost:11434",
    timeout: int = 300,
) -> OllamaClient:
    """Get or create singleton Ollama client."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url=base_url, timeout=timeout)
    return _ollama_client
