"""Data placeholder resolution for interactive test data handling."""

import os
import re
from typing import Callable, Awaitable

from ..config import DataInputMode
from ..models.step import TestStep, DataPlaceholder


# Regex pattern for placeholder syntax: {{variable_name}}
PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def extract_placeholders(text: str) -> list[str]:
    """Extract placeholder variable names from text.
    
    Args:
        text: Text containing placeholders like {{username}}
        
    Returns:
        List of placeholder variable names
    """
    return PLACEHOLDER_PATTERN.findall(text)


def detect_step_placeholders(step: TestStep) -> dict[str, DataPlaceholder]:
    """Detect all placeholders in a test step.
    
    Scans url, text, selector_hint, expected_value for {{variable}} patterns.
    
    Args:
        step: Test step to scan
        
    Returns:
        Dictionary of placeholder name to DataPlaceholder config
    """
    placeholders = {}
    
    # Fields that can contain placeholders
    fields_to_scan = [
        step.url,
        step.text,
        step.selector_hint,
        step.expected_value,
    ]
    
    for field_value in fields_to_scan:
        if field_value:
            for var_name in extract_placeholders(field_value):
                if var_name not in placeholders:
                    # Create placeholder with default config
                    placeholders[var_name] = DataPlaceholder(
                        name=var_name,
                        label=_generate_label(var_name),
                        mode=DataInputMode.PROMPT.value,
                        is_sensitive=_is_sensitive(var_name),
                    )
    
    return placeholders


def _generate_label(var_name: str) -> str:
    """Generate human-readable label from variable name.
    
    Examples:
        username -> "请输入 Username"
        user_password -> "请输入 User Password"
    """
    # Convert snake_case to Title Case
    words = var_name.replace("_", " ").title()
    return f"请输入 {words}"


def _is_sensitive(var_name: str) -> bool:
    """Check if variable name suggests sensitive data.
    
    Args:
        var_name: Variable name to check
        
    Returns:
        True if likely sensitive (password, token, secret, etc.)
    """
    sensitive_keywords = [
        "password", "passwd", "pwd", "secret", "token",
        "key", "credential", "auth", "api_key", "apikey",
    ]
    var_lower = var_name.lower()
    return any(kw in var_lower for kw in sensitive_keywords)


def substitute_placeholders(text: str, resolved_values: dict[str, str]) -> str:
    """Substitute placeholders with resolved values.
    
    Args:
        text: Text containing placeholders
        resolved_values: Dictionary of variable name to resolved value
        
    Returns:
        Text with placeholders substituted
    """
    def replace(match):
        var_name = match.group(1)
        return resolved_values.get(var_name, match.group(0))
    
    return PLACEHOLDER_PATTERN.sub(replace, text)


class DataResolver:
    """Resolves data placeholders during test execution.
    
    Supports three modes:
    - PRESET: Read from environment variables or default values
    - PROMPT: Ask user for input at runtime
    - GENERATE: Use LLM to generate test data
    """
    
    def __init__(
        self,
        prompt_callback: Callable[[str, str, bool], Awaitable[str]] | None = None,
        generate_callback: Callable[[str, str], Awaitable[str]] | None = None,
    ) -> None:
        """Initialize data resolver.
        
        Args:
            prompt_callback: Async function to prompt user for input.
                Signature: (var_name, label, is_sensitive) -> value
            generate_callback: Async function to generate test data via LLM.
                Signature: (var_name, hint) -> value
        """
        self.prompt_callback = prompt_callback
        self.generate_callback = generate_callback
        self._resolved_cache: dict[str, str] = {}
    
    async def resolve_placeholder(self, placeholder: DataPlaceholder) -> str:
        """Resolve a single placeholder.
        
        Args:
            placeholder: Placeholder configuration
            
        Returns:
            Resolved value
            
        Raises:
            ValueError: If resolution fails
        """
        # Check cache first
        if placeholder.name in self._resolved_cache:
            return self._resolved_cache[placeholder.name]
        
        mode = DataInputMode(placeholder.mode)
        value: str | None = None
        
        if mode == DataInputMode.PRESET:
            value = self._resolve_preset(placeholder)
        elif mode == DataInputMode.PROMPT:
            value = await self._resolve_prompt(placeholder)
        elif mode == DataInputMode.GENERATE:
            value = await self._resolve_generate(placeholder)
        
        if value is None:
            raise ValueError(f"Failed to resolve placeholder: {placeholder.name}")
        
        # Cache and store in placeholder
        self._resolved_cache[placeholder.name] = value
        placeholder.resolved_value = value
        
        return value
    
    def _resolve_preset(self, placeholder: DataPlaceholder) -> str | None:
        """Resolve placeholder from preset value or environment variable."""
        # Priority: env var > default value
        if placeholder.env_var:
            value = os.environ.get(placeholder.env_var)
            if value:
                return value
        
        if placeholder.default_value:
            return placeholder.default_value
        
        # Try common naming conventions for env var
        env_var_name = f"TEST_{placeholder.name.upper()}"
        return os.environ.get(env_var_name)
    
    async def _resolve_prompt(self, placeholder: DataPlaceholder) -> str | None:
        """Resolve placeholder by prompting user."""
        if not self.prompt_callback:
            raise RuntimeError(
                f"Prompt callback not configured, cannot resolve: {placeholder.name}"
            )
        
        return await self.prompt_callback(
            placeholder.name,
            placeholder.label,
            placeholder.is_sensitive,
        )
    
    async def _resolve_generate(self, placeholder: DataPlaceholder) -> str | None:
        """Resolve placeholder by generating with LLM."""
        if not self.generate_callback:
            raise RuntimeError(
                f"Generate callback not configured, cannot resolve: {placeholder.name}"
            )
        
        hint = placeholder.generate_hint or f"Generate a valid value for {placeholder.name}"
        return await self.generate_callback(placeholder.name, hint)
    
    async def resolve_step(self, step: TestStep) -> TestStep:
        """Resolve all placeholders in a test step.
        
        Args:
            step: Test step with placeholder definitions
            
        Returns:
            Test step with placeholders resolved and substituted
        """
        if not step.data_placeholders:
            return step
        
        # Resolve all placeholders
        resolved_values = {}
        for name, placeholder in step.data_placeholders.items():
            resolved_values[name] = await self.resolve_placeholder(placeholder)
        
        # Substitute in step fields
        step_copy = step.model_copy(deep=True)
        
        if step_copy.url:
            step_copy.url = substitute_placeholders(step_copy.url, resolved_values)
        if step_copy.text:
            step_copy.text = substitute_placeholders(step_copy.text, resolved_values)
        if step_copy.selector_hint:
            step_copy.selector_hint = substitute_placeholders(
                step_copy.selector_hint, resolved_values
            )
        if step_copy.expected_value:
            step_copy.expected_value = substitute_placeholders(
                step_copy.expected_value, resolved_values
            )
        
        return step_copy
    
    def clear_cache(self) -> None:
        """Clear resolved values cache."""
        self._resolved_cache.clear()
    
    def set_preset_value(self, name: str, value: str) -> None:
        """Manually set a preset value.
        
        Useful for batch runs or API-based execution.
        
        Args:
            name: Placeholder variable name
            value: Value to use
        """
        self._resolved_cache[name] = value
