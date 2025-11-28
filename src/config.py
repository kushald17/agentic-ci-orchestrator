"""Configuration loader for the application."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file in project root
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    # Fallback: try loading from current directory
    load_dotenv()


class Config:
    """Application configuration manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml (defaults to ./config.yaml)
        """
        if config_path is None:
            config_path = os.path.join(os.getcwd(), "config.yaml")
        
        if not os.path.exists(config_path):
            # Try config.example.yaml
            example_path = config_path.replace("config.yaml", "config.example.yaml")
            if os.path.exists(example_path):
                config_path = example_path
            else:
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r") as f:
            self._config = yaml.safe_load(f)
        
        # Substitute environment variables
        self._config = self._substitute_env_vars(self._config)
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute ${ENV_VAR} patterns with environment variables."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Replace ${VAR_NAME} with environment variable
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.getenv(var_name, obj)
            return obj
        return obj
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key.
        
        Args:
            key: Dot-separated key (e.g., "ollama.base_url")
            default: Default value if key not found
        
        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_all(self) -> Dict[str, Any]:
        """Get complete configuration dictionary."""
        return self._config
    
    # Convenience properties
    
    @property
    def ollama_base_url(self) -> str:
        return self.get("ollama.base_url", "http://localhost:11434")
    
    @property
    def ollama_timeout(self) -> int:
        return self.get("ollama.timeout", 300)
    
    @property
    def ollama_reasoning_model(self) -> str:
        return self.get("ollama.models.reasoning", "llama3:70b")
    
    @property
    def ollama_lightweight_model(self) -> str:
        return self.get("ollama.models.lightweight", "llama3:13b")
    
    @property
    def github_token(self) -> str:
        token = self.get("github.token", "")
        if not token:
            raise ValueError("GitHub token not configured. Set GITHUB_TOKEN environment variable.")
        return token
    
    @property
    def github_api_url(self) -> str:
        return self.get("github.api_url", "https://api.github.com")
    
    @property
    def github_branch_prefix(self) -> str:
        return self.get("github.branch_prefix", "agent/ci-")
    
    @property
    def max_healing_attempts(self) -> int:
        return self.get("safety.rate_limits.max_healing_attempts_per_run", 3)
    
    @property
    def confidence_auto_commit_threshold(self) -> float:
        return self.get("safety.confidence.auto_commit_threshold", 0.9)
    
    @property
    def confidence_pr_threshold(self) -> float:
        return self.get("safety.confidence.pr_creation_threshold", 0.7)
    
    @property
    def development_mode(self) -> bool:
        return self.get("development.debug", False)
    
    @property
    def dry_run(self) -> bool:
        return self.get("development.dry_run", False)


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config
