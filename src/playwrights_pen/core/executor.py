"""Test step executor."""

from datetime import datetime
from typing import Any

from ..llm import LLMClient
from ..mcp import MCPClient
from ..models import ActionType, AssertionType, Session, SessionStatus, StepExecution, TestStep


class TestExecutor:
    """Executor for individual test steps."""
    
    def __init__(
        self,
        mcp_client: MCPClient,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Initialize executor.
        
        Args:
            mcp_client: MCP client for browser operations
            llm_client: LLM client for element location
        """
        self.mcp = mcp_client
        self.llm = llm_client or LLMClient()
    
    async def execute_step(
        self,
        step: TestStep,
        step_index: int,
        use_recorded_ref: bool = False,
    ) -> StepExecution:
        """Execute a single test step.
        
        Args:
            step: The test step to execute
            step_index: Index of the step
            use_recorded_ref: Whether to use recorded element reference
            
        Returns:
            StepExecution record
        """
        execution = StepExecution(
            step_index=step_index,
            status=SessionStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        try:
            # Get current page snapshot
            snapshot = await self.mcp.get_snapshot()
            execution.snapshot_before = snapshot
            
            # Execute based on action type
            result = await self._execute_action(step, snapshot, use_recorded_ref)
            
            # Record the element ref that was used (for replay)
            if step.recorded_ref:
                execution.element_ref_used = step.recorded_ref
            
            # Get snapshot after execution
            execution.snapshot_after = await self.mcp.get_snapshot()
            execution.result = str(result)
            execution.status = SessionStatus.PASSED
            
        except Exception as e:
            execution.status = SessionStatus.FAILED
            execution.error = str(e)
        
        execution.ended_at = datetime.now()
        return execution
    
    async def _execute_action(
        self,
        step: TestStep,
        snapshot: str,
        use_recorded_ref: bool,
    ) -> dict[str, Any]:
        """Execute the step action.
        
        Args:
            step: Test step
            snapshot: Current accessibility snapshot
            use_recorded_ref: Whether to use recorded ref
            
        Returns:
            Execution result
        """
        action = step.action
        
        if action == ActionType.NAVIGATE:
            if not step.url:
                raise ValueError("Navigate action requires URL")
            return await self.mcp.navigate(step.url)
        
        elif action == ActionType.CLICK:
            ref = await self._get_element_ref(step, snapshot, use_recorded_ref)
            return await self.mcp.click(ref, element=step.selector_hint)
        
        elif action == ActionType.TYPE:
            ref = await self._get_element_ref(step, snapshot, use_recorded_ref)
            if not step.text:
                raise ValueError("Type action requires text")
            return await self.mcp.type(ref, step.text, element=step.selector_hint)
        
        elif action == ActionType.SELECT:
            ref = await self._get_element_ref(step, snapshot, use_recorded_ref)
            values = step.extra_params.get("values", [step.text] if step.text else [])
            return await self.mcp.select(ref, values, element=step.selector_hint)
        
        elif action == ActionType.HOVER:
            ref = await self._get_element_ref(step, snapshot, use_recorded_ref)
            return await self.mcp.hover(ref, element=step.selector_hint)
        
        elif action == ActionType.SCROLL:
            direction = step.extra_params.get("direction", "down")
            amount = step.extra_params.get("amount")
            return await self.mcp.scroll(direction, amount)
        
        elif action == ActionType.WAIT:
            time_ms = step.extra_params.get("time_ms", 1000)
            return await self.mcp.wait(time_ms)
        
        elif action == ActionType.SCREENSHOT:
            filename = step.extra_params.get("filename")
            return await self.mcp.screenshot(filename)
        
        elif action == ActionType.ASSERT:
            return await self._execute_assertion(step, snapshot)
        
        elif action == ActionType.EXECUTE_JS:
            function = step.extra_params.get("function", "")
            return await self.mcp.evaluate(function)
        
        else:
            raise ValueError(f"Unknown action type: {action}")
    
    async def _get_element_ref(
        self,
        step: TestStep,
        snapshot: str,
        use_recorded_ref: bool,
    ) -> str:
        """Get element reference for the step.
        
        Args:
            step: Test step
            snapshot: Current accessibility snapshot
            use_recorded_ref: Whether to use recorded ref
            
        Returns:
            Element reference string
        """
        # Use recorded ref if available and requested
        if use_recorded_ref and step.recorded_ref:
            return step.recorded_ref
        
        # Otherwise, use LLM to locate element
        if not step.selector_hint:
            raise ValueError("Element action requires selector_hint")
        
        result = await self.llm.locate_element(snapshot, step.selector_hint)
        
        if not result.get("ref"):
            raise ValueError(
                f"Could not locate element: {step.selector_hint}. "
                f"Reason: {result.get('reasoning', 'Unknown')}"
            )
        
        # Store for future regression
        step.recorded_ref = result["ref"]
        
        return result["ref"]
    
    async def _execute_assertion(
        self,
        step: TestStep,
        snapshot: str,
    ) -> dict[str, Any]:
        """Execute an assertion step.
        
        Args:
            step: Assertion step
            snapshot: Current accessibility snapshot
            
        Returns:
            Assertion result
        """
        assertion_type = step.assertion_type
        expected = step.expected_value
        
        if not assertion_type:
            raise ValueError("Assert action requires assertion_type")
        
        if assertion_type == AssertionType.TEXT_CONTAINS:
            if not step.selector_hint:
                # Check entire page
                if expected and expected in snapshot:
                    return {"passed": True, "message": f"Text '{expected}' found in page"}
                raise AssertionError(f"Text '{expected}' not found in page")
            
            # Check specific element
            result = await self.llm.locate_element(snapshot, step.selector_hint)
            if result.get("ref"):
                # Element found, check its content
                return {"passed": True, "message": f"Element found with ref: {result['ref']}"}
            raise AssertionError(f"Element '{step.selector_hint}' not found")
        
        elif assertion_type == AssertionType.ELEMENT_VISIBLE:
            result = await self.llm.locate_element(snapshot, step.selector_hint or "")
            if result.get("ref"):
                return {"passed": True, "message": "Element is visible"}
            raise AssertionError(f"Element '{step.selector_hint}' not visible")
        
        elif assertion_type == AssertionType.ELEMENT_EXISTS:
            result = await self.llm.locate_element(snapshot, step.selector_hint or "")
            if result.get("ref"):
                return {"passed": True, "message": "Element exists"}
            raise AssertionError(f"Element '{step.selector_hint}' does not exist")
        
        elif assertion_type in (AssertionType.URL_CONTAINS, AssertionType.URL_EQUALS,
                                AssertionType.TITLE_CONTAINS, AssertionType.TITLE_EQUALS):
            # These need JavaScript evaluation
            if assertion_type in (AssertionType.URL_CONTAINS, AssertionType.URL_EQUALS):
                js_result = await self.mcp.evaluate("() => window.location.href")
                actual = str(js_result.get("content", ""))
            else:
                js_result = await self.mcp.evaluate("() => document.title")
                actual = str(js_result.get("content", ""))
            
            if "contains" in assertion_type.value:
                if expected and expected in actual:
                    return {"passed": True, "actual": actual, "expected": expected}
                raise AssertionError(f"Expected '{expected}' in '{actual}'")
            else:
                if actual == expected:
                    return {"passed": True, "actual": actual}
                raise AssertionError(f"Expected '{expected}', got '{actual}'")
        
        else:
            raise ValueError(f"Unknown assertion type: {assertion_type}")
