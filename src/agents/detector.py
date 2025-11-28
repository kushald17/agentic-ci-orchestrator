"""
Repository Detector Agent.

Inspects repository structure to determine language, build tools, and configuration.
"""

import re
from typing import Dict, Optional
import structlog

from src.models.state import AgentState, RepositoryMetadata
from src.integrations.github_client import GitHubClient

logger = structlog.get_logger()


class RepositoryDetectorAgent:
    """Detects repository language and configuration using heuristics."""
    
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
    
    def detect(self, state: AgentState) -> AgentState:
        """
        Detect repository metadata.
        
        Args:
            state: Current agent state
        
        Returns:
            Updated state with repo_metadata populated
        """
        logger.info(
            "detecting_repository",
            repo=f"{state.repo_owner}/{state.repo_name}",
            branch=state.repo_branch,
        )
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            
            # Get root files
            files = self.github_client.list_files(repo, "", state.repo_branch)
            
            # Detect language and tools
            metadata = RepositoryMetadata(
                owner=state.repo_owner,
                name=state.repo_name,
                branch=state.repo_branch,
                full_name=f"{state.repo_owner}/{state.repo_name}",
                language="generic",
            )
            
            # Python detection
            if self._has_python_indicators(files):
                metadata.language = "python"
                metadata.language_version = self._detect_python_version(repo, files, state.repo_branch)
                metadata.package_manager = self._detect_python_package_manager(files)
                metadata.dependencies_file = self._find_python_dependencies(files)
                metadata.has_tests = self._has_python_tests(files)
                metadata.test_framework = self._detect_python_test_framework(repo, files, state.repo_branch)
                metadata.has_linter = self._has_python_linter(repo, files, state.repo_branch)
                metadata.build_tool = metadata.package_manager
            
            # Node.js detection
            elif self._has_node_indicators(files):
                metadata.language = "node"
                metadata.package_manager = self._detect_node_package_manager(files)
                metadata.dependencies_file = "package.json"
                package_json = self._get_package_json(repo, state.repo_branch)
                if package_json:
                    metadata.has_tests = "test" in package_json.get("scripts", {})
                    metadata.has_linter = "lint" in package_json.get("scripts", {})
                    metadata.custom_commands = package_json.get("scripts", {})
                metadata.build_tool = "npm"
            
            # Java detection
            elif self._has_java_indicators(files):
                metadata.language = "java"
                if "pom.xml" in files:
                    metadata.build_tool = "maven"
                    metadata.dependencies_file = "pom.xml"
                elif any("build.gradle" in f for f in files):
                    metadata.build_tool = "gradle"
                    metadata.dependencies_file = "build.gradle"
                metadata.has_tests = self._has_java_tests(files)
            
            # Go detection
            elif "go.mod" in files:
                metadata.language = "go"
                metadata.package_manager = "go"
                metadata.dependencies_file = "go.mod"
                metadata.has_tests = any("_test.go" in f for f in files)
            
            # Rust detection
            elif "Cargo.toml" in files:
                metadata.language = "rust"
                metadata.package_manager = "cargo"
                metadata.dependencies_file = "Cargo.toml"
                metadata.has_tests = True  # Rust projects typically have tests
            
            # Ruby detection
            elif "Gemfile" in files:
                metadata.language = "ruby"
                metadata.package_manager = "bundler"
                metadata.dependencies_file = "Gemfile"
            
            state.repo_metadata = metadata
            state.next_action = "generate"
            
            logger.info(
                "repository_detected",
                language=metadata.language,
                package_manager=metadata.package_manager,
                has_tests=metadata.has_tests,
                has_linter=metadata.has_linter,
            )
            
            return state
            
        except Exception as e:
            error_msg = f"Repository detection failed: {str(e)}"
            logger.error("detection_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    # Python detection methods
    
    def _has_python_indicators(self, files: list) -> bool:
        """Check if repository has Python indicators."""
        python_indicators = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile",
            "poetry.lock",
        ]
        return any(indicator in files for indicator in python_indicators) or \
               any(f.endswith(".py") for f in files)
    
    def _detect_python_version(
        self,
        repo,
        files: list,
        branch: str
    ) -> Optional[str]:
        """Detect Python version from various sources."""
        # Check pyproject.toml
        if "pyproject.toml" in files:
            content = self.github_client.get_file_content(repo, "pyproject.toml", branch)
            if content:
                # Look for python version requirement
                match = re.search(r'python\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    version = match.group(1)
                    # Extract major.minor (e.g., ^3.11 -> 3.11)
                    version_match = re.search(r'(\d+\.\d+)', version)
                    if version_match:
                        return version_match.group(1)
        
        # Check .python-version
        if ".python-version" in files:
            content = self.github_client.get_file_content(repo, ".python-version", branch)
            if content:
                return content.strip()
        
        # Default to 3.11
        return "3.11"
    
    def _detect_python_package_manager(self, files: list) -> str:
        """Detect Python package manager."""
        if "poetry.lock" in files or "pyproject.toml" in files:
            return "poetry"
        elif "Pipfile" in files:
            return "pipenv"
        elif "requirements.txt" in files:
            return "pip"
        return "pip"
    
    def _find_python_dependencies(self, files: list) -> Optional[str]:
        """Find Python dependencies file."""
        if "requirements.txt" in files:
            return "requirements.txt"
        elif "pyproject.toml" in files:
            return "pyproject.toml"
        elif "Pipfile" in files:
            return "Pipfile"
        return None
    
    def _has_python_tests(self, files: list) -> bool:
        """Check if repository has Python tests."""
        test_indicators = ["tests/", "test/", "test_", "_test.py"]
        return any(
            any(indicator in f for indicator in test_indicators)
            for f in files
        )
    
    def _detect_python_test_framework(
        self,
        repo,
        files: list,
        branch: str
    ) -> Optional[str]:
        """Detect Python test framework."""
        # Check pyproject.toml for pytest
        if "pyproject.toml" in files:
            content = self.github_client.get_file_content(repo, "pyproject.toml", branch)
            if content and "pytest" in content:
                return "pytest"
        
        # Check requirements files
        for req_file in ["requirements.txt", "requirements-dev.txt", "dev-requirements.txt"]:
            if req_file in files:
                content = self.github_client.get_file_content(repo, req_file, branch)
                if content:
                    if "pytest" in content:
                        return "pytest"
                    elif "unittest" in content:
                        return "unittest"
        
        return "pytest"  # Default
    
    def _has_python_linter(
        self,
        repo,
        files: list,
        branch: str
    ) -> bool:
        """Check if repository has Python linter configuration."""
        linter_files = [
            ".ruff.toml",
            "ruff.toml",
            ".flake8",
            "pylintrc",
            ".pylintrc",
        ]
        if any(f in files for f in linter_files):
            return True
        
        # Check pyproject.toml for linter config
        if "pyproject.toml" in files:
            content = self.github_client.get_file_content(repo, "pyproject.toml", branch)
            if content and any(linter in content for linter in ["ruff", "flake8", "pylint", "black"]):
                return True
        
        return False
    
    # Node.js detection methods
    
    def _has_node_indicators(self, files: list) -> bool:
        """Check if repository has Node.js indicators."""
        return "package.json" in files
    
    def _detect_node_package_manager(self, files: list) -> str:
        """Detect Node.js package manager."""
        if "pnpm-lock.yaml" in files:
            return "pnpm"
        elif "yarn.lock" in files:
            return "yarn"
        elif "package-lock.json" in files:
            return "npm"
        return "npm"
    
    def _get_package_json(self, repo, branch: str) -> Optional[Dict]:
        """Parse package.json."""
        import json
        content = self.github_client.get_file_content(repo, "package.json", branch)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return None
        return None
    
    # Java detection methods
    
    def _has_java_indicators(self, files: list) -> bool:
        """Check if repository has Java indicators."""
        java_indicators = ["pom.xml", "build.gradle", "build.gradle.kts"]
        return any(indicator in files for indicator in java_indicators) or \
               any(f.endswith(".java") for f in files)
    
    def _has_java_tests(self, files: list) -> bool:
        """Check if repository has Java tests."""
        return any("test" in f.lower() for f in files if f.endswith(".java"))
