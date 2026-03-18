"""LLM client for natural language processing and reasoning."""

import json
from typing import Any

from openai import AsyncOpenAI

from ..config import settings
from ..models import ActionType, AssertionType, TestStep


# System prompts for different tasks
PARSE_TESTCASE_PROMPT = """You are a test automation expert. Your task is to parse natural language test case descriptions into structured test steps.

Given a test case description, extract the sequence of browser actions needed to execute the test.

For each step, identify:
1. action: One of [navigate, click, type, select, hover, scroll, wait, screenshot, assert, execute_js]
2. url: For navigate action, the URL to go to
3. text: For type action, the text to input
4. selector_hint: Human-readable description of the target element (for click, type, select, hover actions)
5. assertion_type: For assert action, one of [text_contains, text_equals, element_visible, element_exists, url_contains, url_equals, title_contains, title_equals]
6. expected_value: For assert action, the expected value
7. is_key_step: Whether this step is critical and should require user confirmation (true for important actions like submit, delete, etc.)
8. description: Brief description of what this step does

Respond with a JSON array of step objects.

Example input: "打开百度首页，在搜索框输入'Playwright'，点击搜索按钮，验证搜索结果页面标题包含'Playwright'"

Example output:
[
  {"action": "navigate", "url": "https://www.baidu.com", "description": "打开百度首页"},
  {"action": "type", "selector_hint": "搜索框/搜索输入框", "text": "Playwright", "description": "输入搜索关键词"},
  {"action": "click", "selector_hint": "搜索按钮/百度一下按钮", "is_key_step": true, "description": "点击搜索"},
  {"action": "assert", "assertion_type": "title_contains", "expected_value": "Playwright", "description": "验证标题包含搜索词"}
]"""

LOCATE_ELEMENT_PROMPT = """You are a browser automation expert. Given an accessibility tree snapshot and a human-readable element description, identify the exact element reference.

The accessibility tree is structured with elements having:
- ref: Unique identifier for the element
- role: ARIA role (button, textbox, link, etc.)
- name: Accessible name
- Other attributes

Given the human description, find the best matching element and return its 'ref' value.

Respond with a JSON object:
{
  "ref": "the element reference",
  "reasoning": "brief explanation of why this element was chosen",
  "confidence": 0.0-1.0
}

If no matching element is found, respond:
{
  "ref": null,
  "reasoning": "explanation of why no match was found",
  "confidence": 0
}"""


class LLMClient:
    """Client for LLM API interactions."""
    
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize LLM client.
        
        Args:
            api_key: API key (defaults to settings)
            base_url: Base URL for API (defaults to settings)
            model: Model name (defaults to settings)
        """
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
    
    async def parse_testcase(self, description: str) -> list[TestStep]:
        """Parse natural language test description into structured steps.
        
        Args:
            description: Natural language test case description
            
        Returns:
            List of parsed TestStep objects
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PARSE_TESTCASE_PROMPT},
                {"role": "user", "content": description},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        if not content:
            return []
        
        try:
            data = json.loads(content)
            steps_data = []
            
            # Case 1: Direct list
            if isinstance(data, list):
                steps_data = data
            
            # Case 2: Dict with specific keys
            elif isinstance(data, dict):
                # Try to find a list of steps in the dictionary
                found_steps = False
                
                # 1. Check standard keys
                for key in ["steps", "test_steps", "actions", "output", "result", "items"]:
                    if key in data and isinstance(data[key], list):
                        steps_data = data[key]
                        found_steps = True
                        break
                
                # 2. Check for keys containing specific words (case insensitive) if not found
                if not found_steps:
                    for key, value in data.items():
                        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and "action" in value[0]:
                            k = key.lower()
                            if "steps" in k or "output" in k or "result" in k or "json" in k or "输出" in k:
                                steps_data = value
                                found_steps = True
                                break
                
                # 3. If still not found, just take the first list that looks like steps
                if not found_steps:
                    for value in data.values():
                        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and "action" in value[0]:
                            steps_data = value
                            found_steps = True
                            break
                
                # 4. Fallback: treat the dict itself as a single step if it has an action
                if not found_steps and "action" in data:
                    steps_data = [data]
            
            if not steps_data:
                return []
            
            steps = []
            for step_data in steps_data:
                # Convert action string to enum
                action_str = step_data.get("action", "").lower()
                try:
                    action = ActionType(action_str)
                except ValueError:
                    continue  # Skip invalid actions
                
                # Convert assertion type if present
                assertion_type = None
                if step_data.get("assertion_type"):
                    try:
                        assertion_type = AssertionType(step_data["assertion_type"])
                    except ValueError:
                        pass
                
                step = TestStep(
                    action=action,
                    url=step_data.get("url"),
                    text=step_data.get("text"),
                    selector_hint=step_data.get("selector_hint"),
                    assertion_type=assertion_type,
                    expected_value=step_data.get("expected_value"),
                    is_key_step=step_data.get("is_key_step", False),
                    description=step_data.get("description"),
                )
                steps.append(step)
            
            return steps
            
        except json.JSONDecodeError:
            return []
    
    async def locate_element(
        self,
        accessibility_snapshot: str,
        element_description: str,
    ) -> dict[str, Any]:
        """Locate an element in the accessibility tree.
        
        Args:
            accessibility_snapshot: The accessibility tree snapshot as text
            element_description: Human-readable description of the target element
            
        Returns:
            Dict with ref, reasoning, and confidence
        """
        user_message = f"""Accessibility Tree:
{accessibility_snapshot}

Element to find: {element_description}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": LOCATE_ELEMENT_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        if not content:
            return {"ref": None, "reasoning": "Empty response", "confidence": 0}
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"ref": None, "reasoning": "Invalid JSON response", "confidence": 0}
    
    async def reason_next_action(
        self,
        test_step: TestStep,
        accessibility_snapshot: str,
        previous_context: str | None = None,
    ) -> dict[str, Any]:
        """Reason about the next action to take.
        
        Args:
            test_step: The current test step
            accessibility_snapshot: Current page accessibility tree
            previous_context: Context from previous steps
            
        Returns:
            Dict with action details and reasoning
        """
        system_prompt = """You are a browser automation expert. Given a test step and the current page accessibility tree, determine the exact action to take.

Respond with a JSON object containing:
{
  "action": "the action type",
  "element_ref": "the element reference to interact with (if applicable)",
  "value": "value to use (for type, select actions)",
  "reasoning": "explanation of your decision",
  "confidence": 0.0-1.0
}"""

        user_message = f"""Test Step: {test_step.model_dump_json()}

Accessibility Tree:
{accessibility_snapshot}

{"Previous Context: " + previous_context if previous_context else ""}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        if not content:
            return {"action": None, "reasoning": "Empty response", "confidence": 0}
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"action": None, "reasoning": "Invalid JSON response", "confidence": 0}
