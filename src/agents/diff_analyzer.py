"""
Diff Analyzer Agent.

Analyzes code changes to determine risk level and approval requirements.
"""

from typing import List
import structlog

from src.models.state import AgentState, DiffAnalysis

logger = structlog.get_logger()


class DiffAnalyzerAgent:
    """Analyzes workflow changes for risk assessment."""
    
    def __init__(self, config: dict):
        """
        Initialize analyzer with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.auto_commit_threshold = config.get("safety", {}).get("confidence", {}).get("auto_commit_threshold", 0.9)
    
    def analyze(self, state: AgentState) -> AgentState:
        """
        Analyze workflow changes.
        
        Args:
            state: Current state with workflow_content and validation_result
        
        Returns:
            Updated state with diff_analysis
        """
        if not state.workflow_content:
            state.add_error("Cannot analyze diff without workflow content")
            state.next_action = "fail"
            return state
        
        logger.info("analyzing_diff", repo=f"{state.repo_owner}/{state.repo_name}")
        
        try:
            workflow_path = state.workflow_content.path
            workflow_size = len(state.workflow_content.content)
            
            # Analyze changes
            files_changed = [workflow_path]
            lines_added = state.workflow_content.content.count('\n')
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(state)
            risk_category = self._categorize_risk(risk_score)
            
            # Determine if approval required
            requires_approval = self._requires_approval(state, risk_score)
            
            # Create analysis
            diff_analysis = DiffAnalysis(
                files_changed=files_changed,
                lines_added=lines_added,
                lines_removed=0,  # New file
                risk_score=risk_score,
                risk_category=risk_category,
                affected_functions=[],
                requires_approval=requires_approval,
            )
            
            state.diff_analysis = diff_analysis
            state.next_action = "commit"
            
            logger.info(
                "diff_analyzed",
                risk_score=risk_score,
                risk_category=risk_category,
                requires_approval=requires_approval,
            )
            
            return state
            
        except Exception as e:
            error_msg = f"Diff analysis failed: {str(e)}"
            logger.error("analysis_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    def _calculate_risk_score(self, state: AgentState) -> float:
        """
        Calculate risk score (0.0 = low risk, 1.0 = high risk).
        
        Factors:
        - Confidence score from generation
        - Validation issues
        - Workflow complexity
        """
        risk = 0.0
        
        # Base risk from confidence (inverse)
        if state.workflow_content:
            confidence = state.workflow_content.confidence
            risk += (1.0 - confidence) * 0.4  # 40% weight
        
        # Risk from validation warnings
        if state.validation_result and state.validation_result.warnings:
            warning_count = len(state.validation_result.warnings)
            risk += min(warning_count * 0.1, 0.3)  # Up to 30% weight
        
        # Risk from workflow size (complexity)
        if state.workflow_content:
            lines = state.workflow_content.content.count('\n')
            if lines > 200:
                risk += 0.2
            elif lines > 100:
                risk += 0.1
        
        # Risk from security issues (should be 0 if validated)
        if state.validation_result and state.validation_result.security_issues:
            risk += 0.5  # Major risk boost
        
        return min(risk, 1.0)  # Cap at 1.0
    
    def _categorize_risk(self, risk_score: float) -> str:
        """Categorize risk level."""
        if risk_score >= 0.7:
            return "critical"
        elif risk_score >= 0.5:
            return "high"
        elif risk_score >= 0.3:
            return "medium"
        else:
            return "low"
    
    def _requires_approval(self, state: AgentState, risk_score: float) -> bool:
        """
        Determine if human approval is required.
        
        Rules:
        - High/critical risk always requires approval
        - Low confidence requires approval
        - Security issues require approval
        - Low risk + high confidence can be auto-committed (Phase 5)
        """
        # Security issues always require approval
        if state.validation_result and state.validation_result.security_issues:
            return True
        
        # High risk requires approval
        if risk_score >= 0.5:
            return True
        
        # Low confidence requires approval
        if state.workflow_content and state.workflow_content.confidence < 0.7:
            return True
        
        # For Phase 2, always create PR (no auto-commit yet)
        return True
