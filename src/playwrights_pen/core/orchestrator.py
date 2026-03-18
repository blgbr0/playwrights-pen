"""Test orchestrator for managing test execution flow."""

from datetime import datetime
from typing import AsyncGenerator, Callable

from ..config import ConfirmationMode, settings
from ..llm import LLMClient
from ..mcp import MCPClient
from ..models import ExecutionMode, Session, SessionStatus, StepExecution, TestCase, TestStep
from ..storage import Repository
from .executor import TestExecutor
from .parser import TestParser
from .recorder import ExecutionRecorder


class StepResult:
    """Result of a step execution with context."""
    
    def __init__(
        self,
        step: TestStep,
        execution: StepExecution,
        requires_confirmation: bool = False,
    ) -> None:
        self.step = step
        self.execution = execution
        self.requires_confirmation = requires_confirmation
    
    @property
    def passed(self) -> bool:
        return self.execution.status == SessionStatus.PASSED
    
    @property
    def failed(self) -> bool:
        return self.execution.status == SessionStatus.FAILED


class TestOrchestrator:
    """Orchestrates test execution with confirmation modes."""
    
    def __init__(
        self,
        mcp_client: MCPClient | None = None,
        llm_client: LLMClient | None = None,
        repository: Repository | None = None,
        confirmation_mode: ConfirmationMode | None = None,
    ) -> None:
        """Initialize orchestrator.
        
        Args:
            mcp_client: MCP client (created on demand if not provided)
            llm_client: LLM client
            repository: Data repository
            confirmation_mode: Confirmation mode for interactive execution
        """
        self._mcp_client = mcp_client
        self.llm = llm_client or LLMClient()
        self.repository = repository or Repository()
        self.confirmation_mode = confirmation_mode or settings.default_confirmation_mode
        
        self.parser = TestParser(self.llm)
        self.recorder = ExecutionRecorder()
        self._executor: TestExecutor | None = None
    
    async def run_exploration(
        self,
        testcase: TestCase,
        on_step_complete: Callable[[StepResult], None] | None = None,
        on_confirmation_needed: Callable[[StepResult], bool] | None = None,
        on_manual_record: Callable[[TestStep, int], StepExecution] | None = None,
    ) -> Session:
        """Run test in exploration mode (first run).
        
        Args:
            testcase: Test case to execute
            on_step_complete: Callback after each step completes
            on_confirmation_needed: Callback BEFORE step execution, returns True to auto-execute
            on_manual_record: Callback when user rejects auto-execution, should record manual action
            
        Returns:
            Completed session
        """
        # Parse steps if not already done
        if not testcase.steps:
            testcase.steps = await self.parser.parse(testcase.description)
            testcase.steps = self.parser.identify_key_steps(testcase.steps)
            self.repository.save_testcase(testcase)
        
        # Create session
        session = Session(
            test_case_id=testcase.id,
            mode=ExecutionMode.EXPLORATION,
            total_steps=len(testcase.steps),
        )
        session.start()
        self.repository.save_session(session)
        
        # Execute with connection (MCP or Target)
        ctx = self._mcp_client.session() if hasattr(self._mcp_client, "session") else self._get_mcp_client().connect()
        async with ctx as mcp:
            executor = TestExecutor(mcp, self.llm)
            
            for i, step in enumerate(testcase.steps):
                # Check if confirmation is needed BEFORE execution
                needs_confirmation = self._should_confirm(step)
                
                execution = None
                
                if needs_confirmation:
                    # Pause and ask for confirmation BEFORE execution
                    session.pause()
                    self.repository.save_session(session)
                    
                    # Create a preview result for confirmation
                    preview_execution = StepExecution(step_index=i)
                    preview_result = StepResult(step, preview_execution, requires_confirmation=True)
                    
                    if on_confirmation_needed:
                        user_confirmed = on_confirmation_needed(preview_result)
                        
                        if user_confirmed:
                            # User approved - auto execute the step
                            session.resume()
                            execution = await executor.execute_step(step, i, use_recorded_ref=False)
                            self.recorder.record_user_confirmation(execution)
                        else:
                            # User rejected - enter manual recording mode
                            session.resume()
                            if on_manual_record:
                                # Let user perform the action manually, record it
                                execution = await on_manual_record(step, i)
                                if execution:
                                    execution.user_modified = True
                            else:
                                # No manual recorder, abort
                                session.abort("User rejected step, no manual recorder available")
                                break
                    else:
                        # No confirmation callback, just execute
                        session.resume()
                        execution = await executor.execute_step(step, i, use_recorded_ref=False)
                else:
                    # No confirmation needed - auto execute
                    execution = await executor.execute_step(step, i, use_recorded_ref=False)
                
                if execution is None:
                    session.abort("Step execution failed")
                    break
                
                session.step_executions.append(execution)
                
                # Update session stats
                if execution.status == SessionStatus.PASSED:
                    session.passed_steps += 1
                else:
                    session.failed_steps += 1
                
                # Create result for callback
                result = StepResult(step, execution, needs_confirmation)
                
                # Notify step completion
                if on_step_complete:
                    on_step_complete(result)
                
                # Stop on failure
                if execution.status == SessionStatus.FAILED:
                    session.finish(False, execution.error)
                    break
                
                self.repository.save_session(session)
            
            else:
                # All steps completed
                session.finish(True)
        
        # Update testcase with session reference
        testcase.last_session_id = session.id
        self.repository.save_testcase(testcase)
        self.repository.save_session(session)
        
        return session
    
    async def run_regression(
        self,
        testcase: TestCase,
        reference_session: Session | None = None,
        on_step_complete: Callable[[StepResult], None] | None = None,
    ) -> Session:
        """Run test in regression mode using recorded steps.
        
        Args:
            testcase: Test case to execute
            reference_session: Reference session to use (defaults to latest)
            on_step_complete: Callback after each step
            
        Returns:
            Completed session
        """
        if not testcase.steps:
            raise ValueError("Test case has no parsed steps. Run exploration first.")
        
        # Get reference session
        if reference_session is None:
            reference_session = self.repository.get_latest_session(testcase.id)
            if reference_session is None:
                raise ValueError("No reference session found. Run exploration first.")
        
        # Create session
        session = Session(
            test_case_id=testcase.id,
            mode=ExecutionMode.REGRESSION,
            total_steps=len(testcase.steps),
        )
        session.start()
        self.repository.save_session(session)
        
        # Execute with connection (MCP or Target)
        ctx = self._mcp_client.session() if hasattr(self._mcp_client, "session") else self._get_mcp_client().connect()
        async with ctx as mcp:
            executor = TestExecutor(mcp, self.llm)
            
            for i, step in enumerate(testcase.steps):
                # Try using recorded ref first
                execution = await executor.execute_step(step, i, use_recorded_ref=True)
                session.step_executions.append(execution)
                
                # Update session
                if execution.status == SessionStatus.PASSED:
                    session.passed_steps += 1
                else:
                    session.failed_steps += 1
                
                result = StepResult(step, execution)
                
                if on_step_complete:
                    on_step_complete(result)
                
                # Stop on failure
                if execution.status == SessionStatus.FAILED:
                    session.finish(False, execution.error)
                    break
                
                self.repository.save_session(session)
            
            else:
                session.finish(True)
        
        testcase.last_session_id = session.id
        self.repository.save_testcase(testcase)
        self.repository.save_session(session)
        
        return session
    
    async def run_interactive(
        self,
        testcase: TestCase,
    ) -> AsyncGenerator[StepResult, bool | None]:
        """Run test interactively, yielding after each step.
        
        Usage:
            gen = orchestrator.run_interactive(testcase)
            async for result in gen:
                # Process result
                # Send back confirmation with gen.asend(True) or gen.asend(False)
        
        Args:
            testcase: Test case to execute
            
        Yields:
            StepResult after each step
        """
        if not testcase.steps:
            testcase.steps = await self.parser.parse(testcase.description)
            testcase.steps = self.parser.identify_key_steps(testcase.steps)
            self.repository.save_testcase(testcase)
        
        session = Session(
            test_case_id=testcase.id,
            mode=ExecutionMode.EXPLORATION,
            total_steps=len(testcase.steps),
        )
        session.start()
        
        async with self._get_mcp_client().connect() as mcp:
            executor = TestExecutor(mcp, self.llm)
            
            for i, step in enumerate(testcase.steps):
                execution = await executor.execute_step(step, i, use_recorded_ref=False)
                session.step_executions.append(execution)
                
                if execution.status == SessionStatus.PASSED:
                    session.passed_steps += 1
                else:
                    session.failed_steps += 1
                
                needs_confirmation = self._should_confirm(step)
                result = StepResult(step, execution, needs_confirmation)
                
                # Yield and wait for confirmation
                should_continue = yield result
                
                if should_continue is False:
                    session.abort("User cancelled")
                    break
                
                if execution.status == SessionStatus.FAILED:
                    session.finish(False, execution.error)
                    break
            
            else:
                session.finish(True)
        
        testcase.last_session_id = session.id
        self.repository.save_testcase(testcase)
        self.repository.save_session(session)
    
    def _should_confirm(self, step: TestStep) -> bool:
        """Check if step requires confirmation based on mode.
        
        Args:
            step: Test step
            
        Returns:
            True if confirmation is needed
        """
        if self.confirmation_mode == ConfirmationMode.EVERY_STEP:
            return True
        elif self.confirmation_mode == ConfirmationMode.KEY_STEPS:
            return step.is_key_step
        else:  # NONE
            return False
    
    def _get_mcp_client(self) -> MCPClient:
        """Get or create MCP client."""
        if self._mcp_client is None:
            self._mcp_client = MCPClient()
        return self._mcp_client
