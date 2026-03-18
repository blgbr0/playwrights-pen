"""Test module model for reusable test blocks."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class TestModule(BaseModel):
    """A reusable block of test steps.
    
    Modules represent common operations like:
    - Login flow
    - Navigation to specific page
    - Form filling patterns
    - Checkout process
    
    Modules can be referenced by test cases using `use: module_name`.
    """
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(..., description="Module name (used for referencing)")
    description: str = Field(default="", description="What this module does")
    
    # Steps in this module
    steps: list = Field(
        default_factory=list,
        description="List of TestStep objects in this module"
    )
    
    # Parameters this module accepts
    parameters: list[str] = Field(
        default_factory=list,
        description="Parameter names this module accepts, e.g. ['username', 'password']"
    )
    
    # State detection - what indicates this module is already completed
    completion_indicator: str | None = Field(
        default=None,
        description="Natural language description of state that indicates module is complete"
    )
    
    # Outputs this module provides
    outputs: list[str] = Field(
        default_factory=list,
        description="Variable names this module outputs to context"
    )
    
    # Tags for organization
    tags: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ModuleReference(BaseModel):
    """Reference to a module within a test case."""
    
    module_name: str = Field(..., description="Name of the module to use")
    
    # Parameter values for this invocation
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Parameter values to pass to the module"
    )
    
    # Skip if condition met
    skip_if: str | None = Field(
        default=None,
        description="Natural language condition to skip this module"
    )


class ExecutionContext(BaseModel):
    """Execution context for passing data between steps and modules.
    
    This holds:
    - Extracted data from pages
    - Module outputs
    - Database query results
    - User-provided inputs
    """
    
    # Variable storage
    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Variable name -> value mapping"
    )
    
    # Extracted elements
    extractions: dict[str, str] = Field(
        default_factory=dict,
        description="Extracted data from page elements"
    )
    
    # Database results
    db_results: dict[str, list[dict]] = Field(
        default_factory=dict,
        description="Named database query results"
    )
    
    # Module completion status
    completed_modules: set[str] = Field(
        default_factory=set,
        description="Set of completed module names"
    )
    
    def set_var(self, name: str, value: str) -> None:
        """Set a variable in context."""
        self.variables[name] = value
    
    def get_var(self, name: str, default: str = "") -> str:
        """Get a variable from context."""
        return self.variables.get(name, default)
    
    def mark_module_complete(self, module_name: str) -> None:
        """Mark a module as completed."""
        self.completed_modules.add(module_name)
    
    def is_module_complete(self, module_name: str) -> bool:
        """Check if module is already completed."""
        return module_name in self.completed_modules
    
    def resolve_placeholders(self, text: str) -> str:
        """Resolve {{placeholder}} in text using context variables."""
        import re
        
        def replace(match):
            var_name = match.group(1)
            return self.variables.get(var_name, match.group(0))
        
        return re.sub(r'\{\{(\w+)\}\}', replace, text)
