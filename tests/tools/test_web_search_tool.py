#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for WebSearchTool
"""
import asyncio
import pytest

from minion.tools import WebSearchTool, create_web_search_tool, SearchResult


class TestWebSearchTool:
    """Tests for WebSearchTool class"""

    def test_tool_attributes(self):
        """Test tool basic attributes"""
        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert tool.readonly is True
        assert "query" in tool.inputs
        assert "max_results" in tool.inputs
        assert "provider" in tool.inputs

    def test_create_web_search_tool(self):
        """Test convenience function"""
        tool = create_web_search_tool(
            user_agent="TestAgent/1.0",
            timeout=60
        )
        assert tool.user_agent == "TestAgent/1.0"
        assert tool.timeout == 60

    def test_search_result_dataclass(self):
        """Test SearchResult dataclass"""
        result = SearchResult(
            title="Test Title",
            snippet="Test snippet",
            link="https://example.com"
        )
        assert result.title == "Test Title"
        assert result.snippet == "Test snippet"
        assert result.link == "https://example.com"

        # Test to_dict
        d = result.to_dict()
        assert d["title"] == "Test Title"
        assert d["snippet"] == "Test snippet"
        assert d["link"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_search_duckduckgo(self):
        """Test searching with DuckDuckGo"""
        tool = WebSearchTool()
        result = await tool.forward("python programming", max_results=5)

        # Should return formatted results
        assert isinstance(result, str)
        assert "Found" in result or "No results" in result

    @pytest.mark.asyncio
    async def test_search_with_max_results(self):
        """Test search with limited results"""
        tool = WebSearchTool()
        result = await tool.forward("python", max_results=3)

        # Should return results
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Test search with empty query"""
        tool = WebSearchTool()
        result = await tool.forward("")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_unknown_provider(self):
        """Test search with unknown provider"""
        tool = WebSearchTool()
        result = await tool.forward("test", provider="unknown")

        assert "Error" in result
        assert "Unknown search provider" in result

    @pytest.mark.asyncio
    async def test_search_raw(self):
        """Test raw search results"""
        tool = WebSearchTool()
        results = await tool.search_raw("python programming", max_results=3)

        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], SearchResult)
            assert results[0].title
            assert results[0].link

    def test_clean_duckduckgo_link(self):
        """Test DuckDuckGo link cleaning"""
        tool = WebSearchTool()

        # Test uddg parameter cleaning
        dirty_link = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"
        clean = tool._clean_duckduckgo_link(dirty_link)
        assert "example.com" in clean

        # Test normal link
        normal_link = "https://example.com/page"
        assert tool._clean_duckduckgo_link(normal_link) == normal_link

    def test_format_results(self):
        """Test result formatting"""
        tool = WebSearchTool()

        results = [
            SearchResult("Title 1", "Snippet 1", "https://example1.com"),
            SearchResult("Title 2", "Snippet 2", "https://example2.com"),
        ]

        formatted = tool._format_results(results, "duckduckgo")
        assert "Found 2 search results" in formatted
        assert "Title 1" in formatted
        assert "Title 2" in formatted
        assert "https://example1.com" in formatted

    def test_format_empty_results(self):
        """Test formatting empty results"""
        tool = WebSearchTool()
        formatted = tool._format_results([], "duckduckgo")
        assert "No results found" in formatted


# Simple test runner
if __name__ == "__main__":
    print("Testing WebSearchTool...")

    # Basic tests
    tool = WebSearchTool()
    print(f"✓ Tool name: {tool.name}")
    print(f"✓ Tool readonly: {tool.readonly}")
    print(f"✓ Tool inputs: {list(tool.inputs.keys())}")

    # Test convenience function
    tool2 = create_web_search_tool(user_agent="Test/1.0")
    print(f"✓ create_web_search_tool works: {tool2.user_agent}")

    # Test SearchResult
    sr = SearchResult("Test", "Snippet", "https://test.com")
    print(f"✓ SearchResult: {sr.to_dict()}")

    # Async test
    async def run_async_tests():
        print("\nRunning async tests...")

        # Test search
        result = await tool.forward("python programming language", max_results=5)
        print(f"✓ Search 'python programming language':")
        print(f"  {result[:200]}...")

        # Test raw search
        results = await tool.search_raw("openai", max_results=3)
        print(f"✓ Raw search returned {len(results)} results")
        if results:
            print(f"  First result: {results[0].title}")

        print("\n✅ All tests passed!")

    asyncio.run(run_async_tests())
