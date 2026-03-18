"""Sessions API endpoints."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..config import ConfirmationMode
from ..core import TestOrchestrator
from ..models import ExecutionMode, Session, SessionStatus
from ..storage import Repository

router = APIRouter(prefix="/sessions", tags=["sessions"])
repository = Repository()

# Store running sessions for confirmation handling
_running_sessions: dict[str, dict] = {}


class CreateSessionRequest(BaseModel):
    """Request body for creating a session."""
    
    test_case_id: str
    mode: ExecutionMode = ExecutionMode.EXPLORATION
    confirmation_mode: ConfirmationMode = ConfirmationMode.KEY_STEPS


class SessionResponse(BaseModel):
    """Response model for session."""
    
    id: str
    test_case_id: str
    mode: ExecutionMode
    status: SessionStatus
    current_step: int
    total_steps: int
    passed_steps: int
    failed_steps: int
    error: str | None = None


class ConfirmRequest(BaseModel):
    """Request for confirming a step."""
    
    confirmed: bool = True
    modification: str | None = None


def _session_to_response(session: Session) -> SessionResponse:
    """Convert Session to SessionResponse."""
    return SessionResponse(
        id=session.id,
        test_case_id=session.test_case_id,
        mode=session.mode,
        status=session.status,
        current_step=session.current_step_index,
        total_steps=session.total_steps,
        passed_steps=session.passed_steps,
        failed_steps=session.failed_steps,
        error=session.error_message,
    )


async def _run_test(session_id: str, test_case_id: str, mode: ExecutionMode, confirmation_mode: ConfirmationMode):
    """Background task to run a test."""
    testcase = repository.get_testcase(test_case_id)
    if not testcase:
        return
    
    orchestrator = TestOrchestrator(confirmation_mode=confirmation_mode)
    
    def on_step_complete(result):
        session = repository.get_session(session_id)
        if session:
            repository.save_session(session)
    
    def on_confirmation_needed(result):
        # In API mode, we auto-confirm for now
        # A more advanced implementation would pause and wait for API call
        return True
    
    try:
        if mode == ExecutionMode.EXPLORATION:
            await orchestrator.run_exploration(
                testcase,
                on_step_complete=on_step_complete,
                on_confirmation_needed=on_confirmation_needed,
            )
        else:
            await orchestrator.run_regression(
                testcase,
                on_step_complete=on_step_complete,
            )
    except Exception as e:
        session = repository.get_session(session_id)
        if session:
            session.finish(False, str(e))
            repository.save_session(session)


@router.post("", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
) -> SessionResponse:
    """Create and start a new test session."""
    testcase = repository.get_testcase(request.test_case_id)
    if not testcase:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    # Create session
    session = Session(
        test_case_id=request.test_case_id,
        mode=request.mode,
        total_steps=len(testcase.steps) if testcase.steps else 0,
    )
    repository.save_session(session)
    
    # Start execution in background
    background_tasks.add_task(
        _run_test,
        session.id,
        request.test_case_id,
        request.mode,
        request.confirmation_mode,
    )
    
    return _session_to_response(session)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(test_case_id: str | None = None) -> list[SessionResponse]:
    """List all sessions, optionally filtered by test case."""
    sessions = repository.list_sessions(test_case_id)
    return [_session_to_response(s) for s in sessions]


@router.get("/{session_id}")
async def get_session(session_id: str) -> Session:
    """Get a session by ID with full details."""
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/confirm", response_model=SessionResponse)
async def confirm_step(session_id: str, request: ConfirmRequest) -> SessionResponse:
    """Confirm the current step in an interactive session."""
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status != SessionStatus.PAUSED:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not waiting for confirmation (status: {session.status})",
        )
    
    # Mark current step as confirmed
    if session.step_executions and session.current_step_index < len(session.step_executions):
        execution = session.step_executions[session.current_step_index]
        execution.user_confirmed = request.confirmed
        execution.user_modification = request.modification
    
    if request.confirmed:
        session.resume()
    else:
        session.abort("User rejected step")
    
    repository.save_session(session)
    return _session_to_response(session)


@router.post("/{session_id}/abort", response_model=SessionResponse)
async def abort_session(session_id: str) -> SessionResponse:
    """Abort a running session."""
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status in (SessionStatus.PASSED, SessionStatus.FAILED, SessionStatus.ABORTED):
        raise HTTPException(status_code=400, detail="Session already finished")
    
    session.abort("Aborted by user")
    repository.save_session(session)
    
    return _session_to_response(session)


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session."""
    if not repository.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# ==================== Execution History API ====================

class ExecutionStats(BaseModel):
    """Execution statistics."""
    
    total_executions: int = 0
    passed: int = 0
    failed: int = 0
    aborted: int = 0
    pass_rate: float = 0.0
    avg_steps: float = 0.0
    avg_duration_seconds: float = 0.0


class HistoryFilter(BaseModel):
    """Filter for execution history query."""
    
    test_case_id: str | None = None
    status: SessionStatus | None = None
    mode: ExecutionMode | None = None
    limit: int = 50
    offset: int = 0


class TrendPoint(BaseModel):
    """A point in trend analysis."""
    
    date: str
    total: int
    passed: int
    failed: int
    pass_rate: float


@router.get("/history/stats", response_model=ExecutionStats)
async def get_execution_stats(test_case_id: str | None = None) -> ExecutionStats:
    """Get execution statistics summary.
    
    Optionally filter by test case ID.
    Returns pass rate, average steps, failure rate, etc.
    """
    sessions = repository.list_sessions(test_case_id)
    
    if not sessions:
        return ExecutionStats()
    
    passed = sum(1 for s in sessions if s.status == SessionStatus.PASSED)
    failed = sum(1 for s in sessions if s.status == SessionStatus.FAILED)
    aborted = sum(1 for s in sessions if s.status == SessionStatus.ABORTED)
    total = len(sessions)
    
    # Calculate average steps
    total_steps = sum(s.total_steps for s in sessions)
    avg_steps = total_steps / total if total > 0 else 0
    
    # Calculate average duration (for finished sessions)
    durations = []
    for s in sessions:
        if s.started_at and s.ended_at:
            duration = (s.ended_at - s.started_at).total_seconds()
            durations.append(duration)
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return ExecutionStats(
        total_executions=total,
        passed=passed,
        failed=failed,
        aborted=aborted,
        pass_rate=passed / total if total > 0 else 0,
        avg_steps=avg_steps,
        avg_duration_seconds=avg_duration,
    )


@router.get("/history/recent", response_model=list[SessionResponse])
async def get_recent_executions(
    limit: int = 20,
    test_case_id: str | None = None,
) -> list[SessionResponse]:
    """Get recent test executions.
    
    Returns the most recent sessions, optionally filtered by test case.
    """
    sessions = repository.list_sessions(test_case_id)
    
    # Sort by created_at descending (most recent first)
    sessions.sort(key=lambda s: s.started_at or s.created_at, reverse=True)
    
    return [_session_to_response(s) for s in sessions[:limit]]


@router.get("/history/trends", response_model=list[TrendPoint])
async def get_execution_trends(
    days: int = 7,
    test_case_id: str | None = None,
) -> list[TrendPoint]:
    """Get execution trend analysis over time.
    
    Returns daily pass/fail counts and pass rate for the specified number of days.
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    sessions = repository.list_sessions(test_case_id)
    
    # Group by date
    daily_counts = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    
    cutoff = datetime.now() - timedelta(days=days)
    
    for s in sessions:
        session_date = s.started_at or s.created_at
        if session_date and session_date >= cutoff:
            date_str = session_date.strftime("%Y-%m-%d")
            daily_counts[date_str]["total"] += 1
            if s.status == SessionStatus.PASSED:
                daily_counts[date_str]["passed"] += 1
            elif s.status == SessionStatus.FAILED:
                daily_counts[date_str]["failed"] += 1
    
    # Generate trend points for each day
    trends = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        counts = daily_counts.get(date, {"total": 0, "passed": 0, "failed": 0})
        trends.append(TrendPoint(
            date=date,
            total=counts["total"],
            passed=counts["passed"],
            failed=counts["failed"],
            pass_rate=counts["passed"] / counts["total"] if counts["total"] > 0 else 0,
        ))
    
    return trends


@router.get("/history/{session_id}/recordings")
async def get_session_recordings(session_id: str) -> dict:
    """Get recording artifacts for a session.
    
    Returns paths to screenshots, snapshots, and videos if available.
    """
    from pathlib import Path
    from ..config import settings
    
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    recordings_dir = settings.data_dir / "recordings" / session_id
    
    if not recordings_dir.exists():
        return {
            "session_id": session_id,
            "has_recordings": False,
            "screenshots": [],
            "snapshots": [],
            "video": None,
            "action_log": None,
        }
    
    # Find recordings
    screenshots = list(recordings_dir.glob("screenshot_*.png"))
    snapshots = list(recordings_dir.glob("snapshot_*.txt"))
    video = recordings_dir / "execution.webm"
    action_log = recordings_dir / "actions.json"
    
    return {
        "session_id": session_id,
        "has_recordings": True,
        "recordings_dir": str(recordings_dir),
        "screenshots": [str(p.name) for p in sorted(screenshots)],
        "snapshots": [str(p.name) for p in sorted(snapshots)],
        "video": str(video.name) if video.exists() else None,
        "action_log": str(action_log.name) if action_log.exists() else None,
    }

