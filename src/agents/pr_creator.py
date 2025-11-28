"""
PR Creator Agent.

Creates pull requests with AI-generated descriptions.
"""

import time
import structlog

from src.models.state import AgentState
from src.integrations.github_client import GitHubClient
from src.integrations.ollama_client import OllamaClient

logger = structlog.get_logger()


class PRCreatorAgent:
    """Creates pull requests with descriptions."""
    
    def __init__(
        self,
        github_client: GitHubClient,
        ollama_client: OllamaClient,
        model: str = "llama3:13b",
    ):
        """
        Initialize PR creator.
        
        Args:
            github_client: GitHub API client
            ollama_client: Ollama client for description generation
            model: Model to use for description (lightweight is fine)
        """
        self.github_client = github_client
        self.ollama_client = ollama_client
        self.model = model
    
    def create_pr(self, state: AgentState) -> AgentState:
        """
        Create pull request.
        
        Args:
            state: Current state with git_operation
        
        Returns:
            Updated state with PR information
        """
        if not state.git_operation:
            state.add_error("Cannot create PR without git operation")
            state.next_action = "fail"
            return state
        
        logger.info(
            "creating_pr",
            repo=f"{state.repo_owner}/{state.repo_name}",
            branch=state.git_operation.branch_name,
        )
        
        start_time = time.time()
        
        try:
            repo = self.github_client.get_repository(state.repo_owner, state.repo_name)
            
            # Generate PR title and description
            title = self._generate_pr_title(state)
            description = self._generate_pr_description(state)
            
            # Create pull request
            logger.info("opening_pr", title=title)
            pr = self.github_client.create_pull_request(
                repo=repo,
                title=title,
                body=description,
                head=state.git_operation.branch_name,
                base=state.repo_branch,
            )
            
            # Update git operation with PR info
            state.git_operation.pr_number = pr.number
            state.git_operation.pr_url = pr.html_url
            state.git_operation.pr_status = "open"
            
            state.next_action = "complete"
            
            duration = time.time() - start_time
            state.add_agent_record(
                agent_name="PRCreator",
                action="create_pr",
                result=f"PR #{pr.number}: {pr.html_url}",
                duration=duration,
            )
            
            logger.info(
                "pr_created",
                pr_number=pr.number,
                pr_url=pr.html_url,
                duration=duration,
            )
            
            return state
            
        except Exception as e:
            error_msg = f"PR creation failed: {str(e)}"
            logger.error("pr_creation_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    def _generate_pr_title(self, state: AgentState) -> str:
        """Generate concise PR title."""
        language = state.repo_metadata.language if state.repo_metadata else "project"
        return f"Add CI workflow for {language}"
    
    def _generate_pr_description(self, state: AgentState) -> str:
        """
        Generate comprehensive PR description using LLM.
        
        Falls back to template if LLM fails.
        """
        try:
            # Try LLM-generated description
            return self._generate_llm_description(state)
        except Exception as e:
            logger.warning("llm_pr_description_failed", error=str(e))
            # Fallback to template
            return self._generate_template_description(state)
    
    def _generate_llm_description(self, state: AgentState) -> str:
        """Generate description using Ollama."""
        system_prompt = """You are a technical writer creating a pull request description for a CI workflow.
Write a clear, professional description that explains what the workflow does and why it's beneficial.
Keep it concise (3-5 paragraphs). Use markdown formatting."""
        
        user_prompt = f"""Generate a pull request description for this CI workflow:

Repository: {state.repo_owner}/{state.repo_name}
Language: {state.repo_metadata.language if state.repo_metadata else 'unknown'}
Package Manager: {state.repo_metadata.package_manager if state.repo_metadata else 'unknown'}
Has Tests: {state.repo_metadata.has_tests if state.repo_metadata else False}
Has Linter: {state.repo_metadata.has_linter if state.repo_metadata else False}

Workflow includes:
- Automated linting
- Test execution
- Build process
- Matrix builds across multiple versions

Write a PR description explaining this automated CI workflow."""
        
        response = self.ollama_client.generate(
            model=self.model,
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3,
        )
        
        return response.content.strip()
    
    def _generate_template_description(self, state: AgentState) -> str:
        """Generate description from template."""
        language = state.repo_metadata.language if state.repo_metadata else "unknown"
        pm = state.repo_metadata.package_manager if state.repo_metadata else "N/A"
        
        description_parts = [
            "## 🤖 Automated CI Workflow",
            "",
            f"This PR adds a GitHub Actions workflow for automated CI/CD for this {language} project.",
            "",
            "### ✨ What's Included",
            "",
        ]
        
        if state.repo_metadata and state.repo_metadata.has_linter:
            description_parts.append("- 🔍 **Code Linting**: Automated code quality checks")
        
        if state.repo_metadata and state.repo_metadata.has_tests:
            description_parts.append("- 🧪 **Test Execution**: Runs all tests on every push")
        
        description_parts.extend([
            "- 📦 **Build Process**: Ensures the project builds successfully",
            "- 🔄 **Matrix Builds**: Tests across multiple language versions",
            "- ⚡ **Dependency Caching**: Faster builds with cached dependencies",
            "",
            "### 📋 Configuration",
            "",
            f"- **Language**: {language}",
            f"- **Package Manager**: {pm}",
            f"- **Confidence Score**: {state.workflow_content.confidence:.0%}" if state.workflow_content else "",
            "",
            "### 🎯 Benefits",
            "",
            "- Catches issues early before they reach production",
            "- Ensures code quality standards are maintained",
            "- Provides fast feedback on pull requests",
            "- Reduces manual testing overhead",
            "",
            "### 🔍 Review Notes",
            "",
        ])
        
        if state.validation_result and state.validation_result.warnings:
            description_parts.append("**Warnings**:")
            for warning in state.validation_result.warnings:
                description_parts.append(f"- ⚠️ {warning}")
            description_parts.append("")
        
        if state.diff_analysis:
            description_parts.extend([
                f"**Risk Level**: {state.diff_analysis.risk_category.upper()}",
                f"**Risk Score**: {state.diff_analysis.risk_score:.2f}",
                "",
            ])
        
        description_parts.extend([
            "---",
            "",
            "*Generated by Agentic CI Orchestrator*",
        ])
        
        return "\n".join(description_parts)
