"""MCP client for Playwright browser automation."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import settings


class MCPClient:
    """Client for Playwright MCP server interactions."""
    
    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        headless: bool | None = None,
    ) -> None:
        """Initialize MCP client.
        
        Args:
            command: Command to start MCP server (defaults to settings)
            args: Arguments for MCP command (defaults to settings)
            headless: Whether to run in headless mode (defaults to settings)
        """
        self.command = command or settings.mcp_command
        self.args = args or settings.mcp_args_list
        self.headless = headless if headless is not None else settings.browser_headless
        
        self._session: ClientSession | None = None
        self._read = None
        self._write = None
    
    @asynccontextmanager
    async def connect(self) -> AsyncGenerator["MCPClient", None]:
        """Connect to MCP server as async context manager.
        
        Usage:
            async with mcp_client.connect() as client:
                await client.navigate("https://example.com")
        """
        # Add headless argument if needed
        args = self.args.copy()
        if self.headless:
            args.append("--headless")
        
        # Ensure MCP knows where to find browsers
        import os
        env = os.environ.copy()
        
        # Default user cache for playwright
        browser_path = os.path.expanduser("~/.cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
        
        # Explicitly point to the chromium executable
        # Note: Version specific, but better than failing. We try to find it dynamically.
        chromium_path = os.path.join(browser_path, "chromium-1208", "chrome-linux64", "chrome")
        if os.path.exists(chromium_path):
            env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = chromium_path
        
        server_params = StdioServerParameters(
            command=self.command,
            args=args,
            env=env,
        )
        
        async with stdio_client(server_params) as (read, write):
            self._read = read
            self._write = write
            async with ClientSession(read, write) as session:
                self._session = session
                await session.initialize()
                yield self
                self._session = None
    
    def _ensure_connected(self) -> ClientSession:
        """Ensure we have an active session."""
        if self._session is None:
            raise RuntimeError("MCP client not connected. Use 'async with client.connect():'")
        return self._session
    
    async def call_tool(self, name: str, **kwargs: Any) -> Any:
        """Call an MCP tool.
        
        Args:
            name: Tool name
            **kwargs: Tool arguments
            
        Returns:
            Tool result
        """
        session = self._ensure_connected()
        result = await session.call_tool(name, arguments=kwargs)
        return result
    
    # ==================== Navigation ====================
    
    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL.
        
        Args:
            url: URL to navigate to
            
        Returns:
            Navigation result
        """
        result = await self.call_tool("browser_navigate", url=url)
        return {"success": True, "content": result.content if result else None}
    
    async def go_back(self) -> dict[str, Any]:
        """Navigate back in history."""
        result = await self.call_tool("browser_navigate_back")
        return {"success": True, "content": result.content if result else None}
    
    async def go_forward(self) -> dict[str, Any]:
        """Navigate forward in history."""
        result = await self.call_tool("browser_evaluate", function="window.history.forward()")
        return {"success": True, "content": result.content if result else None}
    
    async def reload(self) -> dict[str, Any]:
        """Reload the page."""
        result = await self.call_tool("browser_evaluate", function="window.location.reload()")
        return {"success": True, "content": result.content if result else None}
    
    # ==================== Snapshot ====================
    
    async def get_snapshot(self) -> str:
        """Get the accessibility tree snapshot.
        
        Returns:
            Accessibility tree as text
        """
        result = await self.call_tool("browser_snapshot")
        if result and result.content:
            # Extract text content from result
            for item in result.content:
                if hasattr(item, "text"):
                    return item.text
        return ""
    
    # ==================== Interactions ====================
    
    async def click(
        self,
        ref: str,
        element: str | None = None,
        double_click: bool = False,
        button: str = "left",
    ) -> dict[str, Any]:
        """Click on an element.
        
        Args:
            ref: Element reference from accessibility tree
            element: Human-readable element description
            double_click: Whether to double-click
            button: Mouse button (left, right, middle)
            
        Returns:
            Click result
        """
        kwargs = {"ref": ref}
        if element:
            kwargs["element"] = element
        if double_click:
            kwargs["doubleClick"] = True
        if button != "left":
            kwargs["button"] = button
        
        result = await self.call_tool("browser_click", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    async def type(
        self,
        ref: str,
        text: str,
        element: str | None = None,
        submit: bool = False,
    ) -> dict[str, Any]:
        """Type text into an element.
        
        Args:
            ref: Element reference from accessibility tree
            text: Text to type
            element: Human-readable element description
            submit: Whether to submit after typing (press Enter)
            
        Returns:
            Type result
        """
        kwargs = {"ref": ref, "text": text}
        if element:
            kwargs["element"] = element
        if submit:
            kwargs["submit"] = True
        
        result = await self.call_tool("browser_type", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    async def select(
        self,
        ref: str,
        values: list[str],
        element: str | None = None,
    ) -> dict[str, Any]:
        """Select option(s) in a dropdown.
        
        Args:
            ref: Element reference
            values: Values to select
            element: Human-readable element description
            
        Returns:
            Select result
        """
        kwargs = {"ref": ref, "values": values}
        if element:
            kwargs["element"] = element
        
        result = await self.call_tool("browser_select_option", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    async def hover(self, ref: str, element: str | None = None) -> dict[str, Any]:
        """Hover over an element.
        
        Args:
            ref: Element reference
            element: Human-readable element description
            
        Returns:
            Hover result
        """
        kwargs = {"ref": ref}
        if element:
            kwargs["element"] = element
        
        result = await self.call_tool("browser_hover", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    async def scroll(
        self,
        direction: str = "down",
        amount: int | None = None,
    ) -> dict[str, Any]:
        """Scroll the page.
        
        Args:
            direction: Scroll direction (up, down, left, right)
            amount: Scroll amount in pixels
            
        Returns:
            Scroll result
        """
        # Map direction to keyboard key
        key_map = {
            "down": "PageDown",
            "up": "PageUp",
            "left": "Home",
            "right": "End",
        }
        key = key_map.get(direction, "PageDown")
        
        # If amount specified, use JavaScript scrollBy
        if amount:
            dx = amount if direction == "right" else (-amount if direction == "left" else 0)
            dy = amount if direction == "down" else (-amount if direction == "up" else 0)
            result = await self.call_tool(
                "browser_evaluate",
                function=f"window.scrollBy({dx}, {dy})",
            )
        else:
            result = await self.call_tool("browser_press_key", key=key)
        
        return {"success": True, "content": result.content if result else None}
    
    # ==================== JavaScript ====================
    
    async def evaluate(self, function: str, ref: str | None = None) -> dict[str, Any]:
        """Execute JavaScript.
        
        Args:
            function: JavaScript function to execute
            ref: Optional element reference to pass to function
            
        Returns:
            Evaluation result
        """
        kwargs = {"function": function}
        if ref:
            kwargs["ref"] = ref
        
        result = await self.call_tool("browser_evaluate", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    # ==================== Utilities ====================
    
    async def screenshot(self, filename: str | None = None) -> dict[str, Any]:
        """Take a screenshot.
        
        Args:
            filename: Optional filename to save to
            
        Returns:
            Screenshot result (may include base64 data)
        """
        kwargs = {}
        if filename:
            kwargs["filename"] = filename
        
        result = await self.call_tool("browser_take_screenshot", **kwargs)
        return {"success": True, "content": result.content if result else None}
    
    async def wait(self, time_ms: int = 1000) -> dict[str, Any]:
        """Wait for a specific time.
        
        Args:
            time_ms: Time to wait in milliseconds
            
        Returns:
            Wait result
        """
        result = await self.call_tool("browser_wait_for", time=time_ms)
        return {"success": True, "content": result.content if result else None}
    
    async def close(self) -> dict[str, Any]:
        """Close the browser."""
        result = await self.call_tool("browser_close")
        return {"success": True, "content": result.content if result else None}
    
    async def get_console_messages(self, level: str = "info") -> list[str]:
        """Get console messages.
        
        Args:
            level: Minimum level (info, warn, error)
            
        Returns:
            List of console messages
        """
        result = await self.call_tool("browser_console_messages", level=level)
        if result and result.content:
            for item in result.content:
                if hasattr(item, "text"):
                    return item.text.split("\n")
        return []
