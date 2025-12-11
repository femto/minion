#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for browser toolset.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock


class TestBrowserToolsetImport:
    """Test browser toolset import and availability."""

    def test_import_browser_toolset(self):
        """Test that BrowserToolset can be imported."""
        from minion.tools import BrowserToolset
        assert BrowserToolset is not None

    def test_import_create_browser_toolset(self):
        """Test that create_browser_toolset can be imported."""
        from minion.tools import create_browser_toolset
        assert create_browser_toolset is not None

    def test_import_has_browser_toolset(self):
        """Test that HAS_BROWSER_TOOLSET can be imported."""
        from minion.tools import HAS_BROWSER_TOOLSET
        assert isinstance(HAS_BROWSER_TOOLSET, bool)

    def test_import_from_browser_submodule(self):
        """Test importing from the browser submodule."""
        from minion.tools.browser import BrowserToolset
        assert BrowserToolset is not None


class TestBrowserToolsetBasics:
    """Test basic BrowserToolset functionality."""

    def test_toolset_has_tools(self):
        """Test that toolset contains expected tools."""
        from minion.tools.browser import BrowserToolset

        # Create toolset (lazy initialization means browser won't start yet)
        toolset = BrowserToolset(headless=True)

        # Check expected tools are present
        expected_tools = [
            "browser_navigate",
            "browser_click",
            "browser_input_text",
            "browser_get_text",
            "browser_get_html",
            "browser_screenshot",
            "browser_scroll",
            "browser_execute_js",
            "browser_get_state",
            "browser_read_links",
            "browser_new_tab",
            "browser_close_tab",
            "browser_switch_tab",
            "browser_refresh",
        ]

        tool_names = [tool.name for tool in toolset.tools]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_get_tool_by_name(self):
        """Test getting a tool by name."""
        from minion.tools.browser import BrowserToolset

        toolset = BrowserToolset(headless=True)

        # Test getting existing tool
        navigate_tool = toolset.get_tool("browser_navigate")
        assert navigate_tool is not None
        assert navigate_tool.name == "browser_navigate"

        # Test getting non-existent tool
        nonexistent = toolset.get_tool("nonexistent_tool")
        assert nonexistent is None

    def test_tool_has_required_attributes(self):
        """Test that each tool has required attributes."""
        from minion.tools.browser import BrowserToolset

        toolset = BrowserToolset(headless=True)

        for tool in toolset.tools:
            assert hasattr(tool, "name"), f"Tool missing 'name' attribute"
            assert hasattr(tool, "description"), f"Tool {tool.name} missing 'description'"
            assert hasattr(tool, "inputs"), f"Tool {tool.name} missing 'inputs'"
            assert hasattr(tool, "output_type"), f"Tool {tool.name} missing 'output_type'"
            assert hasattr(tool, "readonly"), f"Tool {tool.name} missing 'readonly'"

    def test_is_available_method(self):
        """Test the is_available static method."""
        from minion.tools.browser import BrowserToolset

        # Should return a boolean
        result = BrowserToolset.is_available()
        assert isinstance(result, bool)


class TestBrowserToolsetContextManager:
    """Test context manager functionality."""

    def test_sync_context_manager(self):
        """Test synchronous context manager."""
        from minion.tools.browser import BrowserToolset

        with BrowserToolset(headless=True) as toolset:
            assert toolset is not None
            assert len(toolset.tools) > 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test asynchronous context manager."""
        from minion.tools.browser import BrowserToolset

        async with BrowserToolset(headless=True) as toolset:
            assert toolset is not None
            assert len(toolset.tools) > 0


class TestBrowserToolAttributes:
    """Test individual tool attributes."""

    def test_navigate_tool_attributes(self):
        """Test browser_navigate tool attributes."""
        from minion.tools.browser import BrowserNavigateTool

        # Check class attributes
        assert BrowserNavigateTool.name == "browser_navigate"
        assert "url" in BrowserNavigateTool.inputs
        assert BrowserNavigateTool.inputs["url"]["type"] == "string"
        assert BrowserNavigateTool.readonly is False

    def test_get_text_tool_attributes(self):
        """Test browser_get_text tool attributes."""
        from minion.tools.browser import BrowserGetTextTool

        assert BrowserGetTextTool.name == "browser_get_text"
        assert BrowserGetTextTool.inputs == {}  # No inputs
        assert BrowserGetTextTool.readonly is True

    def test_click_tool_attributes(self):
        """Test browser_click tool attributes."""
        from minion.tools.browser import BrowserClickTool

        assert BrowserClickTool.name == "browser_click"
        assert "index" in BrowserClickTool.inputs
        assert BrowserClickTool.inputs["index"]["type"] == "integer"
        assert BrowserClickTool.readonly is False

    def test_input_text_tool_attributes(self):
        """Test browser_input_text tool attributes."""
        from minion.tools.browser import BrowserInputTextTool

        assert BrowserInputTextTool.name == "browser_input_text"
        assert "index" in BrowserInputTextTool.inputs
        assert "text" in BrowserInputTextTool.inputs
        assert BrowserInputTextTool.readonly is False

    def test_scroll_tool_attributes(self):
        """Test browser_scroll tool attributes."""
        from minion.tools.browser import BrowserScrollTool

        assert BrowserScrollTool.name == "browser_scroll"
        assert "scroll_amount" in BrowserScrollTool.inputs
        assert BrowserScrollTool.inputs["scroll_amount"]["type"] == "integer"

    def test_execute_js_tool_attributes(self):
        """Test browser_execute_js tool attributes."""
        from minion.tools.browser import BrowserExecuteJsTool

        assert BrowserExecuteJsTool.name == "browser_execute_js"
        assert "script" in BrowserExecuteJsTool.inputs
        assert BrowserExecuteJsTool.inputs["script"]["type"] == "string"


class TestBrowserToolsetWithMock:
    """Test BrowserToolset with mocked browser."""

    @pytest.fixture
    def mock_browser(self):
        """Create a mock browser."""
        mock = Mock()
        mock.navigate.return_value = {"success": True, "message": "Navigated"}
        mock.click.return_value = {"success": True, "message": "Clicked"}
        mock.input_text.return_value = {"success": True, "message": "Input"}
        mock.get_text.return_value = {
            "success": True,
            "data": {"text": "Page text content"}
        }
        mock.get_html.return_value = {
            "success": True,
            "data": {"html": "<html>content</html>"}
        }
        mock.screenshot.return_value = {
            "success": True,
            "data": {"screenshot": b"fake_screenshot_data"}
        }
        mock.scroll.return_value = {"success": True, "message": "Scrolled"}
        mock.execute_js.return_value = {
            "success": True,
            "data": {"result": "js_result"}
        }
        mock.get_current_state.return_value = {
            "success": True,
            "data": {"url": "https://example.com", "title": "Example"}
        }
        mock.read_links.return_value = {
            "success": True,
            "data": {"links": [{"href": "https://link.com", "text": "Link"}]}
        }
        mock.new_tab.return_value = {"success": True, "message": "New tab"}
        mock.close_tab.return_value = {"success": True, "message": "Closed"}
        mock.switch_tab.return_value = {"success": True, "message": "Switched"}
        mock.refresh.return_value = {"success": True, "message": "Refreshed"}
        mock.cleanup.return_value = None
        return mock

    @pytest.mark.asyncio
    async def test_navigate_tool_with_mock(self, mock_browser):
        """Test navigate tool with mocked browser."""
        from minion.tools.browser import BrowserNavigateTool

        tool = BrowserNavigateTool(mock_browser)
        result = await tool.forward("https://example.com")

        assert "Successfully navigated" in result
        mock_browser.navigate.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_get_text_tool_with_mock(self, mock_browser):
        """Test get_text tool with mocked browser."""
        from minion.tools.browser import BrowserGetTextTool

        tool = BrowserGetTextTool(mock_browser)
        result = await tool.forward()

        assert result == "Page text content"
        mock_browser.get_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_tool_with_mock(self, mock_browser):
        """Test click tool with mocked browser."""
        from minion.tools.browser import BrowserClickTool

        tool = BrowserClickTool(mock_browser)
        result = await tool.forward(5)

        assert "Successfully clicked" in result
        mock_browser.click.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_input_text_tool_with_mock(self, mock_browser):
        """Test input_text tool with mocked browser."""
        from minion.tools.browser import BrowserInputTextTool

        tool = BrowserInputTextTool(mock_browser)
        result = await tool.forward(3, "test input")

        assert "Successfully input" in result
        mock_browser.input_text.assert_called_once_with(3, "test input")

    @pytest.mark.asyncio
    async def test_scroll_tool_with_mock(self, mock_browser):
        """Test scroll tool with mocked browser."""
        from minion.tools.browser import BrowserScrollTool

        tool = BrowserScrollTool(mock_browser)
        result = await tool.forward(500)

        assert "Successfully scrolled" in result
        assert "down" in result
        mock_browser.scroll.assert_called_once_with(500)

    @pytest.mark.asyncio
    async def test_get_state_tool_with_mock(self, mock_browser):
        """Test get_state tool with mocked browser."""
        from minion.tools.browser import BrowserGetStateTool

        tool = BrowserGetStateTool(mock_browser)
        result = await tool.forward()

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example"

    @pytest.mark.asyncio
    async def test_read_links_tool_with_mock(self, mock_browser):
        """Test read_links tool with mocked browser."""
        from minion.tools.browser import BrowserReadLinksTool

        tool = BrowserReadLinksTool(mock_browser)
        result = await tool.forward()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["links"]) == 1


class TestBrowserToolsetErrorHandling:
    """Test error handling in browser tools."""

    @pytest.fixture
    def error_browser(self):
        """Create a mock browser that returns errors."""
        mock = Mock()
        mock.navigate.return_value = {
            "success": False,
            "message": "Network error"
        }
        mock.get_text.side_effect = Exception("Connection lost")
        return mock

    @pytest.mark.asyncio
    async def test_navigate_error_handling(self, error_browser):
        """Test navigate tool handles errors."""
        from minion.tools.browser import BrowserNavigateTool

        tool = BrowserNavigateTool(error_browser)
        result = await tool.forward("https://example.com")

        assert "Failed to navigate" in result or "Network error" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self, error_browser):
        """Test tool handles exceptions gracefully."""
        from minion.tools.browser import BrowserGetTextTool

        tool = BrowserGetTextTool(error_browser)
        result = await tool.forward()

        assert "Error" in result
        assert "Connection lost" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
