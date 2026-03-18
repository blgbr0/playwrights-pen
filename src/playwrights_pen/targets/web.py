"""Web browser test target using Playwright MCP."""

from typing import Any

from pydantic import Field

from .base import TestTarget, TargetType, TargetConfig
from ..mcp.client import MCPClient


class WebTargetConfig(TargetConfig):
    """Configuration for Web browser testing."""
    
    name: str = Field(default="Web Browser", description="Target name")
    mcp_command: str = Field(default="npx", description="MCP server command")
    mcp_args: list[str] = Field(
        default=["@playwright/mcp@latest"],
        description="MCP server arguments"
    )
    browser: str = Field(
        default="chromium",
        description="Browser to use: chromium, firefox, webkit"
    )
    start_url: str | None = Field(
        default=None,
        description="Optional URL to open on startup"
    )


class WebTarget(TestTarget[WebTargetConfig]):
    """Web browser test target using Playwright MCP.
    
    This wraps the existing MCPClient to provide the TestTarget interface.
    """
    
    def __init__(self, config: WebTargetConfig | None = None) -> None:
        """Initialize web target.
        
        Args:
            config: Web target configuration
        """
        super().__init__(config or WebTargetConfig())
        self._mcp: MCPClient | None = None
        self._mcp_context = None
    
    @property
    def target_type(self) -> TargetType:
        """Return the type of this target."""
        return TargetType.WEB
    
    async def connect(self) -> None:
        """Launch browser and connect to MCP server."""
        if self._connected:
            return
        
        self._mcp = MCPClient(
            command=self.config.mcp_command,
            args=self.config.mcp_args,
            headless=self.config.headless,
        )
        
        # Enter the MCP context
        self._mcp_context = self._mcp.connect()
        await self._mcp_context.__aenter__()
        self._connected = True
        
        # Navigate to start URL if specified
        if self.config.start_url:
            await self.navigate(self.config.start_url)
    
    async def disconnect(self) -> None:
        """Close browser and disconnect from MCP server."""
        if not self._connected:
            return
        
        if self._mcp_context:
            await self._mcp_context.__aexit__(None, None, None)
            self._mcp_context = None
        
        self._mcp = None
        self._connected = False
    
    # ==================== Navigation ====================
    
    async def navigate(self, url: str) -> str:
        """Navigate to a URL."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.navigate(url)
    
    async def get_current_url(self) -> str:
        """Get the current URL."""
        # MCP doesn't have a direct method, use JS
        result = await self.execute_js("window.location.href")
        return str(result) if result else ""
    
    async def go_back(self) -> str:
        """Navigate back in history."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.go_back()
    
    async def go_forward(self) -> str:
        """Navigate forward in history."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.go_forward()
    
    async def reload(self) -> str:
        """Reload the current page."""
        await self.execute_js("location.reload()")
        return "Page reloaded"
    
    # ==================== Snapshots ====================
    
    async def get_snapshot(self) -> str:
        """Get accessibility tree snapshot for LLM element location."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.get_snapshot()
    
    # ==================== Element Interaction ====================
    
    async def click(self, element_ref: str, element_description: str | None = None) -> str:
        """Click an element."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.click(element_ref, element=element_description)
    
    async def type_text(
        self, 
        element_ref: str, 
        text: str, 
        element_description: str | None = None
    ) -> str:
        """Type text into an element."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.type(element_ref, text, element=element_description)
    
    async def fill(
        self,
        element_ref: str,
        text: str,
        element_description: str | None = None
    ) -> str:
        """Fill an input with text (clears existing content first)."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.fill(element_ref, text, element=element_description)
    
    async def select_option(
        self,
        element_ref: str,
        values: list[str],
        element_description: str | None = None
    ) -> str:
        """Select option(s) in a dropdown."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.select(element_ref, values, element=element_description)
    
    async def hover(self, element_ref: str, element_description: str | None = None) -> str:
        """Hover over an element."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.hover(element_ref, element=element_description)
    
    # ==================== Page Actions ====================
    
    async def scroll(self, direction: str = "down", amount: int | None = None) -> str:
        """Scroll the page."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        
        # Convert direction to coordinates
        if direction == "down":
            dx, dy = 0, amount or 500
        elif direction == "up":
            dx, dy = 0, -(amount or 500)
        elif direction == "right":
            dx, dy = amount or 500, 0
        elif direction == "left":
            dx, dy = -(amount or 500), 0
        else:
            dx, dy = 0, 500
        
        # Use JavaScript for scrolling
        await self.execute_js(f"window.scrollBy({dx}, {dy})")
        return f"Scrolled {direction}"
    
    async def wait(self, milliseconds: int) -> str:
        """Wait for a specified time."""
        import asyncio
        await asyncio.sleep(milliseconds / 1000)
        return f"Waited {milliseconds}ms"
    
    async def take_screenshot(self, filename: str | None = None) -> str:
        """Take a screenshot."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        return await self._mcp.screenshot(filename)
    
    # ==================== Assertions ====================
    
    async def get_page_title(self) -> str:
        """Get the page title."""
        result = await self.execute_js("document.title")
        return str(result) if result else ""
    
    async def get_text_content(self, element_ref: str | None = None) -> str:
        """Get text content of page or element."""
        if element_ref:
            # Would need element-specific JS or MCP method
            return await self.execute_js("document.body.innerText")
        else:
            return await self.execute_js("document.body.innerText")
    
    async def is_element_visible(self, element_ref: str) -> bool:
        """Check if element is visible."""
        # Use snapshot to check - if element is in snapshot, it's visible
        snapshot = await self.get_snapshot()
        return f"[ref={element_ref}]" in snapshot
    
    # ==================== JavaScript ====================
    
    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript in the browser context."""
        if not self._mcp:
            raise RuntimeError("Not connected")
        
        # Wrap script to return result
        wrapped = f"(() => {{ return {script}; }})()"
        result = await self._mcp.call_tool("browser_evaluate", {
            "expression": wrapped
        })
        
        return result
