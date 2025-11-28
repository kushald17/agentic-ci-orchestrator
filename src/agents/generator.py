"""
Workflow Generator Agent.

Generates GitHub Actions workflows using templates and Ollama reasoning.
"""

import time
from datetime import datetime
import structlog

from src.models.state import AgentState, WorkflowContent
from src.integrations.ollama_client import OllamaClient
from src.templates import get_template

logger = structlog.get_logger()


class WorkflowGeneratorAgent:
    """Generates CI workflows using templates and LLM reasoning."""
    
    def __init__(self, ollama_client: OllamaClient, model: str = "llama3:70b"):
        self.ollama_client = ollama_client
        self.model = model
    
    def generate(self, state: AgentState) -> AgentState:
        """
        Generate workflow file.
        
        Args:
            state: Current agent state with repo_metadata
        
        Returns:
            Updated state with workflow_content
        """
        if not state.repo_metadata:
            state.add_error("Cannot generate workflow without repository metadata")
            state.next_action = "fail"
            return state
        
        logger.info(
            "generating_workflow",
            language=state.repo_metadata.language,
            repo=state.repo_metadata.full_name,
        )
        
        start_time = time.time()
        
        try:
            # Get base template
            template_kwargs = self._get_template_kwargs(state)
            template = get_template(state.repo_metadata.language, **template_kwargs)
            
            # Generate base workflow
            base_workflow = template.generate(
                repo_name=state.repo_metadata.name,
                branch=state.repo_metadata.branch,
                include_lint=state.repo_metadata.has_linter,
                include_test=state.repo_metadata.has_tests,
                include_build=True,
            )
            
            # Enhance with LLM reasoning if needed
            if state.repo_metadata.custom_commands:
                enhanced_workflow = self._enhance_with_llm(state, base_workflow)
            else:
                enhanced_workflow = base_workflow
            
            # Create workflow content
            workflow_content = WorkflowContent(
                filename="ci.yml",
                content=enhanced_workflow,
                path=".github/workflows/ci.yml",
                generated_at=datetime.utcnow(),
                generator_model=self.model,
                confidence=0.95 if not state.repo_metadata.custom_commands else 0.85,
            )
            
            state.workflow_content = workflow_content
            state.next_action = "validate"
            
            duration = time.time() - start_time
            state.add_agent_record(
                agent_name="WorkflowGenerator",
                action="generate",
                result=f"Generated {len(enhanced_workflow)} bytes",
                duration=duration,
            )
            
            logger.info(
                "workflow_generated",
                size=len(enhanced_workflow),
                confidence=workflow_content.confidence,
                duration=duration,
            )
            
            return state
            
        except Exception as e:
            error_msg = f"Workflow generation failed: {str(e)}"
            logger.error("generation_failed", error=str(e))
            state.add_error(error_msg)
            state.next_action = "fail"
            return state
    
    def _get_template_kwargs(self, state: AgentState) -> dict:
        """Extract template-specific kwargs from metadata."""
        kwargs = {}
        metadata = state.repo_metadata
        
        if metadata.language == "python":
            if metadata.language_version:
                kwargs["python_version"] = metadata.language_version
            kwargs["use_poetry"] = metadata.package_manager == "poetry"
            kwargs["use_pipenv"] = metadata.package_manager == "pipenv"
        
        elif metadata.language == "node":
            kwargs["use_yarn"] = metadata.package_manager == "yarn"
            kwargs["use_pnpm"] = metadata.package_manager == "pnpm"
        
        elif metadata.language == "java":
            kwargs["use_gradle"] = metadata.build_tool == "gradle"
        
        return kwargs
    
    def _enhance_with_llm(self, state: AgentState, base_workflow: str) -> str:
        """
        Enhance workflow with LLM reasoning for custom commands.
        
        Args:
            state: Current state with metadata
            base_workflow: Base workflow YAML
        
        Returns:
            Enhanced workflow YAML
        """
        system_prompt = """You are a CI/CD workflow expert. Your task is to enhance a GitHub Actions workflow 
with custom commands from the repository's package.json or similar configuration.

RULES:
1. Preserve all existing steps
2. Add custom commands where appropriate
3. Ensure YAML is valid
4. Do not add secrets or credentials
5. Keep the workflow secure and minimal
6. Return ONLY the complete YAML workflow, nothing else"""
        
        user_prompt = f"""Repository: {state.repo_metadata.full_name}
Language: {state.repo_metadata.language}
Custom commands available:
{state.repo_metadata.custom_commands}

Base workflow:
```yaml
{base_workflow}
```

Enhance this workflow by integrating relevant custom commands. Respond with the complete enhanced YAML."""
        
        try:
            response = self.ollama_client.generate(
                model=self.model,
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.0,
            )
            
            enhanced = response.content.strip()
            
            # Extract YAML from markdown if present
            if "```yaml" in enhanced:
                enhanced = enhanced.split("```yaml")[1].split("```")[0].strip()
            elif "```" in enhanced:
                enhanced = enhanced.split("```")[1].split("```")[0].strip()
            
            # Validate that it's still YAML
            import yaml
            yaml.safe_load(enhanced)
            
            return enhanced
            
        except Exception as e:
            logger.warning("llm_enhancement_failed", error=str(e))
            # Fall back to base workflow
            return base_workflow
