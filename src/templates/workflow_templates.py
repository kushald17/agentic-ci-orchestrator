"""
Workflow templates for different languages.

Provides a composable template system with inheritance.
"""

from typing import Dict, List, Optional
from abc import ABC, abstractmethod


class WorkflowTemplate(ABC):
    """Base class for workflow templates."""
    
    def __init__(self, language: str):
        self.language = language
    
    @abstractmethod
    def get_setup_steps(self) -> List[Dict[str, str]]:
        """Get setup/installation steps."""
        pass
    
    @abstractmethod
    def get_lint_step(self) -> Optional[Dict[str, str]]:
        """Get linting step."""
        pass
    
    @abstractmethod
    def get_test_step(self) -> Optional[Dict[str, str]]:
        """Get testing step."""
        pass
    
    @abstractmethod
    def get_build_step(self) -> Optional[Dict[str, str]]:
        """Get build step."""
        pass
    
    def get_cache_config(self) -> Optional[Dict[str, str]]:
        """Get caching configuration."""
        return None
    
    def get_matrix_config(self) -> Optional[Dict[str, List[str]]]:
        """Get matrix build configuration."""
        return None
    
    def generate(
        self,
        repo_name: str,
        branch: str = "main",
        include_lint: bool = True,
        include_test: bool = True,
        include_build: bool = True,
    ) -> str:
        """
        Generate complete workflow YAML.
        
        Args:
            repo_name: Repository name for context
            branch: Default branch
            include_lint: Include linting step
            include_test: Include testing step
            include_build: Include building step
        
        Returns:
            Complete workflow YAML as string
        """
        workflow = {
            "name": f"CI - {repo_name}",
            "on": {
                "push": {"branches": [branch]},
                "pull_request": {"branches": [branch]},
            },
            "jobs": {
                "ci": {
                    "runs-on": "ubuntu-latest",
                    "steps": [],
                }
            }
        }
        
        # Add checkout step
        workflow["jobs"]["ci"]["steps"].append({
            "name": "Checkout code",
            "uses": "actions/checkout@v4",
        })
        
        # Add matrix if available
        matrix = self.get_matrix_config()
        if matrix:
            workflow["jobs"]["ci"]["strategy"] = {"matrix": matrix}
        
        # Add setup steps
        for step in self.get_setup_steps():
            workflow["jobs"]["ci"]["steps"].append(step)
        
        # Add cache if available
        cache = self.get_cache_config()
        if cache:
            workflow["jobs"]["ci"]["steps"].append(cache)
        
        # Add lint step
        if include_lint:
            lint_step = self.get_lint_step()
            if lint_step:
                workflow["jobs"]["ci"]["steps"].append(lint_step)
        
        # Add test step
        if include_test:
            test_step = self.get_test_step()
            if test_step:
                workflow["jobs"]["ci"]["steps"].append(test_step)
        
        # Add build step
        if include_build:
            build_step = self.get_build_step()
            if build_step:
                workflow["jobs"]["ci"]["steps"].append(build_step)
        
        # Convert to YAML string
        import yaml
        return yaml.dump(workflow, sort_keys=False, default_flow_style=False)


class PythonTemplate(WorkflowTemplate):
    """Python workflow template."""
    
    def __init__(
        self,
        python_version: str = "3.11",
        use_poetry: bool = False,
        use_pipenv: bool = False,
    ):
        super().__init__("python")
        self.python_version = python_version
        self.use_poetry = use_poetry
        self.use_pipenv = use_pipenv
    
    def get_setup_steps(self) -> List[Dict[str, str]]:
        steps = [
            {
                "name": "Set up Python",
                "uses": "actions/setup-python@v5",
                "with": {
                    "python-version": self.python_version,
                },
            }
        ]
        
        if self.use_poetry:
            steps.append({
                "name": "Install Poetry",
                "run": "pip install poetry",
            })
            steps.append({
                "name": "Install dependencies",
                "run": "poetry install",
            })
        elif self.use_pipenv:
            steps.append({
                "name": "Install Pipenv",
                "run": "pip install pipenv",
            })
            steps.append({
                "name": "Install dependencies",
                "run": "pipenv install --dev",
            })
        else:
            steps.append({
                "name": "Install dependencies",
                "run": "pip install -r requirements.txt || pip install -e .[dev] || echo 'No dependencies file found'",
            })
        
        return steps
    
    def get_cache_config(self) -> Optional[Dict[str, str]]:
        return {
            "name": "Cache pip packages",
            "uses": "actions/cache@v4",
            "with": {
                "path": "~/.cache/pip",
                "key": "${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}",
                "restore-keys": "${{ runner.os }}-pip-",
            },
        }
    
    def get_lint_step(self) -> Optional[Dict[str, str]]:
        if self.use_poetry:
            cmd = "poetry run ruff check . && poetry run black --check ."
        elif self.use_pipenv:
            cmd = "pipenv run ruff check . && pipenv run black --check ."
        else:
            cmd = "pip install ruff black && ruff check . && black --check ."
        
        return {
            "name": "Lint with ruff and black",
            "run": cmd,
        }
    
    def get_test_step(self) -> Optional[Dict[str, str]]:
        if self.use_poetry:
            cmd = "poetry run pytest --cov --cov-report=xml"
        elif self.use_pipenv:
            cmd = "pipenv run pytest --cov --cov-report=xml"
        else:
            cmd = "pip install pytest pytest-cov && pytest --cov --cov-report=xml"
        
        return {
            "name": "Run tests",
            "run": cmd,
        }
    
    def get_build_step(self) -> Optional[Dict[str, str]]:
        if self.use_poetry:
            return {
                "name": "Build package",
                "run": "poetry build",
            }
        else:
            return {
                "name": "Build package",
                "run": "pip install build && python -m build",
            }
    
    def get_matrix_config(self) -> Optional[Dict[str, List[str]]]:
        return {
            "python-version": ["3.9", "3.10", "3.11", "3.12"],
        }


class NodeTemplate(WorkflowTemplate):
    """Node.js workflow template."""
    
    def __init__(
        self,
        node_version: str = "20",
        use_yarn: bool = False,
        use_pnpm: bool = False,
    ):
        super().__init__("node")
        self.node_version = node_version
        self.use_yarn = use_yarn
        self.use_pnpm = use_pnpm
    
    def get_setup_steps(self) -> List[Dict[str, str]]:
        steps = [
            {
                "name": "Set up Node.js",
                "uses": "actions/setup-node@v4",
                "with": {
                    "node-version": self.node_version,
                },
            }
        ]
        
        if self.use_pnpm:
            steps.append({
                "name": "Install pnpm",
                "run": "npm install -g pnpm",
            })
            steps.append({
                "name": "Install dependencies",
                "run": "pnpm install",
            })
        elif self.use_yarn:
            steps.append({
                "name": "Install dependencies",
                "run": "yarn install",
            })
        else:
            steps.append({
                "name": "Install dependencies",
                "run": "npm ci",
            })
        
        return steps
    
    def get_cache_config(self) -> Optional[Dict[str, str]]:
        if self.use_pnpm:
            path = "~/.pnpm-store"
            key_file = "pnpm-lock.yaml"
        elif self.use_yarn:
            path = "~/.yarn/cache"
            key_file = "yarn.lock"
        else:
            path = "~/.npm"
            key_file = "package-lock.json"
        
        return {
            "name": "Cache dependencies",
            "uses": "actions/cache@v4",
            "with": {
                "path": path,
                "key": f"${{{{ runner.os }}}}-node-${{{{ hashFiles('**/{key_file}') }}}}",
                "restore-keys": "${{ runner.os }}-node-",
            },
        }
    
    def get_lint_step(self) -> Optional[Dict[str, str]]:
        if self.use_pnpm:
            cmd = "pnpm run lint"
        elif self.use_yarn:
            cmd = "yarn lint"
        else:
            cmd = "npm run lint"
        
        return {
            "name": "Lint code",
            "run": cmd,
        }
    
    def get_test_step(self) -> Optional[Dict[str, str]]:
        if self.use_pnpm:
            cmd = "pnpm test"
        elif self.use_yarn:
            cmd = "yarn test"
        else:
            cmd = "npm test"
        
        return {
            "name": "Run tests",
            "run": cmd,
        }
    
    def get_build_step(self) -> Optional[Dict[str, str]]:
        if self.use_pnpm:
            cmd = "pnpm run build"
        elif self.use_yarn:
            cmd = "yarn build"
        else:
            cmd = "npm run build"
        
        return {
            "name": "Build project",
            "run": cmd,
        }
    
    def get_matrix_config(self) -> Optional[Dict[str, List[str]]]:
        return {
            "node-version": ["18", "20", "21"],
        }


class JavaTemplate(WorkflowTemplate):
    """Java workflow template."""
    
    def __init__(
        self,
        java_version: str = "17",
        use_gradle: bool = False,
    ):
        super().__init__("java")
        self.java_version = java_version
        self.use_gradle = use_gradle
    
    def get_setup_steps(self) -> List[Dict[str, str]]:
        return [
            {
                "name": "Set up JDK",
                "uses": "actions/setup-java@v4",
                "with": {
                    "java-version": self.java_version,
                    "distribution": "temurin",
                },
            }
        ]
    
    def get_cache_config(self) -> Optional[Dict[str, str]]:
        if self.use_gradle:
            return {
                "name": "Cache Gradle packages",
                "uses": "actions/cache@v4",
                "with": {
                    "path": "~/.gradle/caches",
                    "key": "${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') }}",
                    "restore-keys": "${{ runner.os }}-gradle-",
                },
            }
        else:
            return {
                "name": "Cache Maven packages",
                "uses": "actions/cache@v4",
                "with": {
                    "path": "~/.m2",
                    "key": "${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}",
                    "restore-keys": "${{ runner.os }}-m2-",
                },
            }
    
    def get_lint_step(self) -> Optional[Dict[str, str]]:
        if self.use_gradle:
            return {
                "name": "Lint with Checkstyle",
                "run": "./gradlew checkstyleMain",
            }
        else:
            return {
                "name": "Lint with Checkstyle",
                "run": "mvn checkstyle:check",
            }
    
    def get_test_step(self) -> Optional[Dict[str, str]]:
        if self.use_gradle:
            return {
                "name": "Run tests",
                "run": "./gradlew test",
            }
        else:
            return {
                "name": "Run tests",
                "run": "mvn test",
            }
    
    def get_build_step(self) -> Optional[Dict[str, str]]:
        if self.use_gradle:
            return {
                "name": "Build with Gradle",
                "run": "./gradlew build",
            }
        else:
            return {
                "name": "Build with Maven",
                "run": "mvn package",
            }
    
    def get_matrix_config(self) -> Optional[Dict[str, List[str]]]:
        return {
            "java-version": ["11", "17", "21"],
        }


class GenericTemplate(WorkflowTemplate):
    """Generic/fallback workflow template."""
    
    def __init__(self):
        super().__init__("generic")
    
    def get_setup_steps(self) -> List[Dict[str, str]]:
        return []
    
    def get_lint_step(self) -> Optional[Dict[str, str]]:
        return {
            "name": "Lint (placeholder)",
            "run": "echo 'Add your linting command here'",
        }
    
    def get_test_step(self) -> Optional[Dict[str, str]]:
        return {
            "name": "Test (placeholder)",
            "run": "echo 'Add your test command here'",
        }
    
    def get_build_step(self) -> Optional[Dict[str, str]]:
        return {
            "name": "Build (placeholder)",
            "run": "echo 'Add your build command here'",
        }


def get_template(
    language: str,
    **kwargs
) -> WorkflowTemplate:
    """
    Factory function to get appropriate template.
    
    Args:
        language: Language name
        **kwargs: Additional template-specific parameters
    
    Returns:
        WorkflowTemplate instance
    """
    templates = {
        "python": PythonTemplate,
        "node": NodeTemplate,
        "javascript": NodeTemplate,
        "typescript": NodeTemplate,
        "java": JavaTemplate,
    }
    
    template_class = templates.get(language.lower(), GenericTemplate)
    return template_class(**kwargs)
