"""Electron application test target using Playwright Electron API."""

import asyncio
import os
from pathlib import Path
from typing import Any

from pydantic import Field

from .base import TestTarget, TargetType, TargetConfig


class ElectronTargetConfig(TargetConfig):
    """Configuration for Electron application testing."""
    
    name: str = Field(default="Electron App", description="Target name")
    
    # Electron executable path (for packaged apps)
    executable_path: str | None = Field(
        default=None,
        description="Path to packaged Electron executable (.exe, .app, AppImage)"
    )
    
    # Project path (for development mode)
    project_path: str | None = Field(
        default=None,
        description="Path to Electron project directory (for dev mode)"
    )
    
    # Start command (for development mode)
    start_command: str = Field(
        default="npm start",
        description="Command to start Electron app in dev mode"
    )
    
    # Additional arguments
    args: list[str] = Field(
        default_factory=list,
        description="Additional arguments to pass to Electron"
    )
    
    # Environment variables
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for Electron process"
    )
    
    # Wait time for app to start
    startup_timeout_ms: int = Field(
        default=30000,
        description="Timeout for app startup in milliseconds"
    )


class ElectronTarget(TestTarget[ElectronTargetConfig]):
    """Electron application test target using Playwright CDP connection.
    
    Supports two modes:
    1. Packaged app: Provide executable_path to a .exe/.app/AppImage
    2. Development: Provide project_path and start_command
    
    Uses Chrome DevTools Protocol (CDP) to connect to a manually launched
    Electron instance.
    """
    
    def __init__(self, config: ElectronTargetConfig | None = None) -> None:
        """Initialize Electron target.
        
        Args:
            config: Electron target configuration
        """
        super().__init__(config or ElectronTargetConfig())
        self._electron_process = None  # subprocess.Popen
        self._browser = None  # CDP Browser instance
        self._page = None  # Main window page
        self._playwright = None
        self._cdp_port = 9222
    
    @property
    def target_type(self) -> TargetType:
        """Return the type of this target."""
        return TargetType.ELECTRON
    
    async def connect(self) -> None:
        """Launch Electron application and connect via CDP."""
        if self._connected:
            return
            
        import socket
        import subprocess
        
        # Check if port is already in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sock.connect_ex(('127.0.0.1', self._cdp_port)) == 0:
            sock.close()
            # Port in use, find another one
            import random
            self._cdp_port = random.randint(9223, 9999)
        else:
            sock.close()
        
        # Import playwright
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        
        # Launch app
        if self.config.executable_path:
            await self._launch_packaged_app()
        elif self.config.project_path:
            await self._launch_dev_app()
        else:
            raise ValueError("Either executable_path or project_path must be set")
            
        # Wait for CDP endpoint
        import time
        max_retries = 30
        connected = False
        
        for i in range(max_retries):
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self._cdp_port}")
                connected = True
                break
            except Exception:
                await asyncio.sleep(1)
                
        if not connected:
            if self._electron_process:
                self._electron_process.terminate()
            raise RuntimeError(f"Failed to connect to Electron via CDP on port {self._cdp_port} after 30 seconds")
            
        # Get first window page
        contexts = self._browser.contexts
        if not contexts:
            await asyncio.sleep(2)  # Give it a moment to initialize default context
            contexts = self._browser.contexts
            
        if contexts and contexts[0].pages:
            self._page = contexts[0].pages[0]
        else:
            # Try to grab wait for the first page
            context = contexts[0] if contexts else self._browser.contexts[0]
            if not context.pages:
                self._page = await context.new_page()
            else:
                self._page = context.pages[0]
                
        self._connected = True
    
    async def _launch_packaged_app(self) -> None:
        """Launch a packaged Electron application."""
        import subprocess
        
        exec_path = Path(self.config.executable_path).expanduser().resolve()
        
        if not exec_path.exists():
            raise FileNotFoundError(f"Electron executable not found: {exec_path}")
        
        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.env)
        env.pop("ELECTRON_RUN_AS_NODE", None)
        
        cmd = [str(exec_path), f'--remote-debugging-port={self._cdp_port}'] + self.config.args
        self._electron_process = subprocess.Popen(cmd, env=env)
    
    async def _launch_dev_app(self) -> None:
        """Launch an Electron app in development mode."""
        import subprocess
        
        project_path = Path(self.config.project_path).expanduser().resolve()
        
        if not project_path.exists():
            raise FileNotFoundError(f"Project directory not found: {project_path}")
        
        # Find main entry point
        package_json = project_path / "package.json"
        if not package_json.exists():
            raise FileNotFoundError(f"package.json not found in {project_path}")
        
        import json
        with open(package_json) as f:
            pkg = json.load(f)
        
        main = pkg.get("main", "index.js")
        main_path = project_path / main
        
        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.env)
        env["ELECTRON_ENABLE_LOGGING"] = "1"
        env.pop("ELECTRON_RUN_AS_NODE", None)
        
        # Find node_modules electron
        electron_path = project_path / "node_modules" / ".bin" / "electron"
        if os.name == 'nt' and not str(electron_path).endswith('.cmd'):
            electron_path = Path(str(electron_path) + '.cmd')
            
        if not electron_path.exists():
            # Try global electron
            electron_path = Path(r"npx.cmd" if os.name == 'nt' else "npx")
            cmd = [str(electron_path), "electron", ".", f'--remote-debugging-port={self._cdp_port}'] + self.config.args
        else:
            cmd = [str(electron_path), ".", f'--remote-debugging-port={self._cdp_port}'] + self.config.args
            
        self._electron_process = subprocess.Popen(
            cmd, 
            cwd=str(project_path), 
            env=env
        )
    
    async def disconnect(self) -> None:
        """Close Electron application."""
        if not self._connected:
            return
        
        if self._browser:
            await self._browser.close()
            self._browser = None
            
        if self._electron_process:
            self._electron_process.terminate()
            self._electron_process = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        self._page = None
        self._connected = False
    
    def _ensure_page(self):
        """Ensure page is available."""
        if not self._page:
            raise RuntimeError("Not connected or no window available")
        return self._page
    
    # ==================== Navigation ====================
    
    async def navigate(self, url: str) -> str:
        """Navigate to a URL (or load local file)."""
        page = self._ensure_page()
        await page.goto(url)
        return f"Navigated to {url}"
    
    async def get_current_url(self) -> str:
        """Get the current URL."""
        page = self._ensure_page()
        return page.url
    
    async def go_back(self) -> str:
        """Navigate back in history."""
        page = self._ensure_page()
        await page.go_back()
        return "Navigated back"
    
    async def go_forward(self) -> str:
        """Navigate forward in history."""
        page = self._ensure_page()
        await page.go_forward()
        return "Navigated forward"
    
    async def reload(self) -> str:
        """Reload the current page."""
        page = self._ensure_page()
        await page.reload()
        return "Page reloaded"
    
    # ==================== Snapshots ====================
    
    async def get_snapshot(self) -> str:
        """Get accessibility tree snapshot for LLM element location.
        
        This builds a simplified DOM tree of interactive elements and text nodes,
        and injects data-ref attributes into the DOM for later interaction.
        """
        page = self._ensure_page()
        
        script = """
        () => {
            let counter = 1;
            const lines = [];
            
            function isVisible(el) {
                if (!el || el.nodeType !== 1) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            }
            
            function processNode(node, indent) {
                if (!isVisible(node)) return;
                
                const tagName = node.tagName.toLowerCase();
                const interactiveTags = ['a', 'button', 'input', 'select', 'textarea'];
                const role = node.getAttribute('role') || tagName;
                
                let isInteractive = interactiveTags.includes(tagName) || node.hasAttribute('onclick') || node.getAttribute('role');
                
                let text = '';
                if (tagName === 'input' || tagName === 'textarea') {
                    text = node.value || node.placeholder || node.name || '';
                } else if (node.innerText) {
                    text = node.innerText.trim().split('\\n')[0];
                }
                
                // Truncate long text
                if (text && text.length > 50) {
                    text = text.substring(0, 47) + '...';
                }
                
                let outputLine = null;
                if (isInteractive || (text && !['div', 'main', 'body', 'html', 'form'].includes(tagName))) {
                    const ref = 'e' + counter++;
                    node.setAttribute('data-ref', ref);
                    
                    let line = '  '.repeat(indent) + `- ${role}`;
                    if (text) line += ` "${text}"`;
                    line += ` [ref=${ref}]`;
                    lines.push(line);
                    outputLine = true;
                }
                
                // Only process children if this wasn't an interactive leaf node
                if (!isInteractive || ['div', 'form', 'main', 'body', 'html', 'nav', 'header', 'footer'].includes(tagName)) {
                    for (const child of node.children) {
                        processNode(child, outputLine ? indent + 1 : indent);
                    }
                }
            }
            
            processNode(document.body, 0);
            return lines.join('\\n');
        }
        """
        return await page.evaluate(script)
    
    # ==================== Element Interaction ====================
    
    async def click(self, element_ref: str, element: str | None = None, **kwargs) -> str:
        """Click an element by ref or description."""
        page = self._ensure_page()
        
        await page.locator(f'[data-ref="{element_ref}"]').click()
        return f"Clicked element {element_ref}"
    
    async def type_text(
        self, 
        element_ref: str, 
        text: str, 
        element: str | None = None,
        **kwargs
    ) -> str:
        """Type text into an element."""
        page = self._ensure_page()
        
        await page.locator(f'[data-ref="{element_ref}"]').fill(text)
        return f"Typed '{text}'"
    
    async def fill(
        self,
        element_ref: str,
        text: str,
        element: str | None = None,
        **kwargs
    ) -> str:
        """Fill an input with text."""
        page = self._ensure_page()
        
        await page.locator(f'[data-ref="{element_ref}"]').fill(text)
        return f"Filled with '{text}'"
    
    async def select_option(
        self,
        element_ref: str,
        values: list[str],
        element: str | None = None,
        **kwargs
    ) -> str:
        """Select option(s) in a dropdown."""
        page = self._ensure_page()
        
        await page.locator(f'[data-ref="{element_ref}"]').select_option(values)
        return f"Selected {values}"
    
    async def hover(self, element_ref: str, element: str | None = None, **kwargs) -> str:
        """Hover over an element."""
        page = self._ensure_page()
        
        await page.locator(f'[data-ref="{element_ref}"]').hover()
        return f"Hovered over {element_ref}"
    
    # ==================== Page Actions ====================
    
    async def scroll(self, direction: str = "down", amount: int | None = None) -> str:
        """Scroll the page."""
        page = self._ensure_page()
        
        pixels = amount or 500
        if direction == "down":
            await page.mouse.wheel(0, pixels)
        elif direction == "up":
            await page.mouse.wheel(0, -pixels)
        elif direction == "right":
            await page.mouse.wheel(pixels, 0)
        elif direction == "left":
            await page.mouse.wheel(-pixels, 0)
        
        return f"Scrolled {direction} by {pixels}px"
    
    async def wait(self, milliseconds: int) -> str:
        """Wait for a specified time."""
        await asyncio.sleep(milliseconds / 1000)
        return f"Waited {milliseconds}ms"
    
    async def take_screenshot(self, filename: str | None = None) -> str:
        """Take a screenshot."""
        page = self._ensure_page()
        
        path = filename or f"screenshot_{asyncio.get_event_loop().time()}.png"
        await page.screenshot(path=path)
        return path
    
    # ==================== Assertions ====================
    
    async def get_page_title(self) -> str:
        """Get the page title."""
        page = self._ensure_page()
        return await page.title()
    
    async def get_text_content(self, element_ref: str | None = None) -> str:
        """Get text content of page or element."""
        page = self._ensure_page()
        return await page.locator('body').inner_text()
    
    async def is_element_visible(self, element_ref: str) -> bool:
        """Check if element is visible."""
        snapshot = await self.get_snapshot()
        return f"[ref={element_ref}]" in snapshot
    
    # ==================== JavaScript ====================
    
    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript in the Electron renderer context."""
        page = self._ensure_page()
        return await page.evaluate(script)
    
    # ==================== Electron-Specific ====================
    
    async def get_window_count(self) -> int:
        """Get the number of open windows."""
        if not self._electron_app:
            return 0
        return len(self._electron_app.windows())
    
    async def switch_to_window(self, index: int) -> None:
        """Switch to a different window by index."""
        if not self._electron_app:
            raise RuntimeError("Not connected")
        
        windows = self._electron_app.windows()
        if 0 <= index < len(windows):
            self._page = windows[index]
        else:
            raise IndexError(f"Window index {index} out of range")
    
    async def evaluate_in_main(self, expression: str) -> Any:
        """Evaluate JavaScript in the main process.
        
        Note: This requires the Electron app to expose IPC handlers.
        """
        if not self._electron_app:
            raise RuntimeError("Not connected")
        
        return await self._electron_app.evaluate(expression)

    # ==================== MCPClient Compatibility Aliases ====================
    
    async def type(self, ref: str, text: str, element: str | None = None, submit: bool = False) -> dict[str, Any]:
        """Alias for type_text to match MCPClient interface."""
        result = await self.type_text(ref, text, element)
        if submit:
            page = self._ensure_page()
            await page.keyboard.press("Enter")
        return {"success": True, "content": result}
        
    async def select(self, ref: str, values: list[str], element: str | None = None) -> dict[str, Any]:
        """Alias for select_option to match MCPClient interface."""
        result = await self.select_option(ref, values[0] if values else "", element)
        return {"success": True, "content": result}
        
    async def screenshot(self, filename: str | None = None) -> dict[str, Any]:
        """Alias for take_screenshot to match MCPClient interface."""
        result = await self.take_screenshot(filename)
        return {"success": True, "content": result}
        
    async def evaluate(self, function: str, ref: str | None = None) -> dict[str, Any]:
        """Alias for execute_js to match MCPClient interface."""
        # Wrap function execution
        page = self._ensure_page()
        result = await page.evaluate(function)
        return {"success": True, "content": str(result)}
