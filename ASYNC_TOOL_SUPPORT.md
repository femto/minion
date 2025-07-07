# Asynchronous Tool Support for Code Minion Python Executor

This document describes the implementation of asynchronous tool support for the Code Minion Python executor, enabling the execution of async/await-based tools alongside traditional synchronous tools.

## Overview

The async tool support extends the Code Minion Python executor with the ability to:
- Execute asynchronous tools using `async`/`await` syntax
- Automatically wrap synchronous tools for use in async contexts
- Support concurrent tool execution using `asyncio.gather()` and similar patterns
- Maintain backward compatibility with existing synchronous tools
- Provide proper error handling and security for async operations

## Architecture

### Core Components

1. **AsyncBaseTool** (`minion/tools/async_base_tool.py`)
   - Base class for all asynchronous tools
   - Provides async `forward()` method interface
   - Supports async initialization with `setup()` method

2. **AsyncPythonExecutor** (`minion/main/async_python_executor.py`)
   - Async version of the Python code executor
   - Handles both sync and async tool calls transparently
   - Maintains security and safety features from the sync executor

3. **SyncToAsyncToolAdapter**
   - Automatically wraps synchronous tools for async execution
   - Uses `asyncio.run_in_executor()` to avoid blocking the event loop

4. **Example Async Tools** (`minion/tools/async_example_tools.py`)
   - Demonstrates various async tool patterns
   - Includes web requests, file operations, database simulation

## Usage Examples

### Creating Async Tools

#### Class-based Async Tool
```python
from minion.tools.async_base_tool import AsyncBaseTool

class AsyncWebRequestTool(AsyncBaseTool):
    name = "async_web_request"
    description = "Send asynchronous HTTP requests"
    inputs = {
        "url": {"type": "string", "description": "The URL to request"},
        "method": {"type": "string", "description": "HTTP method"}
    }
    output_type = "object"
    
    async def forward(self, url: str, method: str = "GET") -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url) as response:
                return {
                    "status": response.status,
                    "data": await response.json()
                }
```

#### Function-based Async Tool
```python
from minion.tools.async_base_tool import async_tool

@async_tool
async def async_calculate_pi(precision: int = 1000) -> float:
    """
    Asynchronously calculate Pi using the Leibniz formula
    
    Args:
        precision: Number of iterations for calculation
        
    Returns:
        Approximation of Pi
    """
    pi_estimate = 0.0
    sign = 1
    
    for i in range(precision):
        pi_estimate += sign / (2 * i + 1)
        sign *= -1
        
        # Yield control periodically
        if i % 100 == 0:
            await asyncio.sleep(0.001)
    
    return pi_estimate * 4
```

### Using the Async Executor

```python
import asyncio
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.tools.async_example_tools import EXAMPLE_ASYNC_TOOLS

async def main():
    # Create async executor
    executor = AsyncPythonExecutor(
        additional_authorized_imports=["asyncio"],
        max_print_outputs_length=10000
    )
    
    # Send tools (both sync and async)
    executor.send_tools(EXAMPLE_ASYNC_TOOLS)
    
    # Execute code with async tools
    code = """
    # Single async tool call
    result = await async_calculate_pi(100)
    print(f"Pi approximation: {result}")
    
    # Concurrent async operations
    tasks = [
        async_fetch_data("url1", 0.5),
        async_fetch_data("url2", 0.3),
        async_calculate_pi(500)
    ]
    results = await asyncio.gather(*tasks)
    print(f"Completed {len(results)} operations")
    """
    
    output, logs, is_final = await executor(code)
    print(f"Output: {output}")
    print(f"Logs: {logs}")

# Run the example
asyncio.run(main())
```

## Key Features

### 1. Transparent Sync/Async Tool Integration

The async executor automatically detects tool types and handles them appropriately:

- **Async tools** (`AsyncBaseTool` instances): Called with `await`
- **Sync tools** (`BaseTool` instances): Wrapped with `SyncToAsyncToolAdapter`
- **Regular functions**: Called directly (sync) or with `await` (async functions)

### 2. Concurrent Execution Support

Code can use standard `asyncio` patterns for concurrent execution:

```python
# Concurrent execution
tasks = [tool1(), tool2(), tool3()]
results = await asyncio.gather(*tasks)

# Sequential execution
result1 = await tool1()
result2 = await tool2(result1)
result3 = await tool3(result2)
```

### 3. Error Handling and Safety

The async executor maintains all security features from the sync version:

- Restricted imports and function access
- Operation count limits to prevent infinite loops
- Safe evaluation of expressions
- Proper exception handling and propagation

### 4. Performance Benefits

Async tools provide significant performance improvements for I/O-bound operations:

- Network requests can run concurrently
- File operations don't block other tools
- Database queries can be parallelized
- CPU-bound tasks can yield control periodically

## Implementation Details

### AST Evaluation

The async executor extends the original AST evaluation with async-aware versions of key functions:

- `evaluate_async_call()`: Handles async tool calls and coroutine functions
- `evaluate_async_ast()`: Main async evaluation dispatcher
- `evaluate_async_python_code()`: Entry point for async code execution

### Tool Call Resolution

When a tool is called, the executor determines the appropriate execution method:

1. Check if it's an `AsyncBaseTool` → use `await tool(*args, **kwargs)`
2. Check if it's a coroutine function → use `await func(*args, **kwargs)`
3. Check if it's a sync `BaseTool` → wrap with adapter and await
4. Otherwise → call directly as sync function

### Adapter Pattern

The `SyncToAsyncToolAdapter` allows sync tools to work in async contexts:

```python
class SyncToAsyncToolAdapter(AsyncBaseTool):
    def __init__(self, sync_tool):
        super().__init__()
        self.sync_tool = sync_tool
    
    async def forward(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.sync_tool.forward(*args, **kwargs)
        )
```

## Testing

The implementation includes comprehensive tests in `test_async_tools.py`:

1. **Basic async tool execution**
2. **Concurrent operations with `asyncio.gather()`**
3. **Mixed sync/async tool usage**
4. **Database simulation with async operations**
5. **File operations with async I/O**
6. **Error handling and graceful failures**
7. **Performance benchmarking vs sync execution**

Run the tests with:
```bash
python test_async_tools.py
```

## Dependencies

The async tool support has minimal additional dependencies:

- **Core**: Only standard library `asyncio`
- **Optional**: `aiohttp` for web request examples (gracefully degrades if not available)

## Migration Guide

### For Tool Developers

1. **Creating new async tools**: Inherit from `AsyncBaseTool` or use `@async_tool` decorator
2. **Converting existing tools**: Usually just need to add `async` to method signatures and `await` to async calls

### For Executor Users

1. **Switch to async executor**:
   ```python
   # Old
   from minion.main.local_python_executor import LocalPythonExecutor
   executor = LocalPythonExecutor(...)
   output, logs, is_final = executor(code)
   
   # New
   from minion.main.async_python_executor import AsyncPythonExecutor
   executor = AsyncPythonExecutor(...)
   output, logs, is_final = await executor(code)
   ```

2. **Use async/await in code**:
   ```python
   # Async tool calls must use await
   result = await my_async_tool(arg1, arg2)
   
   # Sync tools work as before (automatically wrapped)
   sync_result = my_sync_tool(arg1, arg2)
   ```

## Best Practices

### 1. Tool Design

- Use async tools for I/O-bound operations (network, files, databases)
- Add periodic `await asyncio.sleep(0)` in CPU-intensive loops
- Implement proper timeout handling for network operations
- Use context managers for resource management

### 2. Error Handling

- Always handle exceptions in async tools
- Provide meaningful error messages
- Use try/except blocks for graceful degradation

### 3. Performance

- Use `asyncio.gather()` for concurrent operations
- Avoid blocking operations in async tools
- Consider using `asyncio.run_in_executor()` for CPU-bound tasks

### 4. Security

- Validate all inputs in async tools
- Use proper timeout values to prevent hanging
- Follow the same security practices as sync tools

## Future Enhancements

Potential improvements for the async tool support:

1. **Streaming Support**: Tools that yield results progressively
2. **Background Tasks**: Tools that run in the background
3. **Rate Limiting**: Built-in rate limiting for API calls
4. **Caching**: Async-aware caching mechanisms
5. **Monitoring**: Performance monitoring and metrics
6. **Connection Pooling**: Shared connection pools for database/HTTP tools

## Conclusion

The asynchronous tool support provides a powerful foundation for building scalable, high-performance tools in the Code Minion ecosystem. It maintains full backward compatibility while enabling new patterns for concurrent execution and improved I/O performance.

The implementation follows Python's async/await best practices and provides a clean, intuitive API for both tool developers and users.