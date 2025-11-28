"""Integrations package for external services."""

from src.integrations.ollama_client import OllamaClient, get_ollama_client
from src.integrations.github_client import GitHubClient, get_github_client

__all__ = [
    "OllamaClient",
    "get_ollama_client",
    "GitHubClient",
    "get_github_client",
]
