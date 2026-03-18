"""Execution session model definitions."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a unique ID."""
    return uuid4().hex[:12]


class ExecutionMode(str, Enum):
    """Execution mode for a session."""
    
    EXPLORATION = "exploration"  # 首轮探索执行
    REGRESSION = "regression"    # 回归测试执行
    HYBRID = "hybrid"            # 混合模式


class SessionStatus(str, Enum):
    """Status of an execution session."""
    
    PENDING = "pending"          # 等待开始
    RUNNING = "running"          # 执行中
    PAUSED = "paused"            # 暂停等待确认
    PASSED = "passed"            # 通过
    FAILED = "failed"            # 失败
    ABORTED = "aborted"          # 中止


class StepExecution(BaseModel):
    """Record of a single step execution."""
    
    step_index: int = Field(description="Index of the step in the test case")
    
    # Execution state
    status: SessionStatus = Field(default=SessionStatus.PENDING)
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    
    # Context
    snapshot_before: str | None = Field(
        default=None,
        description="Accessibility tree snapshot before execution",
    )
    snapshot_after: str | None = Field(
        default=None,
        description="Accessibility tree snapshot after execution",
    )
    
    # LLM reasoning
    llm_reasoning: str | None = Field(
        default=None,
        description="LLM's reasoning for element selection",
    )
    element_ref_used: str | None = Field(
        default=None,
        description="Actual element reference used",
    )
    
    # Result
    result: str | None = Field(default=None, description="Execution result")
    error: str | None = Field(default=None, description="Error message if failed")
    
    # User confirmation
    user_confirmed: bool = Field(
        default=False,
        description="Whether user confirmed this step",
    )
    user_modified: bool = Field(
        default=False,
        description="Whether this step was modified/executed manually by user",
    )


class Session(BaseModel):
    """An execution session for a test case."""
    
    id: str = Field(default_factory=generate_id, description="Session ID")
    test_case_id: str = Field(description="Associated test case ID")
    
    # Execution configuration
    mode: ExecutionMode = Field(
        default=ExecutionMode.EXPLORATION,
        description="Execution mode",
    )
    
    # Status
    status: SessionStatus = Field(default=SessionStatus.PENDING)
    current_step_index: int = Field(default=0, description="Current step index")
    
    # Execution records
    step_executions: list[StepExecution] = Field(
        default_factory=list,
        description="Execution record for each step",
    )
    
    # Timestamps
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    
    # Summary
    total_steps: int = Field(default=0)
    passed_steps: int = Field(default=0)
    failed_steps: int = Field(default=0)
    
    # Error info
    error_message: str | None = Field(default=None)
    
    def start(self) -> None:
        """Mark session as started."""
        self.status = SessionStatus.RUNNING
        self.started_at = datetime.now()
    
    def pause(self) -> None:
        """Pause session for user confirmation."""
        self.status = SessionStatus.PAUSED
    
    def resume(self) -> None:
        """Resume session after user confirmation."""
        self.status = SessionStatus.RUNNING
    
    def finish(self, passed: bool, error: str | None = None) -> None:
        """Mark session as finished."""
        self.status = SessionStatus.PASSED if passed else SessionStatus.FAILED
        self.ended_at = datetime.now()
        self.error_message = error
    
    def abort(self, reason: str | None = None) -> None:
        """Abort session."""
        self.status = SessionStatus.ABORTED
        self.ended_at = datetime.now()
        self.error_message = reason
