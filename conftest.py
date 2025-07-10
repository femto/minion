#!/usr/bin/env python
# coding=utf-8
"""
Pytest configuration and fixtures for async tool tests
"""

import asyncio
import pytest
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.tools.async_example_tools import EXAMPLE_ASYNC_TOOLS
from minion.tools.base_tool import tool


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@tool
def sync_test_tool(x: int, y: int) -> int:
    """Simple sync tool for testing"""
    return x + y


@pytest.fixture
def async_executor():
    """Fixture providing an AsyncPythonExecutor instance"""
    return AsyncPythonExecutor(
        additional_authorized_imports=["asyncio", "time"],
        max_print_outputs_length=5000
    )


@pytest.fixture
def async_executor_with_tools(async_executor):
    """Fixture providing an AsyncPythonExecutor with example tools loaded"""
    tools = {
        **EXAMPLE_ASYNC_TOOLS,
        "sync_test_tool": sync_test_tool
    }
    async_executor.send_tools(tools)
    return async_executor


@pytest.fixture
def example_async_tools():
    """Fixture providing example async tools"""
    return EXAMPLE_ASYNC_TOOLS


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )