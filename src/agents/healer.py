"""
Healer Agent.

Generates patches to fix CI failures autonomously.
"""

import time
from typing import Optional, Dict, List
import structlog

from src.models.state import AgentState, HealingAttempt
from src.integrations.ollama_client import OllamaClient
from src.integrations.github_client import GitHubClient

logger = structlog.get_logger()


class HealerAgent:
    """Generates and applies patches to fix CI failures."""
    
    # Pre-defined healing strategies for common issues
    HEALING_STRATEGIES = {
        "gradle_permission": {
            "pattern": ["gradlew", "permission denied", "command not found"],
            "fix_type": "add_step",
            "confidence": 0.95,
        },
        "test_failure_gradle": {
            "pattern": ["test failed", "tests failed", "failures:", "assertion", "expected"],
            "fix_type": "skip_tests_temporarily",
            "confidence": 0.70,
        },
        "python_dependency": {
            "pattern": ["no module named", "cannot import", "modulenotfounderror"],
            "fix_type": "modify_dependencies",
            "confidence": 0.85,
        },
        "node_dependency": {
            "pattern": ["cannot find module", "error: cannot find package"],
            "fix_type": "modify_dependencies",
            "confidence": 0.85,
        },
        "java_version": {
            "pattern": ["unsupported class version", "invalid target release"],
            "fix_type": "adjust_java_version",
            "confidence": 0.90,
        },
    }
    
    def __init__(
        self,
        github_client: GitHubClient,
        ollama_client: OllamaClient,
        model: str = "llama3:70b",
        max_attempts: int = 3,
    ):
        """
        Initialize healer agent.
        
        Args:
            github_client: GitHub API client
            ollama_client: Ollama client for patch generation
            model: Model to use for reasoning
            max_attempts: Maximum healing attempts
        """
        self.github_client = github_client
        self.ollama_client = ollama_client
        self.model = model
        self.max_attempts = max_attempts
    
    def heal(self, state: AgentState) -> AgentState:
        """
        Attempt to heal CI failures.
        
        Args:
            state: Current state with failures detected
        
        Returns:
            Updated state with healing attempt
        """
        if not state.failures:
            state.add_error("No failures to heal")
            state.next_action = "fail"
            return state
        
        if not state.should_continue_healing(self.max_attempts):
            state.add_error(f"Max healing attempts ({self.max_attempts}) reached")
            state.next_action = "request_approval"
            return state
        
        logger.info(
            "starting_heal",
            repo=f"{state.repo_owner}/{state.repo_name}",
            attempt=state.current_healing_count + 1,
            failures=len(state.failures),
        )
        
        start_time = time.time()
        
        try:
            # Fetch detailed logs for better analysis
            failure = state.failures[0]  # Heal first failure
            detailed_logs = self._fetch_failure_logs(failure, state)
            
            # Enrich failure with detailed logs
            if detailed_logs:
                failure.log_excerpt = detailed_logs[:2000]  # Limit to 2000 chars
            
            # Analyze failure and determine strategy
            strategy = self._determine_strategy(failure, state)
            
            if not strategy:
                logger.warning("no_healing_strategy", failure_type=failure.failure_type)
                # Try LLM-based healing as fallback
                logger.info("attempting_llm_healing")
                strategy = {
                    "name": "llm_analysis",
                    "fix_type": "llm_patch",
                    "confidence": 0.60,
                }
                if not strategy:
                    state.next_action = "request_approval"
                    return state
            
            # Generate patch
            patch = self._generate_patch(failure, strategy, state)
            
            if not patch:
                logger.warning("patch_generation_failed")
                state.next_action = "request_approval"
                return state
            
            # Create healing attempt record
            attempt = HealingAttempt(
                attempt_number=state.current_healing_count + 1,
                strategy=strategy["name"],
                patch_content=patch["content"],
                files_modified=patch["files"],
                confidence=patch["confidence"],
                sandbox_validated=False,  # Phase 4 doesn't include sandbox yet
            )
            
            state.healing_attempts.append(attempt)
            state.current_healing_count += 1
            
            # Apply the patch
            applied = self._apply_patch(patch, state)
            attempt.applied = applied
            
            if not applied:
                logger.error("patch_application_failed")
                state.next_action = "request_approval"
                return state
            
            duration = time.time() - start_time
            state.add_agent_record(
                agent_name="Healer",
                action="heal",
                result=f"Applied {strategy['name']} strategy",
                duration=duration,
            )
            
            # Monitor the fix
            state.next_action = "monitor"
            
            logger.info(
                "healing_complete",
                strategy=strategy["name"],
                confidence=patch["confidence"],
                duration=duration,
            )
            
            return state
            
        except Exception as e:
            error_msg = f"Healing failed: {str(e)}"
            logger.error("healing_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "request_approval"
            return state
    
    def _fetch_failure_logs(self, failure, state: AgentState) -> Optional[str]:
        """Fetch detailed logs from the failed workflow run."""
        try:
            if not state.workflow_run or not state.workflow_run.run_id:
                return None
            
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            run_id = state.workflow_run.run_id
            
            # Try to get workflow run logs
            logs = self.github_client.get_workflow_run_logs(repo, run_id)
            
            if logs:
                # Extract relevant failure information
                log_lines = logs.split('\n')
                # Get last 100 lines which usually contain error information
                relevant_logs = '\n'.join(log_lines[-100:])
                logger.info("fetched_logs", length=len(relevant_logs))
                return relevant_logs
            
            # Fallback: try to get workflow run details
            run = self.github_client.get_workflow_run(repo, run_id)
            if run:
                log_text = f"Workflow Run #{run_id}\n"
                log_text += f"Status: {run.get('status', 'unknown')}\n"
                log_text += f"Conclusion: {run.get('conclusion', 'unknown')}\n"
                return log_text
            
            return None
            
        except Exception as e:
            logger.warning("log_fetch_failed", error=str(e))
            return None
    
    def _determine_strategy(self, failure, state: AgentState) -> Optional[Dict]:
        """
        Determine the best healing strategy for a failure.
        
        Args:
            failure: FailureInfo object
            state: Current state
        
        Returns:
            Strategy dict or None
        """
        error_text = f"{failure.step_name} {failure.error_message} {failure.log_excerpt}".lower()
        
        # Check predefined strategies
        for strategy_name, strategy_def in self.HEALING_STRATEGIES.items():
            for pattern in strategy_def["pattern"]:
                if pattern.lower() in error_text:
                    logger.info(
                        "strategy_matched",
                        strategy=strategy_name,
                        confidence=strategy_def["confidence"],
                    )
                    return {
                        "name": strategy_name,
                        "fix_type": strategy_def["fix_type"],
                        "confidence": strategy_def["confidence"],
                    }
        
        # For build_error, check if it's Gradle-related
        if failure.failure_type == "build_error":
            if any(word in error_text for word in ["gradlew", "gradle"]):
                return {
                    "name": "gradle_permission",
                    "fix_type": "add_step",
                    "confidence": 0.90,
                }
        
        # For test_failure, use test healing strategy
        if failure.failure_type == "test_failure":
            return {
                "name": "test_failure_gradle",
                "fix_type": "skip_tests_temporarily",
                "confidence": 0.70,
            }
        
        # No clear strategy
        return None
    
    def _generate_patch(self, failure, strategy: Dict, state: AgentState) -> Optional[Dict]:
        """
        Generate a patch to fix the failure.
        
        Args:
            failure: FailureInfo object
            strategy: Healing strategy
            state: Current state
        
        Returns:
            Patch dict with content, files, and confidence
        """
        # For common issues, use predefined patches
        if strategy["name"] == "gradle_permission":
            return self._generate_gradle_permission_fix(state)
        
        elif strategy["name"] == "test_failure_gradle":
            return self._generate_test_failure_fix(failure, state)
        
        elif strategy["name"] == "java_version":
            return self._generate_java_version_fix(failure, state)
        
        elif strategy["name"] == "llm_analysis":
            # Use LLM for complex analysis
            return self._generate_llm_patch(failure, strategy, state)
        
        # For complex issues, use LLM
        return self._generate_llm_patch(failure, strategy, state)
    
    def _generate_gradle_permission_fix(self, state: AgentState) -> Dict:
        """Generate fix for Gradle wrapper permission issue."""
        workflow_content = state.workflow_content.content
        
        # Find where to insert the chmod step (before first gradlew usage)
        lines = workflow_content.split('\n')
        new_lines = []
        inserted = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for a step that contains gradlew
            if not inserted and '- name:' in line and i + 1 < len(lines):
                # Check if next line(s) contain gradlew
                for j in range(i + 1, min(i + 5, len(lines))):
                    if './gradlew' in lines[j]:
                        # Found it! Insert chmod step before this step
                        step_indent = len(line) - len(line.lstrip())
                        new_lines.append(' ' * step_indent + '- name: Make gradlew executable')
                        new_lines.append(' ' * step_indent + '  run: chmod +x gradlew')
                        inserted = True
                        break
            
            new_lines.append(line)
            i += 1
        
        new_content = '\n'.join(new_lines)
        
        return {
            "content": new_content,
            "files": [state.workflow_content.path],
            "confidence": 0.95,
            "description": "Add chmod +x gradlew before running tests",
        }
    
    def _generate_test_failure_fix(self, failure, state: AgentState) -> Dict:
        """Generate fix for test failures by analyzing logs with LLM."""
        
        # If we have detailed logs, use LLM to generate a proper fix
        if failure.log_excerpt and len(failure.log_excerpt) > 50:
            logger.info("using_llm_for_test_fix", log_length=len(failure.log_excerpt))
            llm_patch = self._generate_llm_patch(failure, {"name": "test_failure", "confidence": 0.70}, state)
            if llm_patch:
                return llm_patch
        
        # Fallback to simple workflow fix
        workflow_content = state.workflow_content.content
        lines = workflow_content.split('\n')
        new_lines = []
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            # Find the test step and add continue-on-error or proper test command
            if '- name:' in line and ('test' in line.lower() or 'run tests' in line.lower()):
                # Check if next lines contain the run command
                if i + 1 < len(lines) and 'run:' in lines[i + 1]:
                    run_line = lines[i + 1]
                    indent = len(run_line) - len(run_line.lstrip())
                    
                    # If it's gradlew test, make sure it uses proper flags
                    if './gradlew' in run_line and 'test' in run_line:
                        # Add --continue flag to show all failures
                        if '--continue' not in run_line:
                            new_lines[len(new_lines)-1] = run_line.replace('test', 'test --continue --no-daemon')
                            i += 1
                            continue
        
        new_content = '\n'.join(new_lines)
        
        return {
            "content": new_content,
            "files": [state.workflow_content.path],
            "confidence": 0.75,
            "description": "Add proper test flags to show all failures and continue on error",
        }
    
    def _generate_java_version_fix(self, failure, state: AgentState) -> Dict:
        """Generate fix for Java version incompatibility."""
        workflow_content = state.workflow_content.content
        
        # Adjust Java version in matrix or setup-java step
        # For now, use a simple fix: change to Java 17 (most compatible)
        new_content = workflow_content.replace("java-version: '11'", "java-version: '17'")
        new_content = new_content.replace("java-version: '21'", "java-version: '17'")
        
        return {
            "content": new_content,
            "files": [state.workflow_content.path],
            "confidence": 0.85,
            "description": "Adjust Java version to 17 for compatibility",
        }
    
    def _generate_llm_patch(self, failure, strategy: Dict, state: AgentState) -> Optional[Dict]:
        """Generate patch using LLM for complex issues."""
        try:
            system_prompt = """You are an expert at fixing GitHub Actions workflows and test failures.
Analyze the failure carefully and generate a complete fixed YAML workflow.

Key considerations:
1. For test failures: Check if the issue is in the workflow setup (missing dependencies, wrong commands, permissions)
2. For Java/Gradle: Ensure gradlew has execute permissions (chmod +x gradlew)
3. For build errors: Check Java version, Gradle version, dependencies
4. Preserve all existing jobs and structure
5. Only modify what's necessary to fix the failure

Output ONLY the complete fixed YAML workflow, no explanations or markdown fences."""
            
            # Build comprehensive failure context
            failure_context = f"""Failure Analysis:
- Type: {failure.failure_type}
- Job: {failure.job_name}
- Step: {failure.step_name}
- Error: {failure.error_message}"""
            
            if failure.root_cause:
                failure_context += f"\n- Root Cause: {failure.root_cause}"
            
            if failure.log_excerpt:
                failure_context += f"\n\nDetailed Logs:\n{failure.log_excerpt[:1500]}"
            
            user_prompt = f"""Fix this GitHub Actions workflow failure:

{failure_context}

Repository: {state.repo_owner}/{state.repo_name}
Previous Healing Attempts: {state.current_healing_count}

Current Workflow:
```yaml
{state.workflow_content.content}
```

Analyze the failure and generate the complete fixed YAML workflow.
Focus on fixing the root cause, not just symptoms."""
            
            logger.info("generating_llm_patch", failure_type=failure.failure_type, 
                       attempt=state.current_healing_count + 1)
            
            response = self.ollama_client.generate(
                model=self.model,
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.1,
            )
            
            # Extract YAML from response
            content = response.content.strip()
            if '```yaml' in content:
                content = content.split('```yaml')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            logger.info("llm_patch_generated", length=len(content), confidence=0.70)
            
            return {
                "content": content,
                "files": [state.workflow_content.path],
                "confidence": 0.70,  # Lower confidence for LLM patches
                "description": f"LLM-generated fix for {failure.failure_type} in {failure.step_name}",
            }
            
        except Exception as e:
            logger.error("llm_patch_failed", error=str(e))
            return None
    
    def _apply_patch(self, patch: Dict, state: AgentState) -> bool:
        """
        Apply the patch by committing to the PR branch.
        
        Args:
            patch: Patch dict with content and files
            state: Current state with git_operation
        
        Returns:
            True if successful, False otherwise
        """
        if not state.git_operation or not state.git_operation.branch_name:
            logger.error("no_branch_to_apply_patch")
            return False
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            
            # Commit the patched workflow
            commit_message = f"fix: {patch['description']}\n\nGenerated by Agentic CI Orchestrator - Healing attempt #{state.current_healing_count}"
            
            commit_sha = self.github_client.commit_file(
                repo=repo,
                path=patch["files"][0],
                content=patch["content"],
                message=commit_message,
                branch=state.git_operation.branch_name,
            )
            
            logger.info(
                "patch_applied",
                commit_sha=commit_sha[:8],
                files=len(patch["files"]),
            )
            
            return True
            
        except Exception as e:
            logger.error("patch_application_failed", error=str(e))
            return False
