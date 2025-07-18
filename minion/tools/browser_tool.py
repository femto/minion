"""
Browser tool for Minion.

This module provides browser functionality that can be used with the Minion framework.
It encapsulates browser-use functionality into a class-based implementation.
"""

import asyncio
import importlib.util
import json
import sys
import multiprocessing
from typing import Any, Dict, List, Optional, Union
from queue import Empty
from multiprocessing import Process, Queue

from pydantic import BaseModel, Field
from loguru import logger

# Constants
MAX_LENGTH = 128_000

# Valid browser actions
VALID_ACTIONS = {
    "navigate", "click", "input_text", "screenshot", "get_html",
    "get_text", "read_links", "execute_js", "scroll", "switch_tab",
    "new_tab", "close_tab", "refresh", "get_current_state"
}

class BrowserToolResult(BaseModel):
    """Result of a browser tool execution."""
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


class BrowserProcess:
    """Manages browser operations in a separate process."""
    def __init__(self, headless=False):
        self.command_queue = Queue()
        self.result_queue = Queue()
        self.process = None
        self.headless = headless
        self._start_process()

    def _start_process(self):
        """Start the browser process."""
        if self.process is None or not self.process.is_alive():
            self.process = Process(target=self._browser_worker, args=(self.command_queue, self.result_queue, self.headless))
            self.process.start()

    def _browser_worker(self, cmd_queue: Queue, result_queue: Queue, headless: bool):
        """Worker function that runs in a separate process."""
        try:
            # Import browser_use modules
            from browser_use import Browser as BrowserUseBrowser
            from browser_use import BrowserConfig
            from browser_use.browser.context import BrowserContext
            
            browser = None
            context = None
            
            try:
                # Initialize browser
                config = BrowserConfig(headless=headless)
                browser = BrowserUseBrowser(config)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                context = loop.run_until_complete(browser.new_context())
                
                while True:
                    try:
                        cmd = cmd_queue.get(timeout=1)
                        if cmd is None:  # Shutdown signal
                            break
                            
                        action = cmd.get('action')
                        if action not in VALID_ACTIONS:
                            result_queue.put({
                                'success': False,
                                'message': f'Invalid action: {action}'
                            })
                            continue

                        # Handle the action
                        result = loop.run_until_complete(self._handle_action(context, cmd))
                        result_queue.put(result)
                        
                    except Empty:
                        continue
                    except Exception as e:
                        result_queue.put({
                            'success': False,
                            'message': f'Error: {str(e)}'
                        })
                        
            finally:
                if context:
                    loop.run_until_complete(context.close())
                if browser:
                    loop.run_until_complete(browser.close())
                loop.close()
                
        except ImportError as e:
            result_queue.put({
                'success': False,
                'message': f'Error: browser_use package not available. {str(e)}'
            })

    async def _handle_action(self, context, cmd: Dict) -> Dict:
        """Handle a browser action."""
        action = cmd['action']
        try:
            if action == "navigate":
                page = await context.get_current_page()
                await page.goto(cmd['url'])
                return {'success': True, 'message': f"Navigated to {cmd['url']}"}
                
            elif action == "get_html":
                page = await context.get_current_page()
                html = await page.content()
                if len(html) > MAX_LENGTH:
                    html = html[:MAX_LENGTH] + "... (truncated)"
                return {'success': True, 'message': "HTML content retrieved", 'data': {'html': html}}

            elif action == "click":
                if cmd.get('index') is None:
                    return {'success': False, 'message': "Index is required for click action"}
                element = await context.get_dom_element_by_index(cmd['index'])
                if not element:
                    return {'success': False, 'message': f"Element with index {cmd['index']} not found"}
                await context._click_element_node(element)
                return {'success': True, 'message': f"Clicked element at index {cmd['index']}"}

            elif action == "input_text":
                if cmd.get('index') is None:
                    return {'success': False, 'message': "Index is required for input_text action"}
                if cmd.get('text') is None:
                    return {'success': False, 'message': "Text is required for input_text action"}
                element = await context.get_dom_element_by_index(cmd['index'])
                if not element:
                    return {'success': False, 'message': f"Element with index {cmd['index']} not found"}
                await context._input_text_element_node(element, cmd['text'])
                return {'success': True, 'message': f"Input text '{cmd['text']}' at index {cmd['index']}"}

            elif action == "screenshot":
                page = await context.get_current_page()
                screenshot = await page.screenshot()
                return {'success': True, 'message': "Screenshot captured", 'data': {"screenshot": screenshot}}

            elif action == "get_text":
                page = await context.get_current_page()
                text = await page.inner_text("body")
                if len(text) > MAX_LENGTH:
                    text = text[:MAX_LENGTH] + "... (truncated)"
                return {'success': True, 'message': "Text content retrieved", 'data': {"text": text}}

            elif action == "read_links":
                page = await context.get_current_page()
                elements = await page.query_selector_all("a")
                links = []
                for element in elements:
                    href = await element.get_attribute("href")
                    text = await element.inner_text()
                    if href:
                        links.append({"href": href, "text": text})
                return {'success': True, 'message': f"Found {len(links)} links", 'data': {"links": links}}

            elif action == "execute_js":
                if not cmd.get('script'):
                    return {'success': False, 'message': "Script is required for execute_js action"}
                page = await context.get_current_page()
                js_result = await page.evaluate(cmd['script'])
                return {'success': True, 'message': "JavaScript executed", 'data': {"result": str(js_result)}}

            elif action == "scroll":
                if cmd.get('scroll_amount') is None:
                    return {'success': False, 'message': "Scroll amount is required for scroll action"}
                page = await context.get_current_page()
                await page.evaluate(f"window.scrollBy(0, {cmd['scroll_amount']})")
                return {'success': True, 'message': f"Scrolled by {cmd['scroll_amount']} pixels"}

            elif action == "switch_tab":
                if cmd.get('tab_id') is None:
                    return {'success': False, 'message': "Tab ID is required for switch_tab action"}
                await context.switch_to_tab(cmd['tab_id'])
                return {'success': True, 'message': f"Switched to tab {cmd['tab_id']}"}

            elif action == "new_tab":
                if not cmd.get('url'):
                    return {'success': False, 'message': "URL is required for new_tab action"}
                await context.create_new_tab(cmd['url'])
                return {'success': True, 'message': f"Opened new tab with URL {cmd['url']}"}

            elif action == "close_tab":
                await context.close_current_tab()
                return {'success': True, 'message': "Closed current tab"}

            elif action == "refresh":
                page = await context.get_current_page()
                await page.reload()
                return {'success': True, 'message': "Page refreshed"}

            elif action == "get_current_state":
                state = await context.get_state()
                return {
                    'success': True,
                    'message': "Current browser state retrieved",
                    'data': {"url": state.url, "title": state.title}
                }
                
            return {'success': False, 'message': f'Action {action} not implemented'}
            
        except Exception as e:
            return {'success': False, 'message': f'Error executing {action}: {str(e)}'}

    def execute(self, **kwargs) -> Dict:
        """Execute a browser command."""
        self._start_process()  # Ensure process is running
        self.command_queue.put(kwargs)
        try:
            result = self.result_queue.get(timeout=30)  # 30 second timeout
            return result
        except Empty:
            return {'success': False, 'message': 'Operation timed out'}

    def cleanup(self):
        """Clean up resources."""
        if self.process and self.process.is_alive():
            self.command_queue.put(None)  # Send shutdown signal
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
        self.process = None


class BrowserTool:
    """Class for browser interactions.
    
    This class provides a clean interface to browser operations with optional
    dependency on browser-use package.
    """
    def __init__(self, headless=False):
        """Initialize the browser tool.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self._browser_process = None
        self.headless = headless
    
    def _ensure_browser_available(self):
        """Ensure browser_use is available and browser process is initialized."""
        # Check if browser_use module is available
        if not self.is_browser_use_available():
            raise ImportError("browser_use package is not available. Please install it to use BrowserTool.")
        
        # Initialize browser process if needed
        if self._browser_process is None:
            self._browser_process = BrowserProcess(headless=self.headless)
        
        return self._browser_process
    
    @staticmethod
    def is_browser_use_available():
        """Check if browser_use package is available."""
        return importlib.util.find_spec("browser_use") is not None
    
    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="navigate", url=url)
        return BrowserToolResult(**result).model_dump()
    
    def click(self, index: int) -> Dict[str, Any]:
        """Click an element by index."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="click", index=index)
        return BrowserToolResult(**result).model_dump()
    
    def input_text(self, index: int, text: str) -> Dict[str, Any]:
        """Input text into an element."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="input_text", index=index, text=text)
        return BrowserToolResult(**result).model_dump()
    
    def screenshot(self) -> Dict[str, Any]:
        """Capture a screenshot."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="screenshot")
        return BrowserToolResult(**result).model_dump()
    
    def get_html(self) -> Dict[str, Any]:
        """Get page HTML content."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="get_html")
        return BrowserToolResult(**result).model_dump()
    
    def get_text(self) -> Dict[str, Any]:
        """Get text content of the page."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="get_text")
        return BrowserToolResult(**result).model_dump()
    
    def read_links(self) -> Dict[str, Any]:
        """Get all links on the page."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="read_links")
        return BrowserToolResult(**result).model_dump()
    
    def execute_js(self, script: str) -> Dict[str, Any]:
        """Execute JavaScript code."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="execute_js", script=script)
        return BrowserToolResult(**result).model_dump()
    
    def scroll(self, scroll_amount: int) -> Dict[str, Any]:
        """Scroll the page."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="scroll", scroll_amount=scroll_amount)
        return BrowserToolResult(**result).model_dump()
    
    def switch_tab(self, tab_id: int) -> Dict[str, Any]:
        """Switch to a specific tab."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="switch_tab", tab_id=tab_id)
        return BrowserToolResult(**result).model_dump()
    
    def new_tab(self, url: str) -> Dict[str, Any]:
        """Open a new tab."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="new_tab", url=url)
        return BrowserToolResult(**result).model_dump()
    
    def close_tab(self) -> Dict[str, Any]:
        """Close the current tab."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="close_tab")
        return BrowserToolResult(**result).model_dump()
    
    def refresh(self) -> Dict[str, Any]:
        """Refresh the current page."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="refresh")
        return BrowserToolResult(**result).model_dump()
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get the current state of the browser."""
        browser_process = self._ensure_browser_available()
        result = browser_process.execute(action="get_current_state")
        return BrowserToolResult(**result).model_dump()
    
    def cleanup(self):
        """Clean up browser resources."""
        if self._browser_process:
            self._browser_process.cleanup()
            self._browser_process = None