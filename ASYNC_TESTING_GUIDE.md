# Async Tool Testing Guide

This guide explains how to run tests for the asynchronous tool support in Code Minion.

## Prerequisites

Make sure you have all dependencies installed:

```bash
pip install -r requirements.txt
```

The key testing dependencies are:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `aiohttp` - For web request examples (optional)

## Running Tests

### Run All Async Tests

```bash
# Run all async-related tests
pytest -m asyncio -v

# Run specific test file
pytest tests/test_async_tools_unit.py -v

# Run with coverage
pytest tests/test_async_tools_unit.py --cov=minion.main.async_python_executor --cov=minion.tools.async_base_tool -v
```

### Run Individual Test Categories

```bash
# Test async tool creation and decoration
pytest tests/test_async_tools_unit.py::TestAsyncBaseTool -v

# Test async executor functionality  
pytest tests/test_async_tools_unit.py::TestAsyncPythonExecutor -v

# Test sync-to-async adapter
pytest tests/test_async_tools_unit.py::TestSyncToAsyncAdapter -v

# Test file operations
pytest tests/test_async_tools_unit.py::TestAsyncFileOperations -v

# Test database operations
pytest tests/test_async_tools_unit.py::TestAsyncDatabaseOperations -v

# Test performance benefits
pytest tests/test_async_tools_unit.py::test_performance_benefit -v
```

### Run Comprehensive Demo Tests

```bash
# Run the comprehensive test suite (longer running)
pytest test_async_tools.py::test_all_async_features -v

# Run standalone demo (not through pytest)
python test_async_tools.py
```

## Test Structure

### Unit Tests (`tests/test_async_tools_unit.py`)

These are fast, focused unit tests that verify individual components:

- **TestAsyncBaseTool**: Tests async tool base class and decorator
- **TestAsyncPythonExecutor**: Tests the async executor with various scenarios  
- **TestSyncToAsyncAdapter**: Tests automatic sync tool wrapping
- **TestAsyncFileOperations**: Tests async file I/O operations
- **TestAsyncDatabaseOperations**: Tests async database simulation
- **test_performance_benefit**: Verifies async performance improvements

### Integration Tests (`test_async_tools.py`)

These are longer-running integration tests that demonstrate real-world usage:

- Basic async tool execution
- Concurrent async operations with `asyncio.gather()`
- Mixed sync/async tool usage
- File operations with cleanup
- Error handling scenarios
- Performance benchmarking

## Writing New Async Tests

### Test Function Requirements

All async test functions must be marked with `@pytest.mark.asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_my_async_function():
    """Test description"""
    # Your async test code here
    result = await some_async_operation()
    assert result is not None
```

### Using Fixtures

The tests provide several fixtures for common setup:

```python
@pytest.mark.asyncio
async def test_with_executor(async_executor):
    """Test using the executor fixture"""
    # async_executor is pre-configured
    code = "result = await async_tool()"
    output, logs, is_final = await async_executor(code)
    assert output is not None

@pytest.mark.asyncio  
async def test_with_tools(async_executor_with_tools):
    """Test using executor with tools pre-loaded"""
    # Tools are already loaded
    code = "pi = await async_calculate_pi(10)"
    output, logs, is_final = await async_executor_with_tools(code)
    assert abs(output - 3.14159) < 1.0
```

### Test Categories

Use pytest markers to categorize tests:

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_long_running_operation():
    """Test that takes a while to run"""
    pass

# Run only fast tests
pytest -m "asyncio and not slow" -v

# Run only slow tests  
pytest -m "asyncio and slow" -v
```

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you've installed all requirements
   ```bash
   pip install -r requirements.txt
   ```

2. **Async test not running**: Check that you have `@pytest.mark.asyncio` decorator

3. **Event loop issues**: The `conftest.py` should handle this, but if you see event loop errors, try:
   ```bash
   pytest --asyncio-mode=auto
   ```

4. **aiohttp not available**: Some web request tests will skip gracefully if aiohttp isn't installed

### Configuration

The pytest configuration is in `pytest.ini`:

```ini
[tool:pytest]
asyncio_mode = auto
markers =
    asyncio: marks tests as async
    slow: marks tests as slow
```

### GitHub Actions

Tests run automatically on GitHub Actions for Python 3.9, 3.10, and 3.11. See `.github/workflows/test-async-tools.yml` for the CI configuration.

## Performance Testing

The async tests include performance verification:

```python
@pytest.mark.asyncio
async def test_performance_benefit():
    """Verify async provides performance benefits"""
    # Concurrent operations should be faster than sequential
    start = time.time()
    tasks = [async_fetch_data(f"url_{i}", 0.1) for i in range(3)]
    results = await asyncio.gather(*tasks)
    duration = time.time() - start
    
    # Should complete in ~0.1s (concurrent) not ~0.3s (sequential)
    assert duration < 0.5
```

This ensures that async tools actually provide the expected performance benefits for concurrent operations.