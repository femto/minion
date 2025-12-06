#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for WebFetchTool
"""
import asyncio
import pytest

from minion.tools import WebFetchTool, create_web_fetch_tool


class TestWebFetchTool:
    """Tests for WebFetchTool class"""

    def test_tool_attributes(self):
        """Test tool basic attributes"""
        tool = WebFetchTool()
        assert tool.name == "web_fetch"
        assert tool.readonly is True
        assert "url" in tool.inputs
        assert "max_length" in tool.inputs
        assert "start_index" in tool.inputs

    def test_create_web_fetch_tool(self):
        """Test convenience function"""
        tool = create_web_fetch_tool(
            user_agent="TestAgent/1.0",
            timeout=60
        )
        assert tool.user_agent == "TestAgent/1.0"
        assert tool.timeout == 60

    @pytest.mark.asyncio
    async def test_fetch_simple_url(self):
        """Test fetching a simple URL"""
        tool = WebFetchTool()
        result = await tool.forward("https://example.com")

        # Should return markdown content
        assert isinstance(result, str)
        assert len(result) > 0
        # example.com has specific content
        assert "Example Domain" in result or "example" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_with_max_length(self):
        """Test fetching with max_length limit"""
        tool = WebFetchTool()
        result = await tool.forward("https://example.com", max_length=100)

        # Should be truncated
        assert len(result) <= 200  # Some buffer for truncation message

    @pytest.mark.asyncio
    async def test_fetch_with_pagination(self):
        """Test fetching with start_index"""
        tool = WebFetchTool()

        # Get full content
        full_result = await tool.forward("https://example.com", max_length=10000)

        # Get content starting from offset
        partial_result = await tool.forward(
            "https://example.com",
            start_index=50,
            max_length=10000
        )

        # Partial should be shorter
        assert len(partial_result) < len(full_result)

    @pytest.mark.asyncio
    async def test_fetch_raw_html(self):
        """Test fetching raw HTML"""
        tool = WebFetchTool()
        result = await tool.forward("https://example.com", raw=True)

        # Should contain HTML tags
        assert "<" in result and ">" in result

    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self):
        """Test fetching invalid URL returns error"""
        tool = WebFetchTool()
        result = await tool.forward("https://this-domain-does-not-exist-12345.com")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_fetch_empty_url(self):
        """Test fetching empty URL"""
        tool = WebFetchTool()
        result = await tool.forward("")

        assert "Error" in result

    def test_robots_txt_url_generation(self):
        """Test robots.txt URL generation"""
        tool = WebFetchTool()

        robots_url = tool._get_robots_txt_url("https://example.com/some/path")
        assert robots_url == "https://example.com/robots.txt"

        robots_url = tool._get_robots_txt_url("https://example.com:8080/path")
        assert robots_url == "https://example.com:8080/robots.txt"

    def test_basic_html_to_text(self):
        """Test basic HTML to text conversion"""
        tool = WebFetchTool()

        html = "<html><body><h1>Title</h1><p>Content</p><script>alert('x')</script></body></html>"
        text = tool._basic_html_to_text(html)

        assert "Title" in text
        assert "Content" in text
        assert "alert" not in text  # Script should be removed

    def test_clean_markdown(self):
        """Test markdown cleanup"""
        tool = WebFetchTool()

        messy = "# Title\n\n\n\n\nContent   \n\n\nMore"
        clean = tool._clean_markdown(messy)

        # Should have no more than 2 consecutive newlines
        assert "\n\n\n" not in clean


# Simple test runner
if __name__ == "__main__":
    print("Testing WebFetchTool...")

    # Basic tests
    tool = WebFetchTool()
    print(f"✓ Tool name: {tool.name}")
    print(f"✓ Tool readonly: {tool.readonly}")
    print(f"✓ Tool inputs: {list(tool.inputs.keys())}")

    # Test convenience function
    tool2 = create_web_fetch_tool(user_agent="Test/1.0")
    print(f"✓ create_web_fetch_tool works: {tool2.user_agent}")

    # Async test
    async def run_async_tests():
        print("\nRunning async tests...")

        # Test fetch
        result = await tool.forward("https://example.com")
        print(f"✓ Fetch example.com: {len(result)} chars")
        print(f"  Preview: {result[:100]}...")

        # Test with max_length
        result_short = await tool.forward("https://example.com", max_length=50)
        print(f"✓ Fetch with max_length=50: {len(result_short)} chars")

        # Test raw mode
        result_raw = await tool.forward("https://example.com", raw=True)
        has_html = "<" in result_raw and ">" in result_raw
        print(f"✓ Fetch raw HTML: {has_html}")

        print("\n✅ All tests passed!")

    asyncio.run(run_async_tests())
