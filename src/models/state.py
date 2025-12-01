"""
State management for the Agentic CI Orchestrator.

Defines the complete state schema passed between LangGraph nodes.
"""

from typing import Any, Dict, List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RepositoryMetadata(BaseModel):
    """Repository information extracted by detector."""
    owner: str
    name: str
    branch: str
    full_name: str  # owner/name
    language: Literal["python", "node", "java", "go", "rust", "ruby", "generic"]
    language_version: Optional[str] = None
    package_manager: Optional[str] = None  # pip, npm, maven, cargo, etc.
    has_tests: bool = False
    test_framework: Optional[str] = None
    has_linter: bool = False
    linter_type: Optional[str] = None
    build_tool: Optional[str] = None
    dependencies_file: Optional[str] = None  # requirements.txt, package.json, etc.
    custom_commands: Dict[str, str] = Field(default_factory=dict)


class WorkflowContent(BaseModel):
    """Generated workflow file content."""
    filename: str = "ci.yml"
    content: str
    path: str = ".github/workflows/ci.yml"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generator_model: str
    confidence: float = Field(ge=0.0, le=1.0)


class ValidationResult(BaseModel):
    """Result from YAML validation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    security_issues: List[str] = Field(default_factory=list)
    validator_version: str = "1.0.0"


class GitOperation(BaseModel):
    """Git commit and PR information."""
    branch_name: str
    commit_sha: Optional[str] = None
    commit_message: str
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_status: Optional[Literal["open", "closed", "merged"]] = None


class WorkflowRun(BaseModel):
    """GitHub Actions workflow run information."""
    run_id: Optional[int] = None
    run_number: Optional[int] = None
    status: Optional[Literal["queued", "in_progress", "completed"]] = None
    conclusion: Optional[Literal["success", "failure", "cancelled", "skipped"]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    html_url: Optional[str] = None


class FailureInfo(BaseModel):
    """Information about a CI failure."""
    job_name: str
    step_name: str
    error_message: str
    log_excerpt: str
    line_number: Optional[int] = None
    failure_type: Optional[Literal[
        "transient",
        "flaky_test",
        "test_failure",
        "dependency_error",
        "build_error",
        "workflow_misconfiguration",
        "secret_error",
        "unknown"
    ]] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    root_cause: Optional[str] = None


class HealingAttempt(BaseModel):
    """Record of a healing attempt."""
    attempt_number: int
    strategy: str
    patch_content: Optional[str] = None
    files_modified: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    sandbox_validated: bool = False
    sandbox_result: Optional[str] = None
    applied: bool = False
    resulted_in_success: Optional[bool] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DiffAnalysis(BaseModel):
    """Analysis of code changes."""
    files_changed: List[str]
    lines_added: int
    lines_removed: int
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_category: Literal["low", "medium", "high", "critical"]
    affected_functions: List[str] = Field(default_factory=list)
    requires_approval: bool


class AgentState(BaseModel):
    """
    Complete state passed between LangGraph nodes.
    
    This is the shared context for the entire orchestration pipeline.
    """
    
    # Input
    repo_owner: str
    repo_name: str
    repo_branch: str
    trigger_type: Literal["manual", "failure", "scheduled"] = "manual"
    
    # Orchestration control
    config: Optional[Any] = None  # Configuration object
    no_pr: bool = False  # Skip PR creation
    enable_monitoring: bool = False  # Enable workflow monitoring
    no_heal: bool = False  # Disable healing
    
    # Repository Detection
    repo_metadata: Optional[RepositoryMetadata] = None
    
    # Workflow Generation
    workflow_content: Optional[WorkflowContent] = None
    
    # Validation
    validation_result: Optional[ValidationResult] = None
    
    # Git Operations
    git_operation: Optional[GitOperation] = None
    
    # Workflow Execution
    workflow_run: Optional[WorkflowRun] = None
    
    # Failure Analysis
    failures: List[FailureInfo] = Field(default_factory=list)
    
    # Healing
    healing_attempts: List[HealingAttempt] = Field(default_factory=list)
    current_healing_count: int = 0
    
    # Diff Analysis
    diff_analysis: Optional[DiffAnalysis] = None
    
    # Approvals
    requires_human_approval: bool = False
    approval_granted: Optional[bool] = None
    approval_reason: Optional[str] = None
    
    # Error Handling
    errors: List[str] = Field(default_factory=list)
    current_retry_count: int = 0
    
    # Audit Trail
    agent_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Control Flow
    next_action: Optional[Literal[
        "detect",
        "generate",
        "validate",
        "commit",
        "pr_create",
        "dispatch",
        "monitor",
        "diagnose",
        "heal",
        "sandbox_test",
        "request_approval",
        "rollback",
        "complete",
        "fail"
    ]] = "detect"
    
    # Metadata
    run_id: str = Field(default_factory=lambda: f"run-{datetime.utcnow().timestamp()}")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_agent_record(self, agent_name: str, action: str, result: Any, duration: float):
        """Add an agent action to the history."""
        self.agent_history.append({
            "agent": agent_name,
            "action": action,
            "result": str(result)[:500],  # Truncate for storage
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def add_error(self, error: str):
        """Add an error to the error list."""
        self.errors.append(f"[{datetime.utcnow().isoformat()}] {error}")
    
    def should_continue_healing(self, max_attempts: int = 3) -> bool:
        """Check if more healing attempts are allowed."""
        return self.current_healing_count < max_attempts
    
    def get_latest_healing_attempt(self) -> Optional[HealingAttempt]:
        """Get the most recent healing attempt."""
        return self.healing_attempts[-1] if self.healing_attempts else None
