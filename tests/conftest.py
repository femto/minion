import pytest
pytest_plugins = ['pytest_asyncio']
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "llm_integration: mark test as an LLM integration test"
    )
