"""
Monitor Agent.

Tracks GitHub Actions workflow runs and detects failures.
"""

import time
from datetime import datetime
from typing import Optional
import structlog

from src.models.state import AgentState, WorkflowRun
from src.integrations.github_client import GitHubClient

logger = structlog.get_logger()


class MonitorAgent:
    """Monitors GitHub Actions workflow runs."""
    
    def __init__(
        self,
        github_client: GitHubClient,
        poll_interval: int = 10,
        max_wait_time: int = 300,
    ):
        """
        Initialize monitor agent.
        
        Args:
            github_client: GitHub API client
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait for completion
        """
        self.github_client = github_client
        self.poll_interval = poll_interval
        self.max_wait_time = max_wait_time
    
    def monitor(self, state: AgentState, workflow_path: str = ".github/workflows/ci.yml") -> AgentState:
        """
        Monitor workflow execution after PR creation.
        
        Args:
            state: Current state with git_operation (branch info)
            workflow_path: Path to workflow file to monitor
        
        Returns:
            Updated state with workflow_run information
        """
        if not state.git_operation or not state.git_operation.branch_name:
            state.add_error("Cannot monitor without git operation/branch")
            state.next_action = "fail"
            return state
        
        logger.info(
            "monitoring_workflow",
            repo=f"{state.repo_owner}/{state.repo_name}",
            branch=state.git_operation.branch_name,
        )
        
        start_time = time.time()
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            
            # Wait for workflow to start
            logger.info("waiting_for_workflow_run")
            workflow_run = self._wait_for_workflow_run(repo, state.git_operation.branch_name)
            
            if not workflow_run:
                state.add_error("No workflow run found within timeout")
                state.next_action = "fail"
                return state
            
            # Track the run
            run_info = WorkflowRun(
                run_id=workflow_run.id,
                run_number=workflow_run.run_number,
                status=workflow_run.status,
                conclusion=workflow_run.conclusion,
                started_at=workflow_run.created_at,
                completed_at=workflow_run.updated_at if workflow_run.status == "completed" else None,
                html_url=workflow_run.html_url,
            )
            
            state.workflow_run = run_info
            
            logger.info(
                "workflow_run_found",
                run_id=workflow_run.id,
                run_number=workflow_run.run_number,
                status=workflow_run.status,
            )
            
            # Wait for completion
            final_run = self._wait_for_completion(workflow_run)
            
            # Update with final status
            state.workflow_run.status = final_run.status
            state.workflow_run.conclusion = final_run.conclusion
            state.workflow_run.completed_at = final_run.updated_at
            
            duration = time.time() - start_time
            state.add_agent_record(
                agent_name="Monitor",
                action="monitor_workflow",
                result=f"Run #{final_run.run_number}: {final_run.conclusion}",
                duration=duration,
            )
            
            # Determine next action based on result
            if final_run.conclusion == "success":
                state.next_action = "complete"
                logger.info(
                    "workflow_succeeded",
                    run_id=final_run.id,
                    duration=duration,
                )
            elif final_run.conclusion == "failure":
                state.next_action = "diagnose"
                logger.warning(
                    "workflow_failed",
                    run_id=final_run.id,
                    duration=duration,
                )
            elif final_run.conclusion in ["cancelled", "skipped"]:
                state.next_action = "complete"
                logger.info(
                    "workflow_not_executed",
                    run_id=final_run.id,
                    conclusion=final_run.conclusion,
                )
            else:
                state.add_error(f"Unknown workflow conclusion: {final_run.conclusion}")
                state.next_action = "fail"
            
            return state
            
        except Exception as e:
            error_msg = f"Monitoring failed: {str(e)}"
            logger.error("monitoring_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    def _wait_for_workflow_run(self, repo, branch_name: str, max_attempts: int = 30):
        """
        Wait for a workflow run to appear for the branch.
        
        Args:
            repo: PyGithub repository object
            branch_name: Branch to check for runs
            max_attempts: Maximum polling attempts
        
        Returns:
            WorkflowRun object or None
        """
        for attempt in range(max_attempts):
            try:
                # Get recent workflow runs
                runs = repo.get_workflow_runs(branch=branch_name)
                
                for run in runs[:5]:  # Check last 5 runs
                    if run.head_branch == branch_name:
                        logger.info(
                            "workflow_run_detected",
                            run_id=run.id,
                            attempt=attempt + 1,
                        )
                        return run
                
                if attempt < max_attempts - 1:
                    logger.debug("workflow_not_started_yet", attempt=attempt + 1)
                    time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.warning("poll_error", error=str(e), attempt=attempt + 1)
                time.sleep(self.poll_interval)
        
        logger.error("workflow_run_not_found", branch=branch_name)
        return None
    
    def _wait_for_completion(self, workflow_run, max_attempts: int = 60):
        """
        Poll workflow run until it completes.
        
        Args:
            workflow_run: PyGithub WorkflowRun object
            max_attempts: Maximum polling attempts
        
        Returns:
            Updated WorkflowRun object
        """
        for attempt in range(max_attempts):
            try:
                # Refresh run status
                workflow_run.update()
                
                logger.debug(
                    "polling_status",
                    run_id=workflow_run.id,
                    status=workflow_run.status,
                    conclusion=workflow_run.conclusion,
                    attempt=attempt + 1,
                )
                
                if workflow_run.status == "completed":
                    return workflow_run
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.warning("poll_error", error=str(e), attempt=attempt + 1)
                time.sleep(self.poll_interval)
        
        logger.error("workflow_timeout", run_id=workflow_run.id)
        return workflow_run
    
    def get_workflow_logs(self, state: AgentState) -> Optional[str]:
        """
        Fetch workflow run logs.
        
        Args:
            state: State with workflow_run information
        
        Returns:
            Raw log text or None
        """
        if not state.workflow_run or not state.workflow_run.run_id:
            logger.error("no_workflow_run_to_fetch_logs")
            return None
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            run = repo.get_workflow_run(state.workflow_run.run_id)
            
            # Get logs URL (PyGithub doesn't directly provide log content)
            # We'll need to fetch it via API
            logs_url = run.logs_url
            
            logger.info("fetching_logs", run_id=run.id, logs_url=logs_url)
            
            # Use GitHub client to download logs
            # Note: This returns a ZIP file with all job logs
            # For now, we'll return the URL and parse in failure detector
            return logs_url
            
        except Exception as e:
            logger.error("log_fetch_failed", error=str(e))
            return None
