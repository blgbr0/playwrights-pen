"""Database-backed repository for test cases and sessions."""

from datetime import datetime
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.database import get_db, AsyncSessionLocal
from ..db.models import (
    TestCaseDB, 
    ExecutionSessionDB, 
    StepExecutionDB,
    TestTargetDB,
)
from ..models import Session, TestCase, TestStep, StepExecution as StepExecutionModel


class AsyncRepository:
    """Async database repository for test cases and sessions."""
    
    # ==================== Test Cases ====================
    
    async def save_testcase(self, testcase: TestCase) -> None:
        """Save a test case to database."""
        async with AsyncSessionLocal() as db:
            # Check if exists
            result = await db.execute(
                select(TestCaseDB).where(TestCaseDB.id == testcase.id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                existing.name = testcase.name
                existing.description = testcase.description
                existing.steps = [step.model_dump() for step in testcase.steps]
                existing.tags = testcase.tags
                existing.last_session_id = testcase.last_session_id
            else:
                # Create
                db_testcase = TestCaseDB(
                    id=testcase.id,
                    name=testcase.name,
                    description=testcase.description,
                    steps=[step.model_dump() for step in testcase.steps],
                    tags=testcase.tags,
                    last_session_id=testcase.last_session_id,
                )
                db.add(db_testcase)
            
            await db.commit()
    
    async def get_testcase(self, testcase_id: str) -> TestCase | None:
        """Get a test case by ID."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TestCaseDB).where(TestCaseDB.id == testcase_id)
            )
            db_testcase = result.scalar_one_or_none()
            
            if not db_testcase:
                return None
            
            return self._db_to_testcase(db_testcase)
    
    async def list_testcases(self) -> list[TestCase]:
        """List all test cases."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TestCaseDB).order_by(TestCaseDB.created_at.desc())
            )
            db_testcases = result.scalars().all()
            
            return [self._db_to_testcase(tc) for tc in db_testcases]
    
    async def delete_testcase(self, testcase_id: str) -> bool:
        """Delete a test case."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TestCaseDB).where(TestCaseDB.id == testcase_id)
            )
            db_testcase = result.scalar_one_or_none()
            
            if not db_testcase:
                return False
            
            await db.delete(db_testcase)
            await db.commit()
            return True
    
    def _db_to_testcase(self, db_testcase: TestCaseDB) -> TestCase:
        """Convert DB model to Pydantic model."""
        steps = []
        for step_data in db_testcase.steps or []:
            steps.append(TestStep.model_validate(step_data))
        
        return TestCase(
            id=db_testcase.id,
            name=db_testcase.name,
            description=db_testcase.description,
            steps=steps,
            tags=db_testcase.tags or [],
            created_at=db_testcase.created_at,
            updated_at=db_testcase.updated_at,
            last_session_id=db_testcase.last_session_id,
        )
    
    # ==================== Sessions ====================
    
    async def save_session(self, session: Session) -> None:
        """Save a session to database."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExecutionSessionDB)
                .where(ExecutionSessionDB.id == session.id)
                .options(selectinload(ExecutionSessionDB.step_executions))
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                existing.mode = session.mode.value
                existing.status = session.status.value
                existing.current_step_index = session.current_step_index
                existing.total_steps = session.total_steps
                existing.passed_steps = session.passed_steps
                existing.failed_steps = session.failed_steps
                existing.error_message = session.error_message
                existing.started_at = session.started_at
                existing.ended_at = session.ended_at
                
                # Update step executions
                for step_exec in session.step_executions:
                    await self._save_step_execution(db, session.id, step_exec)
            else:
                # Create
                db_session = ExecutionSessionDB(
                    id=session.id,
                    testcase_id=session.test_case_id,
                    mode=session.mode.value,
                    status=session.status.value,
                    current_step_index=session.current_step_index,
                    total_steps=session.total_steps,
                    passed_steps=session.passed_steps,
                    failed_steps=session.failed_steps,
                    error_message=session.error_message,
                    started_at=session.started_at,
                    ended_at=session.ended_at,
                )
                db.add(db_session)
                await db.flush()  # Get the ID
                
                # Add step executions
                for step_exec in session.step_executions:
                    await self._save_step_execution(db, session.id, step_exec)
            
            await db.commit()
    
    async def _save_step_execution(
        self, 
        db: AsyncSession, 
        session_id: str, 
        step_exec: StepExecutionModel
    ) -> None:
        """Save or update a step execution."""
        result = await db.execute(
            select(StepExecutionDB).where(
                StepExecutionDB.session_id == session_id,
                StepExecutionDB.step_index == step_exec.step_index
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.status = step_exec.status.value
            existing.snapshot_before = step_exec.snapshot_before
            existing.snapshot_after = step_exec.snapshot_after
            existing.llm_reasoning = step_exec.llm_reasoning
            existing.element_ref_used = step_exec.element_ref_used
            existing.result = step_exec.result
            existing.error = step_exec.error
            existing.user_confirmed = step_exec.user_confirmed
            existing.user_modification = step_exec.user_modification
            existing.started_at = step_exec.started_at
            existing.ended_at = step_exec.ended_at
        else:
            db_step = StepExecutionDB(
                session_id=session_id,
                step_index=step_exec.step_index,
                status=step_exec.status.value,
                snapshot_before=step_exec.snapshot_before,
                snapshot_after=step_exec.snapshot_after,
                llm_reasoning=step_exec.llm_reasoning,
                element_ref_used=step_exec.element_ref_used,
                result=step_exec.result,
                error=step_exec.error,
                user_confirmed=step_exec.user_confirmed,
                user_modification=step_exec.user_modification,
                started_at=step_exec.started_at,
                ended_at=step_exec.ended_at,
            )
            db.add(db_step)
    
    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExecutionSessionDB)
                .where(ExecutionSessionDB.id == session_id)
                .options(selectinload(ExecutionSessionDB.step_executions))
            )
            db_session = result.scalar_one_or_none()
            
            if not db_session:
                return None
            
            return self._db_to_session(db_session)
    
    async def list_sessions(self, test_case_id: str | None = None) -> list[Session]:
        """List sessions, optionally filtered by test case."""
        async with AsyncSessionLocal() as db:
            query = select(ExecutionSessionDB).options(
                selectinload(ExecutionSessionDB.step_executions)
            )
            
            if test_case_id:
                query = query.where(ExecutionSessionDB.testcase_id == test_case_id)
            
            query = query.order_by(ExecutionSessionDB.created_at.desc())
            
            result = await db.execute(query)
            db_sessions = result.scalars().all()
            
            return [self._db_to_session(s) for s in db_sessions]
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExecutionSessionDB).where(ExecutionSessionDB.id == session_id)
            )
            db_session = result.scalar_one_or_none()
            
            if not db_session:
                return False
            
            await db.delete(db_session)
            await db.commit()
            return True
    
    async def get_latest_session(self, test_case_id: str) -> Session | None:
        """Get the latest session for a test case."""
        sessions = await self.list_sessions(test_case_id)
        return sessions[0] if sessions else None
    
    def _db_to_session(self, db_session: ExecutionSessionDB) -> Session:
        """Convert DB model to Pydantic model."""
        from ..models import ExecutionMode, SessionStatus
        
        step_executions = []
        for db_step in sorted(db_session.step_executions, key=lambda x: x.step_index):
            step_executions.append(StepExecutionModel(
                step_index=db_step.step_index,
                status=SessionStatus(db_step.status),
                snapshot_before=db_step.snapshot_before,
                snapshot_after=db_step.snapshot_after,
                llm_reasoning=db_step.llm_reasoning,
                element_ref_used=db_step.element_ref_used,
                result=db_step.result,
                error=db_step.error,
                user_confirmed=db_step.user_confirmed,
                user_modification=db_step.user_modification,
                started_at=db_step.started_at,
                ended_at=db_step.ended_at,
            ))
        
        return Session(
            id=db_session.id,
            test_case_id=db_session.testcase_id,
            mode=ExecutionMode(db_session.mode),
            status=SessionStatus(db_session.status),
            current_step_index=db_session.current_step_index,
            step_executions=step_executions,
            started_at=db_session.started_at,
            ended_at=db_session.ended_at,
            total_steps=db_session.total_steps,
            passed_steps=db_session.passed_steps,
            failed_steps=db_session.failed_steps,
            error_message=db_session.error_message,
        )


# Singleton instance
async_repository = AsyncRepository()
