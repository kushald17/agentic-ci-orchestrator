"""
Phase 2 Test - Full pipeline with PR creation.

Tests:
1. Detection
2. Generation
3. Validation
4. Diff Analysis
5. Git Commit
6. PR Creation
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


def test_phase2():
    """Test Phase 2 functionality."""
    configure_logging(debug=True)
    config = get_config()
    
    # Use a small test repository (adjust as needed)
    # For demo purposes, using the Git-demo repo
    owner = "kushald17"
    name = "Git-demo"
    branch = "main"
    
    print(f"\n{'='*60}")
    print(f"Testing Phase 2 on {owner}/{name}")
    print(f"{'='*60}\n")
    
    # Initialize state
    state = AgentState(
        repo_owner=owner,
        repo_name=name,
        repo_branch=branch,
        trigger_type="manual",
    )
    
    # Phase 1: Detection
    print("Phase 1: Detection...")
    github_client = get_github_client(
        token=config.github_token,
        api_url=config.github_api_url,
    )
    detector = RepositoryDetectorAgent(github_client)
    state = detector.detect(state)
    
    if state.next_action == "fail":
        print(f"❌ Detection failed: {state.errors}")
        return False
    
    print(f"✓ Detected: {state.repo_metadata.language}")
    print(f"  Package Manager: {state.repo_metadata.package_manager}")
    print(f"  Has Tests: {state.repo_metadata.has_tests}")
    
    # Phase 2: Generation
    print("\nPhase 2: Generation...")
    ollama_client = get_ollama_client(
        base_url=config.ollama_base_url,
        timeout=config.ollama_timeout,
    )
    
    if not ollama_client.health_check():
        print("❌ Ollama not available")
        return False
    
    generator = WorkflowGeneratorAgent(
        ollama_client=ollama_client,
        model=config.ollama_reasoning_model,
    )
    state = generator.generate(state)
    
    if state.next_action == "fail":
        print(f"❌ Generation failed: {state.errors}")
        return False
    
    print(f"✓ Generated workflow: {len(state.workflow_content.content)} bytes")
    print(f"  Confidence: {state.workflow_content.confidence:.2%}")
    
    # Phase 3: Validation
    print("\nPhase 3: Validation...")
    validator = YAMLValidatorAgent(config.get_all())
    state = validator.validate(state)
    
    if not state.validation_result.is_valid:
        print(f"❌ Validation failed: {state.validation_result.errors}")
        return False
    
    print(f"✓ Validation passed")
    if state.validation_result.warnings:
        print(f"  Warnings: {len(state.validation_result.warnings)}")
    
    # Phase 4: Diff Analysis
    print("\nPhase 4: Diff Analysis...")
    analyzer = DiffAnalyzerAgent(config.get_all())
    state = analyzer.analyze(state)
    
    if state.next_action == "fail":
        print(f"❌ Diff analysis failed: {state.errors}")
        return False
    
    print(f"✓ Risk analysis complete")
    print(f"  Risk Score: {state.diff_analysis.risk_score:.2f}")
    print(f"  Risk Category: {state.diff_analysis.risk_category}")
    print(f"  Requires Approval: {state.diff_analysis.requires_approval}")
    
    # Phase 5: Commit
    print("\nPhase 5: Git Commit...")
    committer = GitCommitAgent(github_client)
    state = committer.commit(state)
    
    if state.next_action == "fail":
        print(f"❌ Commit failed: {state.errors}")
        return False
    
    print(f"✓ Committed to branch")
    print(f"  Branch: {state.git_operation.branch_name}")
    print(f"  Commit SHA: {state.git_operation.commit_sha[:8]}")
    
    # Phase 6: PR Creation
    print("\nPhase 6: PR Creation...")
    pr_creator = PRCreatorAgent(
        github_client=github_client,
        ollama_client=ollama_client,
        model=config.ollama_lightweight_model,
    )
    state = pr_creator.create_pr(state)
    
    if state.next_action == "fail":
        print(f"❌ PR creation failed: {state.errors}")
        return False
    
    print(f"✓ Pull request created!")
    print(f"  PR Number: #{state.git_operation.pr_number}")
    print(f"  URL: {state.git_operation.pr_url}")
    print(f"  Status: {state.git_operation.pr_status}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Phase 2 Test: SUCCESS ✓")
    print(f"{'='*60}")
    print(f"\nPR: {state.git_operation.pr_url}")
    print(f"Branch: {state.git_operation.branch_name}")
    print(f"Confidence: {state.workflow_content.confidence:.2%}")
    print(f"Risk: {state.diff_analysis.risk_category.upper()}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_phase2()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
