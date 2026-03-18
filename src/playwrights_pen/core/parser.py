"""Natural language test case parser."""

from ..llm import LLMClient
from ..models import TestCase, TestStep


class TestParser:
    """Parser for natural language test descriptions."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize parser.
        
        Args:
            llm_client: LLM client instance (creates default if not provided)
        """
        self.llm = llm_client or LLMClient()
    
    async def parse(self, description: str) -> list[TestStep]:
        """Parse natural language description into test steps.
        
        Args:
            description: Natural language test description
            
        Returns:
            List of parsed TestStep objects
        """
        return await self.llm.parse_testcase(description)
    
    async def create_testcase(
        self,
        name: str,
        description: str,
        tags: list[str] | None = None,
    ) -> TestCase:
        """Create a test case from natural language description.
        
        Args:
            name: Test case name
            description: Natural language description
            tags: Optional tags
            
        Returns:
            TestCase with parsed steps
        """
        steps = await self.parse(description)
        
        return TestCase(
            name=name,
            description=description,
            steps=steps,
            tags=tags or [],
        )
    
    def identify_key_steps(self, steps: list[TestStep]) -> list[TestStep]:
        """Identify and mark key steps that require confirmation.
        
        Key steps include:
        - Form submissions
        - Delete/remove actions
        - Payment/checkout actions
        - Any step with significant side effects
        
        Args:
            steps: List of test steps
            
        Returns:
            Steps with is_key_step updated
        """
        key_indicators = [
            "submit", "delete", "remove", "confirm", "checkout",
            "pay", "order", "cancel", "approve", "reject",
            "提交", "删除", "移除", "确认", "结账", 
            "支付", "下单", "取消", "批准", "拒绝",
        ]
        
        for step in steps:
            # Check description for key indicators
            desc = (step.description or "").lower()
            hint = (step.selector_hint or "").lower()
            
            for indicator in key_indicators:
                if indicator in desc or indicator in hint:
                    step.is_key_step = True
                    break
        
        return steps
