"""
Phase 4 Test - Healing.

Tests the healing agent on a real failing workflow (Gradle permission issue).
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import get_config
from src.logging_config import configure_logging
from src.models.state import AgentState, FailureInfo, WorkflowRun, GitOperation, WorkflowContent
from src.integrations import get_ollama_client, get_github_client
from src.agents.healer import HealerAgent


def test_phase4_healing():
    """Test Phase 4 healing on Gradle permission failure."""
    configure_logging(debug=True)
    config = get_config()
    
    owner = "kushald17"
    name = "my-project"
    branch = "agent/ci-20251127-084520"  # Branch from previous test
    
    print(f"\n{'='*60}")
    print(f"Testing Phase 4 Healing on {owner}/{name}")
    print(f"Branch: {branch}")
    print(f"{'='*60}\n")
    
    # Initialize state with simulated failure
    state = AgentState(
        repo_owner=owner,
        repo_name=name,
        repo_branch=branch,
        trigger_type="manual",
    )
    
    # Simulate workflow content (the problematic workflow)
    state.workflow_content = WorkflowContent(
        content="""name: CI - my-project
'on':
  push:
    branches:
    - main
  pull_request:
    branches:
    - main
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    - name: Set up JDK
      uses: actions/setup-java@v4
      with:
        java-version: '17'
        distribution: temurin
    - name: Cache Gradle packages
      uses: actions/cache@v4
      with:
        path: ~/.gradle/caches
        key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') }}
        restore-keys: ${{ runner.os }}-gradle-
    - name: Run tests
      run: ./gradlew test
    - name: Build with Gradle
      run: ./gradlew build
    strategy:
      matrix:
        java-version:
        - '11'
        - '17'
        - '21'
""",
        path=".github/workflows/ci.yml",
        generator_model="template",
        confidence=0.95,
    )
    
    # Simulate git operation
    state.git_operation = GitOperation(
        branch_name=branch,
        commit_sha="9b98c075",
        commit_message="Initial workflow",
        pr_number=6,
        pr_url=f"https://github.com/{owner}/{name}/pull/6",
        pr_status="open",
    )
    
    # Simulate workflow run failure
    state.workflow_run = WorkflowRun(
        run_id=19730342133,
        run_number=18,
        status="completed",
        conclusion="failure",
        html_url=f"https://github.com/{owner}/{name}/actions/runs/19730342133",
    )
    
    # Simulate detected failure (Gradle permission issue)
    failure = FailureInfo(
        job_name="ci",
        step_name="Run tests",
        error_message="./gradlew: Permission denied",
        log_excerpt="bash: ./gradlew: Permission denied",
        failure_type="build_error",
        confidence=0.90,
        root_cause="Gradle wrapper not executable",
    )
    state.failures = [failure]
    state.next_action = "heal"
    
    print("Simulated Failure:")
    print(f"  Step: {failure.step_name}")
    print(f"  Type: {failure.failure_type}")
    print(f"  Error: {failure.error_message}")
    print(f"  Root Cause: {failure.root_cause}")
    
    # Phase 9: Healing
    print("\nPhase 9: Healing...")
    
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
        max_attempts=3,
    )
    
    state = healer.heal(state)
    
    if state.next_action == "fail":
        print(f"❌ Healing failed: {state.errors}")
        return False
    
    if state.next_action == "request_approval":
        print(f"⚠️  Healing not applicable")
        return False
    
    # Check healing attempt
    attempt = state.get_latest_healing_attempt()
    
    print(f"\n✓ Healing patch generated!")
    print(f"  Strategy: {attempt.strategy}")
    print(f"  Confidence: {attempt.confidence:.0%}")
    print(f"  Files Modified: {len(attempt.files_modified)}")
    print(f"  Applied: {attempt.applied}")
    
    # Show the patch
    print(f"\n  Patch Preview:")
    lines = attempt.patch_content.split('\n')
    for line in lines[15:35]:  # Show relevant section
        print(f"    {line}")
    
    # Verify the fix is in the patch
    if "chmod +x gradlew" in attempt.patch_content:
        print(f"\n✓ Patch contains expected fix (chmod +x gradlew)")
    else:
        print(f"\n⚠️  Patch may not contain expected fix")
    
    # Summary
    print(f"\n{'='*60}")
    print("Phase 4 Test: SUCCESS ✓")
    print(f"{'='*60}")
    print(f"\nHealing Attempt: #{attempt.attempt_number}")
    print(f"Strategy: {attempt.strategy}")
    print(f"Patch Applied: {attempt.applied}")
    print(f"Next Action: {state.next_action}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_phase4_healing()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
