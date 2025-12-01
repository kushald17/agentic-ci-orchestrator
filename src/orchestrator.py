"""
LangGraph-based orchestrator for the Agentic CI system.

This module implements the agent workflow using LangGraph's StateGraph
for proper agent coordination, conditional routing, and parallel execution.
"""

from typing import Dict, Any, Literal, Annotated
import time
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict

from src.config import Config
from src.models.state import AgentState
from src.integrations import get_ollama_client, get_github_client
from src.agents import (
    RepositoryDetectorAgent,
    WorkflowGeneratorAgent, 
    YAMLValidatorAgent
)
from src.agents.diff_analyzer import DiffAnalyzerAgent
from src.agents.git_commit import GitCommitAgent
from src.agents.pr_creator import PRCreatorAgent
from src.agents.monitor import MonitorAgent
from src.agents.failure_detector import FailureDetectorAgent
from src.agents.healer import HealerAgent
from src.logging_config import get_logger

logger = get_logger(__name__)


# Node functions for LangGraph
def detect_node(state: dict) -> dict:
    """Repository detection node."""
    logger.info("langgraph_node_start", node="detect")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState for compatibility
        agent_state = AgentState(**state)
        config = agent_state.config
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        detector = RepositoryDetectorAgent(github_client)
        result = detector.detect(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("RepositoryDetectorAgent", "detect", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="detect", duration=duration, 
                   language=result.repo_metadata.language if result.repo_metadata else None)
        
        # Convert back to dict for LangGraph
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="detect", error=str(e))
        # Update state with error
        state["errors"] = state.get("errors", []) + [f"Detection failed: {str(e)}"]
        state["next_action"] = "fail"
        return state


def generate_node(state: dict) -> dict:
    """Workflow generation node."""
    logger.info("langgraph_node_start", node="generate")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        ollama_client = get_ollama_client(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
        )
        
        # Health check
        if not ollama_client.health_check():
            agent_state.add_error("Ollama is not available")
            agent_state.next_action = "fail"
            return agent_state.dict()
        
        generator = WorkflowGeneratorAgent(
            ollama_client=ollama_client,
            model=config.ollama_reasoning_model,
        )
        
        result = generator.generate(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("WorkflowGeneratorAgent", "generate", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="generate", duration=duration,
                   confidence=result.workflow_content.confidence if result.workflow_content else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="generate", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Generation failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def validate_node(state: dict) -> dict:
    """Workflow validation node."""
    logger.info("langgraph_node_start", node="validate")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        # Pass the full config dict to validator
        validator = YAMLValidatorAgent(config.get_all())
        
        result = validator.validate(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("YAMLValidatorAgent", "validate", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="validate", duration=duration,
                   valid=result.validation_result.is_valid if result.validation_result else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="validate", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Validation failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def diff_analyze_node(state: dict) -> dict:
    """Diff analysis node."""
    logger.info("langgraph_node_start", node="diff_analyze")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        # Pass the full config dict to analyzer
        analyzer = DiffAnalyzerAgent(config.get_all())
        
        result = analyzer.analyze(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("DiffAnalyzerAgent", "analyze", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="diff_analyze", duration=duration,
                   risk_category=result.diff_analysis.risk_category if result.diff_analysis else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="diff_analyze", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Diff analysis failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def commit_node(state: dict) -> dict:
    """Git commit node."""
    logger.info("langgraph_node_start", node="commit")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        committer = GitCommitAgent(github_client)
        result = committer.commit(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("GitCommitAgent", "commit", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="commit", duration=duration,
                   branch=result.git_operation.branch_name if result.git_operation else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="commit", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Commit failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def pr_create_node(state: dict) -> dict:
    """PR creation node."""
    logger.info("langgraph_node_start", node="pr_create")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        ollama_client = get_ollama_client(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
        )
        
        pr_creator = PRCreatorAgent(
            github_client=github_client,
            ollama_client=ollama_client,
            model=config.ollama_lightweight_model,
        )
        
        result = pr_creator.create_pr(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("PRCreatorAgent", "create_pr", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="pr_create", duration=duration,
                   pr_number=result.git_operation.pr_number if result.git_operation else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="pr_create", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"PR creation failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def monitor_node(state: dict) -> dict:
    """Workflow monitoring node."""
    logger.info("langgraph_node_start", node="monitor")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        monitor = MonitorAgent(
            github_client=github_client,
            poll_interval=10,
            max_wait_time=300,
        )
        
        result = monitor.monitor(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("MonitorAgent", "monitor", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="monitor", duration=duration,
                   conclusion=result.workflow_run.conclusion if result.workflow_run else None)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="monitor", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Monitoring failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def failure_detect_node(state: dict) -> dict:
    """Failure detection node."""
    logger.info("langgraph_node_start", node="failure_detect")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        detector = FailureDetectorAgent(github_client)
        result = detector.detect(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("FailureDetectorAgent", "detect", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="failure_detect", duration=duration,
                   failures_found=len(result.failures) if result.failures else 0)
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="failure_detect", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Failure detection failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


def heal_node(state: dict) -> dict:
    """Healing node."""
    logger.info("langgraph_node_start", node="heal")
    start_time = time.time()
    
    try:
        # Convert dict to AgentState
        agent_state = AgentState(**state)
        config = agent_state.config
        
        github_client = get_github_client(
            token=config.github_token,
            api_url=config.github_api_url,
        )
        
        ollama_client = get_ollama_client(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
        )
        
        healer = HealerAgent(
            github_client=github_client,
            ollama_client=ollama_client,
            model=config.ollama_reasoning_model,
            max_attempts=config.safety_max_healing_attempts_per_run,
        )
        
        result = healer.heal(agent_state)
        
        duration = time.time() - start_time
        result.add_agent_record("HealerAgent", "heal", result.next_action, duration)
        
        logger.info("langgraph_node_complete", node="heal", duration=duration,
                   healing_attempts=len(result.healing_attempts))
        
        return result.dict()
        
    except Exception as e:
        logger.error("langgraph_node_failed", node="heal", error=str(e))
        agent_state = AgentState(**state)
        agent_state.add_error(f"Healing failed: {str(e)}")
        agent_state.next_action = "fail"
        return agent_state.dict()


# Conditional routing functions
def should_continue_after_detect(state: dict) -> Literal["generate", "fail"]:
    """Route after detection."""
    if state.get("next_action") == "fail":
        return "fail"
    return "generate"


def should_continue_after_generate(state: dict) -> Literal["validate", "fail"]:
    """Route after generation."""
    if state.get("next_action") == "fail":
        return "fail"
    return "validate"


def should_continue_after_validate(state: dict) -> Literal["diff_analyze", "generate", "fail"]:
    """Route after validation."""
    if state.get("next_action") == "fail":
        return "fail"
    elif state.get("next_action") == "regenerate":
        return "generate"  # Loop back to generator for fixes
    return "diff_analyze"


def should_continue_after_diff_analyze(state: dict) -> Literal["commit", "fail"]:
    """Route after diff analysis."""
    if state.get("next_action") == "fail":
        return "fail"
    return "commit"


def should_continue_after_commit(state: dict) -> Literal["pr_create", "complete", "fail"]:
    """Route after commit."""
    if state.get("next_action") == "fail":
        return "fail"
    # Check if no-pr mode or auto-commit mode
    if state.get("no_pr"):
        return "complete"
    return "pr_create"


def should_continue_after_pr(state: dict) -> Literal["monitor", "complete", "fail"]:
    """Route after PR creation."""
    if state.get("next_action") == "fail":
        return "fail"
    # Check if monitoring is requested
    if state.get("enable_monitoring"):
        return "monitor"
    return "complete"


def should_continue_after_monitor(state: dict) -> Literal["failure_detect", "complete", "fail"]:
    """Route after monitoring."""
    if state.get("next_action") == "fail":
        return "fail"
    elif (state.get("workflow_run") and 
          state["workflow_run"].get("conclusion") == "failure"):
        return "failure_detect"
    return "complete"


def should_continue_after_failure_detect(state: dict) -> Literal["heal", "complete", "fail"]:
    """Route after failure detection."""
    if state.get("next_action") == "fail":
        return "fail"
    elif state.get("next_action") == "heal" and not state.get("no_heal"):
        return "heal"
    return "complete"


def should_continue_after_heal(state: dict) -> Literal["monitor", "complete", "fail"]:
    """Route after healing."""
    if state.get("next_action") == "fail":
        return "fail"
    elif state.get("next_action") == "monitor":
        return "monitor"  # Re-monitor healed workflow
    return "complete"


class LangGraphOrchestrator:
    """LangGraph-based orchestrator for the Agentic CI system."""
    
    def __init__(self, config: Config):
        self.config = config
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """Build the LangGraph workflow."""
        logger.info("building_langgraph_workflow")
        
        # Define state schema as a type annotation instead of using StateGraph(AgentState)
        from typing import Any
        
        # Create state graph with dict schema
        workflow = StateGraph(dict)
        
        # Add nodes
        workflow.add_node("detect", detect_node)
        workflow.add_node("generate", generate_node)
        workflow.add_node("validate", validate_node)
        workflow.add_node("diff_analyze", diff_analyze_node)
        workflow.add_node("commit", commit_node)
        workflow.add_node("pr_create", pr_create_node)
        workflow.add_node("monitor", monitor_node)
        workflow.add_node("failure_detect", failure_detect_node)
        workflow.add_node("heal", heal_node)
        
        # Add edges
        workflow.add_edge(START, "detect")
        
        # Conditional edges for routing
        workflow.add_conditional_edges(
            "detect",
            should_continue_after_detect,
            {"generate": "generate", "fail": END}
        )
        
        workflow.add_conditional_edges(
            "generate",
            should_continue_after_generate,
            {"validate": "validate", "fail": END}
        )
        
        workflow.add_conditional_edges(
            "validate",
            should_continue_after_validate,
            {
                "diff_analyze": "diff_analyze",
                "generate": "generate",  # Regeneration loop
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "diff_analyze",
            should_continue_after_diff_analyze,
            {"commit": "commit", "fail": END}
        )
        
        workflow.add_conditional_edges(
            "commit",
            should_continue_after_commit,
            {
                "pr_create": "pr_create",
                "complete": END,
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "pr_create",
            should_continue_after_pr,
            {
                "monitor": "monitor",
                "complete": END,
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "monitor",
            should_continue_after_monitor,
            {
                "failure_detect": "failure_detect",
                "complete": END,
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "failure_detect",
            should_continue_after_failure_detect,
            {
                "heal": "heal",
                "complete": END,
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "heal",
            should_continue_after_heal,
            {
                "monitor": "monitor",  # Re-monitor after healing
                "complete": END,
                "fail": END
            }
        )
        
        # Compile workflow
        compiled_workflow = workflow.compile()
        
        logger.info("langgraph_workflow_built", nodes=len(workflow.nodes))
        return compiled_workflow
    
    def run(self, initial_state: AgentState) -> AgentState:
        """Run the orchestrator workflow."""
        logger.info("langgraph_orchestrator_start", 
                   repo=f"{initial_state.repo_owner}/{initial_state.repo_name}")
        
        # Add config to state
        initial_state.config = self.config
        
        # Convert to dict for LangGraph
        state_dict = initial_state.model_dump()
        
        # Execute workflow
        try:
            result_dict = self.workflow.invoke(state_dict)
            
            # Convert back to AgentState
            result_state = AgentState(**result_dict)
            
            logger.info("langgraph_orchestrator_complete",
                       final_action=result_state.next_action,
                       total_agents=len(result_state.agent_history))
            
            return result_state
            
        except Exception as e:
            logger.error("langgraph_orchestrator_failed", error=str(e))
            initial_state.add_error(f"Orchestrator failed: {str(e)}")
            initial_state.next_action = "fail"
            return initial_state