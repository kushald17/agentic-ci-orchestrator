"""
GitHub API client for repository operations, PR creation, and workflow management.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from github import Github, GithubException, Auth
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.WorkflowRun import WorkflowRun as GHWorkflowRun
import structlog

logger = structlog.get_logger()


class GitHubClient:
    """Client for GitHub API operations."""
    
    def __init__(self, token: str, api_url: str = "https://api.github.com"):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub Personal Access Token or App token
            api_url: GitHub API base URL (for Enterprise)
        """
        self.token = token
        self.api_url = api_url
        
        # Initialize PyGithub client with proper Auth
        auth = Auth.Token(token)
        if api_url == "https://api.github.com":
            self.client = Github(auth=auth)
        else:
            self.client = Github(base_url=api_url, auth=auth)
        
        self._rate_limit_checked = False
    
    def check_rate_limit(self) -> Tuple[int, int]:
        """
        Check GitHub API rate limit.
        
        Returns:
            Tuple of (remaining, limit)
        """
        rate_limit = self.client.get_rate_limit()
        core = rate_limit.core
        logger.info(
            "github_rate_limit",
            remaining=core.remaining,
            limit=core.limit,
            reset=core.reset,
        )
        self._rate_limit_checked = True
        return core.remaining, core.limit
    
    def get_repository(self, owner: str, name: str) -> Repository:
        """Get repository object."""
        try:
            repo = self.client.get_repo(f"{owner}/{name}")
            logger.info("repository_fetched", repo=f"{owner}/{name}")
            return repo
        except GithubException as e:
            logger.error("failed_to_fetch_repository", repo=f"{owner}/{name}", error=str(e))
            raise
    
    def get_file_content(self, repo: Repository, path: str, ref: str = "main") -> Optional[str]:
        """
        Get file content from repository.
        
        Args:
            repo: Repository object
            path: File path in repo
            ref: Branch or commit ref
        
        Returns:
            File content as string, or None if not found
        """
        try:
            content = repo.get_contents(path, ref=ref)
            if isinstance(content, list):
                return None  # Path is a directory
            return content.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                return None
            logger.error("failed_to_get_file", path=path, error=str(e))
            raise
    
    def list_files(self, repo: Repository, path: str = "", ref: str = "main") -> List[str]:
        """
        List files in a directory.
        
        Args:
            repo: Repository object
            path: Directory path (empty for root)
            ref: Branch or commit ref
        
        Returns:
            List of file paths
        """
        try:
            contents = repo.get_contents(path, ref=ref)
            files = []
            
            # Handle single file vs directory
            if not isinstance(contents, list):
                contents = [contents]
            
            for content in contents:
                if content.type == "file":
                    files.append(content.path)
                elif content.type == "dir":
                    # Recursively list subdirectories
                    files.extend(self.list_files(repo, content.path, ref))
            
            return files
        except GithubException as e:
            logger.error("failed_to_list_files", path=path, error=str(e))
            return []
    
    def create_branch(self, repo: Repository, branch_name: str, source_branch: str = "main") -> str:
        """
        Create a new branch.
        
        Args:
            repo: Repository object
            branch_name: Name for the new branch
            source_branch: Branch to branch from
        
        Returns:
            SHA of the branch head
        """
        try:
            source_ref = repo.get_git_ref(f"heads/{source_branch}")
            source_sha = source_ref.object.sha
            
            repo.create_git_ref(f"refs/heads/{branch_name}", source_sha)
            logger.info("branch_created", branch=branch_name, from_branch=source_branch)
            return source_sha
        except GithubException as e:
            if e.status == 422:  # Branch already exists
                logger.warning("branch_already_exists", branch=branch_name)
                ref = repo.get_git_ref(f"heads/{branch_name}")
                return ref.object.sha
            logger.error("failed_to_create_branch", branch=branch_name, error=str(e))
            raise
    
    def commit_file(
        self,
        repo: Repository,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> str:
        """
        Commit a file to a branch.
        
        Args:
            repo: Repository object
            path: File path in repo
            content: File content
            message: Commit message
            branch: Target branch
        
        Returns:
            Commit SHA
        """
        try:
            # Check if file exists
            existing_file = None
            try:
                existing_file = repo.get_contents(path, ref=branch)
            except GithubException:
                pass
            
            if existing_file:
                # Update existing file
                result = repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch,
                )
            else:
                # Create new file
                result = repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch,
                )
            
            commit_sha = result["commit"].sha
            logger.info("file_committed", path=path, branch=branch, sha=commit_sha)
            return commit_sha
            
        except GithubException as e:
            logger.error("failed_to_commit_file", path=path, branch=branch, error=str(e))
            raise
    
    def create_pull_request(
        self,
        repo: Repository,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> PullRequest:
        """
        Create a pull request.
        
        Args:
            repo: Repository object
            title: PR title
            body: PR description
            head: Head branch
            base: Base branch
        
        Returns:
            PullRequest object
        """
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base,
            )
            logger.info("pull_request_created", pr_number=pr.number, url=pr.html_url)
            return pr
        except GithubException as e:
            logger.error("failed_to_create_pr", head=head, base=base, error=str(e))
            raise
    
    def dispatch_workflow(
        self,
        repo: Repository,
        workflow_id: str,
        ref: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Trigger a workflow dispatch.
        
        Args:
            repo: Repository object
            workflow_id: Workflow filename or ID
            ref: Branch or tag to run on
            inputs: Optional workflow inputs
        
        Returns:
            True if dispatch successful
        """
        try:
            workflow = repo.get_workflow(workflow_id)
            workflow.create_dispatch(ref=ref, inputs=inputs or {})
            logger.info("workflow_dispatched", workflow=workflow_id, ref=ref)
            return True
        except GithubException as e:
            logger.error("failed_to_dispatch_workflow", workflow=workflow_id, error=str(e))
            return False
    
    def get_workflow_run(self, repo: Repository, run_id: int) -> Optional[GHWorkflowRun]:
        """Get workflow run by ID."""
        try:
            return repo.get_workflow_run(run_id)
        except GithubException as e:
            logger.error("failed_to_get_workflow_run", run_id=run_id, error=str(e))
            return None
    
    def get_latest_workflow_run(
        self,
        repo: Repository,
        branch: Optional[str] = None,
    ) -> Optional[GHWorkflowRun]:
        """Get the latest workflow run, optionally filtered by branch."""
        try:
            runs = repo.get_workflow_runs(branch=branch)
            if runs.totalCount > 0:
                return runs[0]
            return None
        except GithubException as e:
            logger.error("failed_to_get_latest_run", error=str(e))
            return None
    
    def get_workflow_run_logs(self, repo: Repository, run_id: int) -> Optional[str]:
        """
        Get logs from a workflow run.
        
        Args:
            repo: Repository object
            run_id: Workflow run ID
        
        Returns:
            Logs as string, or None if unavailable
        """
        try:
            run = repo.get_workflow_run(run_id)
            # Note: PyGithub doesn't have direct log access
            # Would need to use download_url and extract zip
            logger.warning("log_download_not_implemented", run_id=run_id)
            return None
        except GithubException as e:
            logger.error("failed_to_get_logs", run_id=run_id, error=str(e))
            return None
    
    def wait_for_workflow_completion(
        self,
        repo: Repository,
        run_id: int,
        timeout: int = 3600,
        poll_interval: int = 30,
    ) -> Optional[GHWorkflowRun]:
        """
        Wait for a workflow run to complete.
        
        Args:
            repo: Repository object
            run_id: Workflow run ID
            timeout: Maximum time to wait (seconds)
            poll_interval: Time between polls (seconds)
        
        Returns:
            WorkflowRun object if completed, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            run = self.get_workflow_run(repo, run_id)
            
            if run and run.status == "completed":
                logger.info(
                    "workflow_completed",
                    run_id=run_id,
                    conclusion=run.conclusion,
                    duration=time.time() - start_time,
                )
                return run
            
            time.sleep(poll_interval)
        
        logger.warning("workflow_wait_timeout", run_id=run_id, timeout=timeout)
        return None
    
    def close(self):
        """Close the client (cleanup)."""
        # PyGithub doesn't require explicit cleanup
        pass


def get_github_client(token: str, api_url: str = "https://api.github.com") -> GitHubClient:
    """Create a new GitHub client."""
    return GitHubClient(token=token, api_url=api_url)
