"""
YAML Validator Agent.

Validates workflow YAML for syntax, structure, and security issues.
"""

import re
from typing import List, Tuple
import structlog
import yaml

from src.models.state import AgentState, ValidationResult

logger = structlog.get_logger()


class YAMLValidatorAgent:
    """Validates GitHub Actions workflow YAML."""
    
    def __init__(self, config: dict):
        """
        Initialize validator with configuration.
        
        Args:
            config: Safety configuration from config.yaml
        """
        self.config = config
        self.forbidden_actions = config.get("safety", {}).get("forbidden", {}).get("unsafe_actions", [])
        self.forbidden_commands = config.get("safety", {}).get("forbidden", {}).get("forbidden_commands", [])
        self.max_file_size = config.get("workflows", {}).get("max_file_size", 10240)
    
    def validate(self, state: AgentState) -> AgentState:
        """
        Validate workflow YAML.
        
        Args:
            state: Current state with workflow_content
        
        Returns:
            Updated state with validation_result
        """
        if not state.workflow_content:
            state.add_error("Cannot validate without workflow content")
            state.next_action = "fail"
            return state
        
        logger.info("validating_workflow", size=len(state.workflow_content.content))
        
        errors: List[str] = []
        warnings: List[str] = []
        security_issues: List[str] = []
        
        content = state.workflow_content.content
        
        # Check file size
        if len(content) > self.max_file_size:
            errors.append(f"Workflow file too large: {len(content)} bytes (max: {self.max_file_size})")
        
        # Validate YAML syntax
        try:
            workflow_dict = yaml.safe_load(content)
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {str(e)}")
            state.validation_result = ValidationResult(
                is_valid=False,
                errors=errors,
            )
            state.next_action = "generate"  # Regenerate
            return state
        
        # Validate workflow structure
        struct_errors = self._validate_structure(workflow_dict)
        errors.extend(struct_errors)
        
        # Check for security issues
        sec_issues = self._check_security(content, workflow_dict)
        security_issues.extend(sec_issues)
        
        # Check for warnings
        warns = self._check_warnings(workflow_dict)
        warnings.extend(warns)
        
        # Determine if valid
        is_valid = len(errors) == 0 and len(security_issues) == 0
        
        validation_result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            security_issues=security_issues,
        )
        
        state.validation_result = validation_result
        
        if is_valid:
            state.next_action = "commit"
            logger.info("validation_passed", warnings=len(warnings))
        else:
            state.next_action = "generate"  # Regenerate if failed
            logger.warning(
                "validation_failed",
                errors=len(errors),
                security_issues=len(security_issues),
            )
        
        return state
    
    def _validate_structure(self, workflow: dict) -> List[str]:
        """Validate workflow structure."""
        errors = []
        
        # Required top-level keys (name is optional, not an error)
        # if "name" not in workflow:
        #     errors.append("Workflow missing 'name' field")
        
        if "on" not in workflow:
            errors.append("Workflow missing 'on' trigger configuration")
        
        if "jobs" not in workflow:
            errors.append("Workflow missing 'jobs' configuration")
            return errors
        
        # Validate jobs
        jobs = workflow.get("jobs", {})
        if not jobs:
            errors.append("Workflow has no jobs defined")
            return errors
        
        for job_name, job_config in jobs.items():
            if not isinstance(job_config, dict):
                errors.append(f"Job '{job_name}' has invalid configuration")
                continue
            
            # Check for runs-on
            if "runs-on" not in job_config:
                errors.append(f"Job '{job_name}' missing 'runs-on'")
            
            # Check for steps
            if "steps" not in job_config:
                errors.append(f"Job '{job_name}' missing 'steps'")
            else:
                steps = job_config["steps"]
                if not isinstance(steps, list) or len(steps) == 0:
                    errors.append(f"Job '{job_name}' has no steps")
        
        return errors
    
    def _check_security(self, content: str, workflow: dict) -> List[str]:
        """Check for security issues."""
        issues = []
        
        # Check for inline secrets (basic patterns)
        secret_patterns = [
            r'(?i)(password|token|key|secret)\s*[:=]\s*["\']?[\w\-/+]{20,}["\']?',
            r'(?i)ghp_[a-zA-Z0-9]{36}',  # GitHub tokens
            r'(?i)github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}',  # GitHub PATs
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, content):
                issues.append(f"Potential inline secret detected (pattern: {pattern[:50]}...)")
        
        # Check for forbidden actions
        for action in self.forbidden_actions:
            action_pattern = action.replace("*", ".*")
            if re.search(f"uses:.*{action_pattern}", content):
                issues.append(f"Forbidden action detected: {action}")
        
        # Check for forbidden commands
        for command in self.forbidden_commands:
            if command in content:
                issues.append(f"Forbidden command detected: {command}")
        
        # Check for dangerous shell patterns
        dangerous_patterns = [
            r'eval\s+\$',
            r'\$\([^)]*curl[^)]*\)',
            r'wget.*\|.*sh',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                issues.append(f"Dangerous shell pattern detected: {pattern}")
        
        # Check workflow permissions
        jobs = workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            if "permissions" in job_config:
                perms = job_config["permissions"]
                if isinstance(perms, dict):
                    # Check for overly broad permissions
                    if perms.get("contents") == "write":
                        issues.append(f"Job '{job_name}' has write access to contents (use with caution)")
                    if perms.get("packages") == "write":
                        issues.append(f"Job '{job_name}' has write access to packages (use with caution)")
        
        return issues
    
    def _check_warnings(self, workflow: dict) -> List[str]:
        """Check for potential issues (non-blocking)."""
        warnings = []
        
        # Check for missing caching
        jobs = workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            has_cache = any(
                step.get("uses", "").startswith("actions/cache")
                for step in steps if isinstance(step, dict)
            )
            
            if not has_cache:
                warnings.append(f"Job '{job_name}' has no caching configured (may be slower)")
        
        # Check for missing timeout
        for job_name, job_config in jobs.items():
            if "timeout-minutes" not in job_config:
                warnings.append(f"Job '{job_name}' has no timeout configured")
        
        # Check for matrix build limits
        for job_name, job_config in jobs.items():
            if "strategy" in job_config and "matrix" in job_config["strategy"]:
                matrix = job_config["strategy"]["matrix"]
                # Calculate matrix combinations
                combinations = 1
                for key, values in matrix.items():
                    if isinstance(values, list):
                        combinations *= len(values)
                
                max_combinations = self.config.get("workflows", {}).get("max_matrix_combinations", 10)
                if combinations > max_combinations:
                    warnings.append(
                        f"Job '{job_name}' matrix has {combinations} combinations "
                        f"(max recommended: {max_combinations})"
                    )
        
        return warnings
