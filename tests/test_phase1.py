"""
Simple test script to verify Phase 1 functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import get_config
from src.logging_config import configure_logging
from src.models.state import AgentState, RepositoryMetadata
from src.templates import get_template


def test_templates():
    """Test workflow template generation."""
    print("Testing workflow templates...")
    
    # Test Python template
    python_template = get_template("python", python_version="3.11", use_poetry=False)
    python_workflow = python_template.generate(repo_name="test-python", branch="main")
    print(f"✓ Python template: {len(python_workflow)} bytes")
    
    # Test Node template
    node_template = get_template("node", use_yarn=True)
    node_workflow = node_template.generate(repo_name="test-node", branch="main")
    print(f"✓ Node template: {len(node_workflow)} bytes")
    
    # Test Java template
    java_template = get_template("java", use_gradle=True)
    java_workflow = java_template.generate(repo_name="test-java", branch="main")
    print(f"✓ Java template: {len(java_workflow)} bytes")
    
    print("All template tests passed!\n")


def test_state():
    """Test state management."""
    print("Testing state management...")
    
    state = AgentState(
        repo_owner="test",
        repo_name="repo",
        repo_branch="main",
    )
    
    # Add some data
    state.repo_metadata = RepositoryMetadata(
        owner="test",
        name="repo",
        branch="main",
        full_name="test/repo",
        language="python",
        has_tests=True,
    )
    
    state.add_agent_record(
        agent_name="TestAgent",
        action="test",
        result="success",
        duration=1.5,
    )
    
    state.add_error("Test error")
    
    print(f"✓ State created: {state.run_id}")
    print(f"✓ Agent history: {len(state.agent_history)} records")
    print(f"✓ Errors: {len(state.errors)}")
    print("State management tests passed!\n")


def test_config():
    """Test configuration loading."""
    print("Testing configuration...")
    
    try:
        config = get_config()
        print(f"✓ Config loaded")
        print(f"✓ Ollama URL: {config.ollama_base_url}")
        print(f"✓ Reasoning model: {config.ollama_reasoning_model}")
        print(f"✓ GitHub API: {config.github_api_url}")
        print(f"✓ Max healing attempts: {config.max_healing_attempts}")
        print("Configuration tests passed!\n")
    except FileNotFoundError:
        print("✗ Config file not found")
        print("  Run: cp config.example.yaml config.yaml")
        return False
    except ValueError as e:
        print(f"✗ Config error: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 1 Component Tests")
    print("=" * 60 + "\n")
    
    # Configure logging
    configure_logging(debug=False)
    
    # Run tests
    test_templates()
    test_state()
    
    config_ok = test_config()
    
    print("=" * 60)
    if config_ok:
        print("✓ All tests passed!")
        print("\nReady to run Phase 1:")
        print("  python src/main.py --repo octocat/Hello-World --mode detect-only")
    else:
        print("✗ Some tests failed - see above for details")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
