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


def run_detection_phase(state: AgentState, config) -> AgentState:
    """Run repository detection phase."""
    logger.info("phase_start", phase="detection")
    
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    
    detector = RepositoryDetectorAgent(github_client)
    state = detector.detect(state)
    
    if state.next_action == "fail":
        logger.error("detection_failed", errors=state.errors)
        return state
    
    logger.info(
        "detection_complete",
        language=state.repo_metadata.language,
        has_tests=state.repo_metadata.has_tests,
    )
    
    return state


def run_generation_phase(state: AgentState, config) -> AgentState:
    """Run workflow generation phase."""
    logger.info("phase_start", phase="generation")
    
    ollama_client = get_ollama_client(
        base_url=config.ollama_base_url,
        timeout=config.ollama_timeout,
    )
    
    # Health check
    if not ollama_client.health_check():
        logger.error("ollama_unavailable")
        state.add_error("Ollama is not available")
        state.next_action = "fail"
        return state
    
    generator = WorkflowGeneratorAgent(
        ollama_client=ollama_client,
        model=config.ollama_reasoning_model,
    )
    
    state = generator.generate(state)
    
    if state.next_action == "fail":
        logger.error("generation_failed", errors=state.errors)
        return state
    
    logger.info(
        "generation_complete",
        workflow_size=len(state.workflow_content.content),
        confidence=state.workflow_content.confidence,
    )
    
    return state


def run_validation_phase(state: AgentState, config) -> AgentState:
    """Run workflow validation phase."""
    logger.info("phase_start", phase="validation")
    
    validator = YAMLValidatorAgent(config.get_all())
    state = validator.validate(state)
    
    if not state.validation_result.is_valid:
        logger.error(
            "validation_failed",
            errors=state.validation_result.errors,
            security_issues=state.validation_result.security_issues,
        )
        # For now, fail if validation fails
        # In a full implementation, we'd regenerate
        state.next_action = "fail"
        return state
    
    if state.validation_result.warnings:
        logger.warning(
            "validation_warnings",
            warnings=state.validation_result.warnings,
        )
    
    logger.info("validation_complete", status="passed")
    
    return state


def run_diff_analysis_phase(state: AgentState, config) -> AgentState:
    """Run diff analysis phase."""
    logger.info("phase_start", phase="diff_analysis")
    
    analyzer = DiffAnalyzerAgent(config.get_all())
    state = analyzer.analyze(state)
    
    if state.next_action == "fail":
        logger.error("diff_analysis_failed", errors=state.errors)
        return state
    
    logger.info(
        "diff_analysis_complete",
        risk_score=state.diff_analysis.risk_score,
        risk_category=state.diff_analysis.risk_category,
        requires_approval=state.diff_analysis.requires_approval,
    )
    
    return state


def run_commit_phase(state: AgentState, config) -> AgentState:
    """Run git commit phase."""
    logger.info("phase_start", phase="commit")
    
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    
    committer = GitCommitAgent(github_client)
    state = committer.commit(state)
    
    if state.next_action == "fail":
        logger.error("commit_failed", errors=state.errors)
        return state
    
    logger.info(
        "commit_complete",
        branch=state.git_operation.branch_name,
        commit_sha=state.git_operation.commit_sha[:8],
    )
    
    return state


def run_pr_phase(state: AgentState, config) -> AgentState:
    """Run PR creation phase."""
    logger.info("phase_start", phase="pr_creation")
    
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
    
    state = pr_creator.create_pr(state)
    
    if state.next_action == "fail":
        logger.error("pr_creation_failed", errors=state.errors)
        return state
    
    logger.info(
        "pr_creation_complete",
        pr_number=state.git_operation.pr_number,
        pr_url=state.git_operation.pr_url,
    )
    
    return state


def run_monitor_phase(state: AgentState, config) -> AgentState:
    """Run workflow monitoring phase."""
    logger.info("phase_start", phase="monitoring")
    
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    
    monitor = MonitorAgent(
        github_client=github_client,
        poll_interval=10,
        max_wait_time=300,
    )
    
    state = monitor.monitor(state)
    
    if state.next_action == "fail":
        logger.error("monitoring_failed", errors=state.errors)
        return state
    
    logger.info(
        "monitoring_complete",
        run_id=state.workflow_run.run_id,
        conclusion=state.workflow_run.conclusion,
    )
    
    return state


def run_failure_detection_phase(state: AgentState, config) -> AgentState:
    """Run failure detection phase."""
    logger.info("phase_start", phase="failure_detection")
    
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    
    detector = FailureDetectorAgent(github_client)
    state = detector.detect(state)
    
    if state.next_action == "fail":
        logger.error("failure_detection_failed", errors=state.errors)
        return state
    
    logger.info(
        "failure_detection_complete",
        failure_count=len(state.failures),
        healable=state.next_action == "heal",
    )
    
    return state


def run_healing_phase(state: AgentState, config) -> AgentState:
    """Run healing phase."""
    logger.info("phase_start", phase="healing")
    
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
        max_attempts=config.get("safety", {}).get("max_healing_attempts", 3),
    )
    
    state = healer.heal(state)
    
    if state.next_action == "fail":
        logger.error("healing_failed", errors=state.errors)
        return state
    
    if state.next_action == "request_approval":
        logger.warning("healing_exhausted_or_not_applicable")
        return state
    
    logger.info(
        "healing_complete",
        attempt=state.current_healing_count,
        strategy=state.get_latest_healing_attempt().strategy if state.healing_attempts else None,
    )
    
    return state


def main():
    """Main execution function."""
    args = parse_args()
    
    # Load configuration
    try:
        config = get_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Please create a config.yaml file (see config.example.yaml)", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Configure logging
    configure_logging(debug=args.debug or config.development_mode)
    
    logger.info(
        "orchestrator_started",
        repo=args.repo,
        branch=args.branch,
        mode=args.mode,
        dry_run=args.dry_run,
    )
    
    # Parse repository
    try:
        owner, name = args.repo.split("/")
    except ValueError:
        logger.error("invalid_repo_format", repo=args.repo)
        print("Error: Repository must be in format owner/name", file=sys.stderr)
        sys.exit(1)
    
    # Initialize state
    state = AgentState(
        repo_owner=owner,
        repo_name=name,
        repo_branch=args.branch,
        trigger_type="manual",
    )
    
    try:
        # Phase 1: Detection
        state = run_detection_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="detection")
            sys.exit(1)
        
        if args.mode == "detect-only":
            print("\n=== Repository Detection Results ===")
            print(f"Language: {state.repo_metadata.language}")
            print(f"Package Manager: {state.repo_metadata.package_manager}")
            print(f"Build Tool: {state.repo_metadata.build_tool}")
            print(f"Has Tests: {state.repo_metadata.has_tests}")
            print(f"Has Linter: {state.repo_metadata.has_linter}")
            if state.repo_metadata.custom_commands:
                print(f"Custom Commands: {list(state.repo_metadata.custom_commands.keys())}")
            return
        
        # Phase 2: Generation
        state = run_generation_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="generation")
            sys.exit(1)
        
        # Phase 3: Validation
        state = run_validation_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="validation")
            sys.exit(1)
        
        if args.mode == "generate-only" or args.dry_run:
            print("\n=== Generated Workflow ===")
            print(state.workflow_content.content)
            print("\n=== Validation Results ===")
            print(f"Valid: {state.validation_result.is_valid}")
            if state.validation_result.warnings:
                print(f"Warnings: {len(state.validation_result.warnings)}")
                for warning in state.validation_result.warnings:
                    print(f"  - {warning}")
            return
        
        # Phase 4: Diff Analysis
        state = run_diff_analysis_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="diff_analysis")
            sys.exit(1)
        
        # Phase 5: Commit
        state = run_commit_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="commit")
            sys.exit(1)
        
        print("\n✓ Workflow committed successfully")
        print(f"  Branch: {state.git_operation.branch_name}")
        print(f"  Commit: {state.git_operation.commit_sha[:8]}")
        print(f"  Risk Level: {state.diff_analysis.risk_category.upper()}")
        
        if args.no_pr:
            logger.info("orchestration_complete", status="success", mode="no_pr")
            print("\nWorkflow committed to branch (no PR created)")
            print(f"  View at: https://github.com/{args.repo}/tree/{state.git_operation.branch_name}")
            return
        
        # Phase 6: Create PR
        state = run_pr_phase(state, config)
        
        if state.next_action == "fail":
            logger.error("orchestration_failed", phase="pr_creation")
            sys.exit(1)
        
        # Success!
        logger.info("orchestration_complete", status="success")
        print("\n✓ Pull request created successfully!")
        print(f"  PR #{state.git_operation.pr_number}")
        print(f"  URL: {state.git_operation.pr_url}")
        print(f"  Branch: {state.git_operation.branch_name}")
        print(f"  Confidence: {state.workflow_content.confidence:.2%}")
        print(f"  Risk Level: {state.diff_analysis.risk_category.upper()}")
        
        # Phase 7: Monitor (optional)
        if args.monitor:
            print("\n⏳ Monitoring workflow execution...")
            state = run_monitor_phase(state, config)
            
            if state.next_action == "fail":
                logger.error("orchestration_failed", phase="monitoring")
                sys.exit(1)
            
            print(f"\n✓ Workflow execution completed")
            print(f"  Run #{state.workflow_run.run_number}")
            print(f"  Status: {state.workflow_run.conclusion.upper()}")
            print(f"  URL: {state.workflow_run.html_url}")
            
            # Phase 8: Failure Detection (if failed)
            if state.workflow_run.conclusion == "failure":
                print("\n🔍 Analyzing failure...")
                state = run_failure_detection_phase(state, config)
                
                if state.next_action == "fail":
                    logger.error("orchestration_failed", phase="failure_detection")
                    sys.exit(1)
                
                print(f"\n⚠️  Detected {len(state.failures)} failure(s):")
                for i, failure in enumerate(state.failures, 1):
                    print(f"\n  {i}. {failure.step_name} ({failure.failure_type})")
                    print(f"     Error: {failure.error_message}")
                    print(f"     Root Cause: {failure.root_cause}")
                    print(f"     Confidence: {failure.confidence:.0%}")
                
                # Phase 9: Healing (if healable and not disabled)
                if state.next_action == "heal" and not args.no_heal:
                    print("\n🔧 Attempting to heal failure...")
                    state = run_healing_phase(state, config)
                    
                    if state.next_action == "fail":
                        logger.error("orchestration_failed", phase="healing")
                        sys.exit(1)
                    
                    if state.next_action == "request_approval":
                        print("\n🤔 Healing not applicable or exhausted - manual investigation required")
                    elif state.next_action == "monitor":
                        attempt = state.get_latest_healing_attempt()
                        print(f"\n✓ Healing patch applied!")
                        print(f"  Strategy: {attempt.strategy}")
                        print(f"  Confidence: {attempt.confidence:.0%}")
                        print(f"  Attempt: #{attempt.attempt_number}")
                        
                        # Re-monitor the healed workflow
                        print("\n⏳ Monitoring healed workflow...")
                        state = run_monitor_phase(state, config)
                        
                        if state.next_action == "fail":
                            logger.error("orchestration_failed", phase="monitoring_heal")
                            sys.exit(1)
                        
                        print(f"\n✓ Healed workflow execution completed")
                        print(f"  Run #{state.workflow_run.run_number}")
                        print(f"  Status: {state.workflow_run.conclusion.upper()}")
                        print(f"  URL: {state.workflow_run.html_url}")
                        
                        # Check if healing succeeded
                        if state.workflow_run.conclusion == "success":
                            attempt.resulted_in_success = True
                            print("\n🎉 Healing successful! Workflow now passes.")
                        elif state.workflow_run.conclusion == "failure":
                            attempt.resulted_in_success = False
                            print("\n⚠️  Healing did not resolve the issue.")
                            
                            # Optionally retry healing
                            if state.should_continue_healing(3):
                                print(f"   Remaining attempts: {3 - state.current_healing_count}")
                            else:
                                print("   Max healing attempts reached.")
                
                elif state.next_action == "heal" and args.no_heal:
                    print("\n💡 Failure appears healable, but --no-heal flag is set")
                    print("   Remove --no-heal to enable automatic healing")
                else:
                    print("\n🤔 Failure requires manual investigation")
        else:
            print("\nNext steps:")
            print("  - Review the PR")
            print("  - Merge when ready")
            print("  - Use --monitor flag to track workflow execution")
        
    except KeyboardInterrupt:
        logger.info("orchestration_interrupted")
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        logger.exception("orchestration_error", error=str(e))
        print(f"\nError: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
