"""Suite runner for batch test execution."""

import asyncio
from datetime import datetime
from typing import Callable, AsyncGenerator

from ..config import ConfirmationMode
from ..models import TestCase, Session, SessionStatus
from ..models.suite import TestSuite, SuiteExecution
from ..storage import Repository
from .orchestrator import TestOrchestrator, StepResult


class SuiteRunner:
    """Runs a test suite (batch of test cases)."""
    
    def __init__(
        self,
        repository: Repository | None = None,
        confirmation_mode: ConfirmationMode = ConfirmationMode.NONE,
    ) -> None:
        """Initialize suite runner.
        
        Args:
            repository: Data repository
            confirmation_mode: Default confirmation mode for tests
        """
        self.repository = repository or Repository()
        self.confirmation_mode = confirmation_mode
    
    def get_test_cases(self, suite: TestSuite) -> list[TestCase]:
        """Get test cases matching suite criteria.
        
        Args:
            suite: Test suite configuration
            
        Returns:
            List of matching test cases
        """
        # Get by explicit IDs
        if suite.test_case_ids:
            cases = []
            for tc_id in suite.test_case_ids:
                tc = self.repository.get_testcase(tc_id)
                if tc:
                    cases.append(tc)
            return cases
        
        # Get by tags
        all_cases = self.repository.list_testcases()
        
        if not suite.include_tags and not suite.exclude_tags:
            return all_cases
        
        filtered = []
        for tc in all_cases:
            # Check include tags (OR logic)
            if suite.include_tags:
                if not any(tag in tc.tags for tag in suite.include_tags):
                    continue
            
            # Check exclude tags
            if suite.exclude_tags:
                if any(tag in tc.tags for tag in suite.exclude_tags):
                    continue
            
            filtered.append(tc)
        
        return filtered
    
    async def run_suite(
        self,
        suite: TestSuite,
        on_case_start: Callable[[TestCase, int, int], None] | None = None,
        on_case_complete: Callable[[TestCase, Session, int, int], None] | None = None,
        on_step_complete: Callable[[StepResult], None] | None = None,
    ) -> SuiteExecution:
        """Run all test cases in a suite.
        
        Args:
            suite: Test suite to run
            on_case_start: Callback when a test case starts (case, index, total)
            on_case_complete: Callback when a test case completes
            on_step_complete: Callback for step completion
            
        Returns:
            Suite execution result
        """
        # Get test cases
        test_cases = self.get_test_cases(suite)
        
        # Create execution record
        execution = SuiteExecution(
            suite_id=suite.id,
            suite_name=suite.name,
            total_cases=len(test_cases),
        )
        execution.start()
        
        if not test_cases:
            execution.finish(True)
            return execution
        
        # Run each test case
        orchestrator = TestOrchestrator(
            repository=self.repository,
            confirmation_mode=self.confirmation_mode,
        )
        
        for i, tc in enumerate(test_cases):
            if on_case_start:
                on_case_start(tc, i, len(test_cases))
            
            # Run with retry
            session = None
            attempts = 0
            max_attempts = suite.retry_count + 1
            
            while attempts < max_attempts:
                attempts += 1
                try:
                    session = await orchestrator.run_exploration(
                        tc,
                        on_step_complete=on_step_complete,
                    )
                    
                    if session.status == SessionStatus.PASSED:
                        break
                    
                    # Retry on failure
                    if attempts < max_attempts:
                        continue
                        
                except Exception as e:
                    if attempts >= max_attempts:
                        # Create failed session
                        session = Session(
                            test_case_id=tc.id,
                            status=SessionStatus.FAILED,
                            error_message=str(e),
                        )
                        break
            
            if session:
                execution.session_ids.append(session.id)
                
                if session.status == SessionStatus.PASSED:
                    execution.passed_cases += 1
                else:
                    execution.failed_cases += 1
                    
                    if suite.stop_on_failure:
                        execution.skipped_cases = len(test_cases) - i - 1
                        break
            
            if on_case_complete:
                on_case_complete(tc, session, i, len(test_cases))
        
        # Finish
        all_passed = execution.failed_cases == 0 and execution.skipped_cases == 0
        execution.finish(all_passed)
        
        return execution
    
    async def run_by_tags(
        self,
        tags: list[str],
        **kwargs,
    ) -> SuiteExecution:
        """Convenience method to run tests by tags.
        
        Args:
            tags: Tags to filter by
            **kwargs: Additional arguments for run_suite
            
        Returns:
            Suite execution result
        """
        suite = TestSuite(
            name=f"Tag filter: {', '.join(tags)}",
            include_tags=tags,
        )
        return await self.run_suite(suite, **kwargs)
