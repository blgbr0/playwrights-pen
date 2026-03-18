"""Test suite model for batch execution."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class TestSuite(BaseModel):
    """A collection of test cases to run together."""
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(..., description="Suite name")
    description: str = Field(default="", description="Suite description")
    
    # Test case references
    test_case_ids: list[str] = Field(
        default_factory=list,
        description="List of test case IDs in this suite"
    )
    
    # Alternatively, filter by tags
    include_tags: list[str] = Field(
        default_factory=list,
        description="Include test cases with any of these tags"
    )
    exclude_tags: list[str] = Field(
        default_factory=list,
        description="Exclude test cases with any of these tags"
    )
    
    # Execution settings
    parallel: bool = Field(
        default=False,
        description="Run test cases in parallel"
    )
    stop_on_failure: bool = Field(
        default=False,
        description="Stop suite execution on first failure"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries for failed tests"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SuiteExecution(BaseModel):
    """Result of a suite execution."""
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    suite_id: str = Field(..., description="Reference to the suite")
    suite_name: str = Field(default="", description="Suite name for display")
    
    # Execution results
    session_ids: list[str] = Field(
        default_factory=list,
        description="Session IDs for each test case execution"
    )
    
    # Summary stats
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    
    # Timing
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: float = 0.0
    
    # Status
    status: str = Field(
        default="pending",
        description="pending, running, passed, failed, aborted"
    )
    
    def start(self) -> None:
        """Mark execution as started."""
        self.status = "running"
        self.started_at = datetime.now()
    
    def finish(self, success: bool) -> None:
        """Mark execution as finished."""
        self.status = "passed" if success else "failed"
        self.ended_at = datetime.now()
        if self.started_at:
            self.duration_seconds = (self.ended_at - self.started_at).total_seconds()
    
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_cases == 0:
            return 0.0
        return (self.passed_cases / self.total_cases) * 100
