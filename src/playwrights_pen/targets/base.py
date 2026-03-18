"""Base test target abstraction for multi-platform support."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    """Types of test targets supported."""
    
    WEB = "web"          # Web browser (Playwright)
    ELECTRON = "electron"  # Electron application (Playwright Electron)
    MOBILE = "mobile"     # Mobile device/emulator (Appium)


class TargetConfig(BaseModel):
    """Base configuration for test targets."""
    
    name: str = Field(default="Default Target", description="Human-readable name")
    headless: bool = Field(default=False, description="Run in headless mode")
    timeout_ms: int = Field(default=30000, description="Default timeout in milliseconds")


ConfigT = TypeVar("ConfigT", bound=TargetConfig)


class TestTarget(ABC, Generic[ConfigT]):
    """Abstract base class for test targets.
    
    A test target represents a platform that can be automated:
    - Web browser (Chrome, Firefox, etc.)
    - Electron application
    - Mobile device (Android, iOS)
    
    Each target provides a unified interface for:
    - Navigation
    - Element interaction (click, type, etc.)
    - Snapshots (for LLM element location)
    - Screenshots/recording
    """
    
    def __init__(self, config: ConfigT) -> None:
        """Initialize test target with configuration.
        
        Args:
            config: Target-specific configuration
        """
        self.config = config
        self._connected = False
    
    @property
    @abstractmethod
    def target_type(self) -> TargetType:
        """Return the type of this target."""
        ...
    
    @property
    def is_connected(self) -> bool:
        """Check if target is currently connected."""
        return self._connected
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the target.
        
        For web: launch browser
        For electron: launch application
        For mobile: connect to device/emulator
        """
        ...
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the target."""
        ...
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator["TestTarget[ConfigT]", None]:
        """Context manager for test session.
        
        Usage:
            async with target.session() as t:
                await t.navigate("https://example.com")
        """
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
    
    # ==================== Navigation ====================
    
    @abstractmethod
    async def navigate(self, url: str) -> str:
        """Navigate to a URL.
        
        Args:
            url: Target URL
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def get_current_url(self) -> str:
        """Get the current URL."""
        ...
    
    @abstractmethod
    async def go_back(self) -> str:
        """Navigate back in history."""
        ...
    
    @abstractmethod
    async def go_forward(self) -> str:
        """Navigate forward in history."""
        ...
    
    @abstractmethod
    async def reload(self) -> str:
        """Reload the current page."""
        ...
    
    # ==================== Snapshots ====================
    
    @abstractmethod
    async def get_snapshot(self) -> str:
        """Get accessibility tree snapshot for LLM element location.
        
        Returns:
            Text representation of the accessibility tree with element refs
        """
        ...
    
    # ==================== Element Interaction ====================
    
    @abstractmethod
    async def click(self, element_ref: str, element_description: str | None = None) -> str:
        """Click an element.
        
        Args:
            element_ref: Element reference from snapshot (e.g., "e15")
            element_description: Optional human-readable description
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def type_text(
        self, 
        element_ref: str, 
        text: str, 
        element_description: str | None = None
    ) -> str:
        """Type text into an element.
        
        Args:
            element_ref: Element reference from snapshot
            text: Text to type
            element_description: Optional human-readable description
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def fill(
        self,
        element_ref: str,
        text: str,
        element_description: str | None = None
    ) -> str:
        """Fill an input with text (clears existing content first).
        
        Args:
            element_ref: Element reference from snapshot
            text: Text to fill
            element_description: Optional human-readable description
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def select_option(
        self,
        element_ref: str,
        values: list[str],
        element_description: str | None = None
    ) -> str:
        """Select option(s) in a dropdown.
        
        Args:
            element_ref: Element reference from snapshot
            values: Values to select
            element_description: Optional human-readable description
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def hover(self, element_ref: str, element_description: str | None = None) -> str:
        """Hover over an element.
        
        Args:
            element_ref: Element reference from snapshot
            element_description: Optional human-readable description
            
        Returns:
            Result message
        """
        ...
    
    # ==================== Page Actions ====================
    
    @abstractmethod
    async def scroll(self, direction: str = "down", amount: int | None = None) -> str:
        """Scroll the page.
        
        Args:
            direction: "up", "down", "left", "right"
            amount: Pixels to scroll (None for page scroll)
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def wait(self, milliseconds: int) -> str:
        """Wait for a specified time.
        
        Args:
            milliseconds: Time to wait
            
        Returns:
            Result message
        """
        ...
    
    @abstractmethod
    async def take_screenshot(self, filename: str | None = None) -> str:
        """Take a screenshot.
        
        Args:
            filename: Optional filename to save to
            
        Returns:
            Path to screenshot or base64 data
        """
        ...
    
    # ==================== Assertions ====================
    
    @abstractmethod
    async def get_page_title(self) -> str:
        """Get the page title."""
        ...
    
    @abstractmethod
    async def get_text_content(self, element_ref: str | None = None) -> str:
        """Get text content of page or element.
        
        Args:
            element_ref: Optional element reference, None for full page
            
        Returns:
            Text content
        """
        ...
    
    @abstractmethod
    async def is_element_visible(self, element_ref: str) -> bool:
        """Check if element is visible.
        
        Args:
            element_ref: Element reference from snapshot
            
        Returns:
            True if visible
        """
        ...
    
    # ==================== JavaScript ====================
    
    @abstractmethod
    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript in the target context.
        
        Args:
            script: JavaScript code to execute
            
        Returns:
            Result of execution
        """
        ...
