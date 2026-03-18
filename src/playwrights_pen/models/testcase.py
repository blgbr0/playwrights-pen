"""Test case model definitions."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .step import TestStep


def generate_id() -> str:
    """Generate a unique ID."""
    return uuid4().hex[:12]


class TestCase(BaseModel):
    """A test case containing natural language description and parsed steps."""
    
    id: str = Field(default_factory=generate_id, description="Unique identifier")
    name: str = Field(description="Test case name")
    description: str = Field(
        description="Natural language description of the test case"
    )
    
    # Parsed steps (populated after parsing or first execution)
    steps: list[TestStep] = Field(
        default_factory=list,
        description="Parsed test steps",
    )
    
    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Execution history reference
    last_session_id: str | None = Field(
        default=None,
        description="ID of the last execution session",
    )
    
    def model_post_init(self, __context) -> None:
        """Update timestamp on changes."""
        self.updated_at = datetime.now()
