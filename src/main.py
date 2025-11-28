"""
Main entry point for the Agentic CI Orchestrator.
"""

import argparse
import sys
from datetime import datetime

from src.config import get_config
from src.logging_config import configure_logging, get_logger
from src.models.state import AgentState
from src.orchestrator import LangGraphOrchestrator

logger = get_logger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Agentic CI Orchestrator - Autonomous CI pipeline generation and healing"
    )
    
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository in format owner/name (e.g., octocat/Hello-World)",
    )
    
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch to work with (default: main)",
    )
    
    parser.add_argument(
        "--mode",
        choices=["detect-only", "generate-only", "full"],
        default="full",
        help="Execution mode (default: full)",
    )
    
    parser.add_argument(
        "--config",
        help="Path to config.yaml (default: ./config.yaml)",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - no actual commits or PRs",
    )
    
    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="Skip PR creation (only commit to branch)",
    )
    
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor workflow execution after PR creation",
    )
    
    parser.add_argument(
        "--no-heal",
        action="store_true",
        help="Disable automatic healing of failures",
    )
    
    return parser.parse_args()


def print_results(state: AgentState, mode: str):
    """Print results based on execution mode."""
    if mode == "detect-only":
        print("\n=== Repository Detection Results ===")
        if state.repo_metadata:
            print(f"Language: {state.repo_metadata.language}")
            print(f"Package Manager: {state.repo_metadata.package_manager}")
            print(f"Build Tool: {state.repo_metadata.build_tool}")
            print(f"Has Tests: {state.repo_metadata.has_tests}")
            print(f"Has Linter: {state.repo_metadata.has_linter}")
            if state.repo_metadata.custom_commands:
                print(f"Custom Commands: {list(state.repo_metadata.custom_commands.keys())}")
        else:
            print("Detection failed - no metadata available")
            
    elif mode == "generate-only":
        print("\n=== Generated Workflow ===")
        if state.workflow_content:
            print(state.workflow_content.content)
        else:
            print("Generation failed - no workflow content")
            
        print("\n=== Validation Results ===")
        if state.validation_result:
            print(f"Valid: {state.validation_result.is_valid}")
            if state.validation_result.warnings:
                print(f"Warnings: {len(state.validation_result.warnings)}")
                for warning in state.validation_result.warnings:
                    print(f"  - {warning}")
        else:
            print("Validation not performed")
            
    elif mode == "full":
        if state.next_action == "fail":
            print("\n❌ Orchestration failed!")
            if state.errors:
                print("Errors:")
                for error in state.errors:
                    print(f"  - {error}")
        else:
            print("\n✓ Orchestration completed successfully!")
            
            if state.git_operation:
                print(f"  Branch: {state.git_operation.branch_name}")
                if state.git_operation.commit_sha:
                    print(f"  Commit: {state.git_operation.commit_sha[:8]}")
                if state.git_operation.pr_number:
                    print(f"  PR #{state.git_operation.pr_number}")
                    print(f"  URL: {state.git_operation.pr_url}")
            
            if state.workflow_content:
                print(f"  Confidence: {state.workflow_content.confidence:.2%}")
                
            if state.diff_analysis:
                print(f"  Risk Level: {state.diff_analysis.risk_category.upper()}")
            
            if state.workflow_run:
                print(f"  Workflow Status: {state.workflow_run.conclusion.upper()}")
                if state.workflow_run.html_url:
                    print(f"  Workflow URL: {state.workflow_run.html_url}")
            
            if state.healing_attempts:
                print(f"  Healing Attempts: {len(state.healing_attempts)}")
                for attempt in state.healing_attempts:
                    status = "✓" if attempt.resulted_in_success else "⚠️"
                    print(f"    {status} {attempt.strategy} (confidence: {attempt.confidence:.0%})")


def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure logging
    configure_logging(debug=args.debug)
    
    logger.info("orchestrator_starting", 
                repo=args.repo, 
                branch=args.branch, 
                mode=args.mode)
    
    # Parse repository owner/name
    try:
        repo_owner, repo_name = args.repo.split("/", 1)
    except ValueError:
        logger.error("invalid_repo_format", repo=args.repo)
        print(f"Error: Invalid repository format '{args.repo}'. Use 'owner/name'.")
        sys.exit(1)
    
    # Load configuration
    try:
        config = get_config(args.config)
        logger.info("config_loaded")
    except Exception as e:
        logger.error("config_load_failed", error=str(e))
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Create initial state
    initial_state = AgentState(
        repo_owner=repo_owner,
        repo_name=repo_name,
        repo_branch=args.branch,
        no_pr=args.no_pr or args.dry_run,
        enable_monitoring=args.monitor and not args.dry_run,
        no_heal=args.no_heal or args.dry_run,
    )
    
    # Initialize orchestrator
    try:
        orchestrator = LangGraphOrchestrator(config)
        logger.info("langgraph_orchestrator_initialized")
    except Exception as e:
        logger.error("orchestrator_init_failed", error=str(e))
        print(f"Error initializing orchestrator: {e}")
        sys.exit(1)
    
    # Execute workflow
    start_time = datetime.utcnow()
    
    try:
        # Handle different execution modes by setting next_action
        if args.mode == "detect-only":
            # Only run detection, then stop
            initial_state.next_action = "detect"
        elif args.mode == "generate-only":
            # Run through validation, then stop
            initial_state.next_action = "detect" 
        elif args.mode == "full":
            # Run full pipeline
            initial_state.next_action = "detect"
        
        # Execute the LangGraph workflow
        final_state = orchestrator.run(initial_state)
        
        # Handle mode-specific stopping points
        if args.mode == "detect-only":
            # Stop after detection
            if final_state.repo_metadata:
                final_state.next_action = "complete"
        elif args.mode == "generate-only" or args.dry_run:
            # Stop after validation
            if final_state.validation_result:
                final_state.next_action = "complete"
        
        # Print results
        print_results(final_state, args.mode)
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("orchestrator_complete", 
                   duration=duration,
                   final_action=final_state.next_action,
                   total_agents_executed=len(final_state.agent_history),
                   success=final_state.next_action != "fail")
        
        # Exit with appropriate code
        if final_state.next_action == "fail":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("orchestrator_interrupted")
        print("\nOperation interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        logger.error("orchestrator_exception", error=str(e), traceback=True)
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()