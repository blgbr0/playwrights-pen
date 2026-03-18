"""SQLAlchemy ORM models for database storage."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    type_annotation_map = {
        dict[str, Any]: JSON,
    }


def generate_uuid() -> str:
    """Generate a UUID string."""
    return uuid.uuid4().hex


class TestTargetDB(Base):
    """Test target configuration (Web, Electron, Mobile)."""
    
    __tablename__ = "test_targets"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # web, electron, mobile
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    testcases: Mapped[list["TestCaseDB"]] = relationship(back_populates="target")


class TestCaseDB(Base):
    """Test case with natural language description and parsed steps."""
    
    __tablename__ = "test_cases"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    target_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("test_targets.id"), nullable=True
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)  # List of step dicts
    tags: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)  # List of strings
    
    last_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    target: Mapped[TestTargetDB | None] = relationship(back_populates="testcases")
    sessions: Mapped[list["ExecutionSessionDB"]] = relationship(back_populates="testcase")


class ExecutionSessionDB(Base):
    """Execution session for a test case."""
    
    __tablename__ = "execution_sessions"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    testcase_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("test_cases.id"), nullable=False
    )
    
    mode: Mapped[str] = mapped_column(String(50), default="exploration")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    testcase: Mapped[TestCaseDB] = relationship(back_populates="sessions")
    step_executions: Mapped[list["StepExecutionDB"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["ExecutionArtifactDB"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class StepExecutionDB(Base):
    """Execution record for a single step."""
    
    __tablename__ = "step_executions"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("execution_sessions.id"), nullable=False
    )
    
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    
    snapshot_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    llm_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    element_ref_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    user_modification: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    session: Mapped[ExecutionSessionDB] = relationship(back_populates="step_executions")


class ExecutionArtifactDB(Base):
    """Artifacts produced during execution (screenshots, videos, logs)."""
    
    __tablename__ = "execution_artifacts"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("execution_sessions.id"), nullable=False
    )
    
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # screenshot, video, log
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    session: Mapped[ExecutionSessionDB] = relationship(back_populates="artifacts")
