"""
Failure Detector Agent.

Analyzes workflow failures and classifies error types.
"""

import re
import time
from typing import List, Optional, Tuple
import structlog

from src.models.state import AgentState, FailureInfo
from src.integrations.github_client import GitHubClient

logger = structlog.get_logger()


class FailureDetectorAgent:
    """Detects and classifies CI failures."""
    
    # Error patterns for classification
    ERROR_PATTERNS = {
        "dependency_error": [
            r"could not find .*package",
            r"no matching distribution found",
            r"module .* has no attribute",
            r"cannot find module",
            r"error: package .* does not exist",
            r"failed to resolve",
            r"unresolved reference",
        ],
        "build_error": [
            r"compilation failed",
            r"build failed",
            r"syntax error",
            r"cannot find symbol",
            r"undefined reference",
            r"gradlew: not found",
            r"permission denied.*gradlew",
        ],
        "test_failure": [
            r"test.*failed",
            r"assertion.*failed",
            r"\d+ failed.*\d+ passed",
            r"expected .* but got",
        ],
        "workflow_misconfiguration": [
            r"invalid workflow file",
            r"unknown action",
            r"required.*not found",
            r"unable to locate.*action",
        ],
        "secret_error": [
            r"credentials.*not found",
            r"authentication failed",
            r"unauthorized",
        ],
    }
    
    def __init__(self, github_client: GitHubClient):
        """
        Initialize failure detector.
        
        Args:
            github_client: GitHub API client
        """
        self.github_client = github_client
    
    def detect(self, state: AgentState) -> AgentState:
        """
        Analyze workflow failure and extract error information.
        
        Args:
            state: Current state with workflow_run (must have failed)
        
        Returns:
            Updated state with failures list populated
        """
        if not state.workflow_run or state.workflow_run.conclusion != "failure":
            state.add_error("No failed workflow run to analyze")
            state.next_action = "fail"
            return state
        
        logger.info(
            "detecting_failures",
            repo=f"{state.repo_owner}/{state.repo_name}",
            run_id=state.workflow_run.run_id,
        )
        
        start_time = time.time()
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            run = repo.get_workflow_run(state.workflow_run.run_id)
            
            # Get all jobs for this run
            jobs = run.jobs()
            
            failures_found = []
            
            for job in jobs:
                if job.conclusion == "failure":
                    logger.info("analyzing_failed_job", job_name=job.name)
                    
                    # Analyze each step
                    for step in job.steps:
                        if step.conclusion == "failure":
                            failure = self._analyze_step_failure(
                                job_name=job.name,
                                step_name=step.name,
                                step=step,
                            )
                            if failure:
                                failures_found.append(failure)
            
            if not failures_found:
                # No specific failures found, create generic one
                failures_found.append(FailureInfo(
                    job_name="unknown",
                    step_name="unknown",
                    error_message="Workflow failed but no specific error detected",
                    log_excerpt="",
                    failure_type="unknown",
                    confidence=0.3,
                ))
            
            state.failures = failures_found
            
            duration = time.time() - start_time
            state.add_agent_record(
                agent_name="FailureDetector",
                action="detect_failures",
                result=f"Found {len(failures_found)} failure(s)",
                duration=duration,
            )
            
            # Check if healable
            is_healable = self._is_healable(failures_found)
            
            if is_healable:
                state.next_action = "heal"
                logger.info(
                    "failures_detected",
                    count=len(failures_found),
                    healable=True,
                )
            else:
                state.next_action = "request_approval"
                logger.warning(
                    "failures_not_healable",
                    count=len(failures_found),
                )
            
            return state
            
        except Exception as e:
            error_msg = f"Failure detection failed: {str(e)}"
            logger.error("detection_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    def _analyze_step_failure(
        self,
        job_name: str,
        step_name: str,
        step,
    ) -> Optional[FailureInfo]:
        """
        Analyze a failed step and create FailureInfo.
        
        Args:
            job_name: Name of the job
            step_name: Name of the step
            step: PyGithub step object
        
        Returns:
            FailureInfo or None
        """
        try:
            # Extract error from step (limited info available via API)
            # We'll need to parse the step output if available
            
            # For now, use step name and number to infer error
            error_message = f"Step '{step_name}' failed"
            log_excerpt = ""
            
            # Try to get more details from step
            if hasattr(step, 'conclusion') and step.conclusion:
                error_message += f" with conclusion: {step.conclusion}"
            
            # Classify failure type based on step name
            failure_type, confidence = self._classify_failure(step_name, error_message)
            
            return FailureInfo(
                job_name=job_name,
                step_name=step_name,
                error_message=error_message,
                log_excerpt=log_excerpt,
                failure_type=failure_type,
                confidence=confidence,
                root_cause=self._infer_root_cause(step_name, failure_type),
            )
            
        except Exception as e:
            logger.error("step_analysis_failed", error=str(e))
            return None
    
    def _classify_failure(self, step_name: str, error_text: str) -> Tuple[str, float]:
        """
        Classify failure type based on patterns.
        
        Args:
            step_name: Name of the failed step
            error_text: Error message text
        
        Returns:
            (failure_type, confidence) tuple
        """
        combined_text = f"{step_name} {error_text}".lower()
        
        # Check each pattern category
        for failure_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return (failure_type, 0.8)
        
        # Fallback: infer from step name
        if "test" in step_name.lower():
            return ("test_failure", 0.6)
        elif "build" in step_name.lower() or "compile" in step_name.lower():
            return ("build_error", 0.6)
        elif "install" in step_name.lower() or "dependencies" in step_name.lower():
            return ("dependency_error", 0.6)
        
        return ("unknown", 0.3)
    
    def _infer_root_cause(self, step_name: str, failure_type: str) -> str:
        """
        Infer root cause from step name and failure type.
        
        Args:
            step_name: Name of failed step
            failure_type: Classified failure type
        
        Returns:
            Human-readable root cause description
        """
        if failure_type == "build_error":
            if "gradlew" in step_name.lower():
                return "Gradle wrapper may not be executable (missing chmod +x gradlew)"
            return "Build configuration or compilation issue"
        
        elif failure_type == "dependency_error":
            return "Missing or incompatible dependencies"
        
        elif failure_type == "test_failure":
            return "Test assertions failed or test environment issue"
        
        elif failure_type == "workflow_misconfiguration":
            return "GitHub Actions workflow configuration error"
        
        elif failure_type == "secret_error":
            return "Missing or invalid credentials/secrets"
        
        return "Unknown cause - manual investigation required"
    
    def _is_healable(self, failures: List[FailureInfo]) -> bool:
        """
        Determine if failures can be automatically healed.
        
        Args:
            failures: List of detected failures
        
        Returns:
            True if healable, False otherwise
        """
        # For Phase 3, we're just detecting
        # Phase 4 will implement actual healing
        
        healable_types = {
            "workflow_misconfiguration",
            "build_error",  # Some build errors like missing chmod
        }
        
        for failure in failures:
            if failure.failure_type in healable_types and failure.confidence > 0.6:
                return True
        
        # For now, consider most failures not auto-healable
        # This will be expanded in Phase 4
        return False
