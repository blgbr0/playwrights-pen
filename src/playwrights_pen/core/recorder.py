"""Execution recorder for test sessions."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..models import Session, StepExecution


class ExecutionRecorder:
    """Records execution details for sessions."""
    
    def __init__(self, snapshots_dir: Path | None = None) -> None:
        """Initialize recorder.
        
        Args:
            snapshots_dir: Directory for saving snapshots
        """
        self.snapshots_dir = snapshots_dir or settings.snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    def save_snapshot(self, content: str, session_id: str) -> str:
        """Save an accessibility snapshot.
        
        Args:
            content: Snapshot content
            session_id: Session ID
            
        Returns:
            Snapshot ID
        """
        snapshot_id = f"{session_id}_{uuid4().hex[:8]}"
        filepath = self.snapshots_dir / f"{snapshot_id}.txt"
        filepath.write_text(content, encoding="utf-8")
        return snapshot_id
    
    def load_snapshot(self, snapshot_id: str) -> str | None:
        """Load a saved snapshot.
        
        Args:
            snapshot_id: Snapshot ID
            
        Returns:
            Snapshot content or None
        """
        filepath = self.snapshots_dir / f"{snapshot_id}.txt"
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None
    
    def record_step_start(
        self,
        session: Session,
        step_index: int,
    ) -> StepExecution:
        """Record the start of a step execution.
        
        Args:
            session: Current session
            step_index: Step index
            
        Returns:
            New StepExecution record
        """
        execution = StepExecution(
            step_index=step_index,
            started_at=datetime.now(),
        )
        
        # Ensure we have enough slots
        while len(session.step_executions) <= step_index:
            session.step_executions.append(
                StepExecution(step_index=len(session.step_executions))
            )
        
        session.step_executions[step_index] = execution
        session.current_step_index = step_index
        
        return execution
    
    def record_step_complete(
        self,
        execution: StepExecution,
        success: bool,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        """Record step completion.
        
        Args:
            execution: Step execution record
            success: Whether step passed
            result: Result message
            error: Error message if failed
        """
        from ..models import SessionStatus
        
        execution.ended_at = datetime.now()
        execution.status = SessionStatus.PASSED if success else SessionStatus.FAILED
        execution.result = result
        execution.error = error
    
    def record_snapshot(
        self,
        execution: StepExecution,
        snapshot: str,
        session_id: str,
        before: bool = True,
    ) -> str:
        """Record a snapshot for a step.
        
        Args:
            execution: Step execution
            snapshot: Snapshot content
            session_id: Session ID
            before: Whether this is before (True) or after (False) execution
            
        Returns:
            Snapshot ID
        """
        snapshot_id = self.save_snapshot(snapshot, session_id)
        
        if before:
            execution.snapshot_before = snapshot_id
        else:
            execution.snapshot_after = snapshot_id
        
        return snapshot_id
    
    def record_llm_reasoning(
        self,
        execution: StepExecution,
        reasoning: str,
        element_ref: str | None = None,
    ) -> None:
        """Record LLM reasoning for element selection.
        
        Args:
            execution: Step execution
            reasoning: LLM's reasoning
            element_ref: Selected element reference
        """
        execution.llm_reasoning = reasoning
        execution.element_ref_used = element_ref
    
    def record_user_confirmation(
        self,
        execution: StepExecution,
        modification: str | None = None,
    ) -> None:
        """Record user confirmation.
        
        Args:
            execution: Step execution
            modification: User's modification if any
        """
        execution.user_confirmed = True
        execution.user_modified = bool(modification)
