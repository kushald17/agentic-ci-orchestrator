"""
Phase 3 Test - Monitoring and Failure Detection.

Tests:
1. Full pipeline with PR creation
2. Workflow monitoring
3. Failure detection and classification
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import get_config
from src.logging_config import configure_logging
from src.models.state import AgentState
from src.integrations import get_ollama_client, get_github_client
from src.agents import RepositoryDetectorAgent, WorkflowGeneratorAgent, YAMLValidatorAgent
from src.agents.diff_analyzer import DiffAnalyzerAgent
from src.agents.git_commit import GitCommitAgent
from src.agents.pr_creator import PRCreatorAgent
from src.agents.monitor import MonitorAgent
from src.agents.failure_detector import FailureDetectorAgent


def test_phase3_monitoring():
    """Test Phase 3 monitoring on a repository with existing PR/workflow."""
    configure_logging(debug=True)
    config = get_config()
    
    # Use my-project which has a failing workflow
    owner = "kushald17"
    name = "my-project"
    branch = "agent/ci-20251127-072708"  # Branch from Phase 2 test
    
    print(f"\n{'='*60}")
    print(f"Testing Phase 3 Monitoring on {owner}/{name}")
    print(f"Branch: {branch}")
    print(f"{'='*60}\n")
    
    # Initialize state with existing branch
    state = AgentState(
        repo_owner=owner,
        repo_name=name,
        repo_branch=branch,
        trigger_type="manual",
    )
    
    # We need git_operation to monitor
    from src.models.state import GitOperation
    state.git_operation = GitOperation(
        branch_name=branch,
        commit_sha="8940cf52",
        commit_message="Test commit",
        pr_number=5,
        pr_url=f"https://github.com/{owner}/{name}/pull/5",
        pr_status="open",
    )
    
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    
    # Phase 7: Monitor
    print("Phase 7: Monitoring workflow...")
    monitor = MonitorAgent(
        github_client=github_client,
        poll_interval=5,
        max_wait_time=180,
    )
    
    state = monitor.monitor(state)
    
    if state.next_action == "fail":
        print(f"❌ Monitoring failed: {state.errors}")
        return False
    
    print(f"✓ Workflow monitored")
    print(f"  Run ID: {state.workflow_run.run_id}")
    print(f"  Run Number: #{state.workflow_run.run_number}")
    print(f"  Status: {state.workflow_run.status}")
    print(f"  Conclusion: {state.workflow_run.conclusion}")
    print(f"  URL: {state.workflow_run.html_url}")
    
    # Phase 8: Failure Detection (if failed)
    if state.workflow_run.conclusion == "failure":
        print("\nPhase 8: Failure Detection...")
        detector = FailureDetectorAgent(github_client)
        state = detector.detect(state)
        
        if state.next_action == "fail":
            print(f"❌ Failure detection failed: {state.errors}")
            return False
        
        print(f"✓ Failures detected: {len(state.failures)}")
        
        for i, failure in enumerate(state.failures, 1):
            print(f"\n  Failure #{i}:")
            print(f"    Job: {failure.job_name}")
            print(f"    Step: {failure.step_name}")
            print(f"    Type: {failure.failure_type}")
            print(f"    Error: {failure.error_message}")
            print(f"    Root Cause: {failure.root_cause}")
            print(f"    Confidence: {failure.confidence:.0%}")
        
        print(f"\n  Next Action: {state.next_action}")
        
        if state.next_action == "heal":
            print("  💡 Failure appears healable!")
        else:
            print("  🤔 Requires manual investigation")
    
    elif state.workflow_run.conclusion == "success":
        print("\n✓ Workflow succeeded - no failures to detect")
    
    # Summary
    print(f"\n{'='*60}")
    print("Phase 3 Test: SUCCESS ✓")
    print(f"{'='*60}")
    print(f"\nWorkflow Run: {state.workflow_run.html_url}")
    print(f"Conclusion: {state.workflow_run.conclusion}")
    if state.failures:
        print(f"Failures Detected: {len(state.failures)}")
        print(f"Healable: {state.next_action == 'heal'}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_phase3_monitoring()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
