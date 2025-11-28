"""Templates package for workflow generation."""

from src.templates.workflow_templates import (
    WorkflowTemplate,
    PythonTemplate,
    NodeTemplate,
    JavaTemplate,
    GenericTemplate,
    get_template,
)

__all__ = [
    "WorkflowTemplate",
    "PythonTemplate",
    "NodeTemplate",
    "JavaTemplate",
    "GenericTemplate",
    "get_template",
]
