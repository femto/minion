# Async Tool Support in Python Executor

The Python executor in Code Minion now supports asynchronous tools, allowing for better integration with async functions and I/O operations.

## Overview

The new `AsyncLocalPythonExecutor` extends the capabilities of the existing `LocalPythonExecutor` to support:

- Async function calls from Python code
- Async tools and agents
- Backward compatibility with synchronous tools
- Automatic detection and handling of coroutines

## Usage

### Basic Setup

```python
from minion.agents.code_minion import CodeMinion
from minion.tools.base_tool import BaseTool
import asyncio

# Create a CodeMinion with async tool support
agent = CodeMinion(use_async_executor=True)

# Or enable async support later
agent = CodeMinion()
agent.enable_async_tools()
```

### Creating Async Tools

```python
class AsyncWebTool(BaseTool):
    """Example async tool for web requests."""
    
    def __init__(self):
        super().__init__()
        self.name = "fetch_url"
        self.description = "Fetch content from a URL asynchronously"
    
    async def forward(self, url: str) -> str:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()

# Add the async tool
async_tool = AsyncWebTool()
agent.add_tool(async_tool)
agent.send_tools_to_executor(agent.tools)
```

### Using Async Tools in Code

When using the async executor, you can call async functions directly in Python code:

```python
# This will work with AsyncLocalPythonExecutor
code = """
# Call an async tool
result = await fetch_url("https://api.github.com/user")
print(f"Response: {result}")

# Mix with sync operations
data = json.loads(result)
final_answer(f"User data: {data}")
"""

# Execute the code
output, logs, is_final = await agent.python_executor(code)
```

## Technical Details

### Function Call Detection

The async executor automatically detects async functions using:

1. `inspect.iscoroutinefunction(func)` - checks if a function is async
2. `asyncio.iscoroutine(result)` - checks if a result is a coroutine that needs awaiting

### Execution Flow

1. Code is parsed into AST
2. `async_evaluate_ast` handles the evaluation
3. For function calls, `async_evaluate_call` is used
4. Async functions are awaited, sync functions are called normally
5. Results are handled the same way as sync execution

### Compatibility

- **Backward Compatible**: All existing sync tools continue to work
- **Mixed Mode**: Can use both sync and async tools in the same code
- **Automatic Detection**: No need to manually specify which tools are async

## Example: Complete Async Tool Integration

```python
import asyncio
from minion.agents.code_minion import CodeMinion
from minion.tools.base_tool import BaseTool

class AsyncDatabaseTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "query_db"
        self.description = "Query database asynchronously"
    
    async def forward(self, query: str) -> dict:
        # Simulate async database operation
        await asyncio.sleep(0.1)
        return {"result": f"Query '{query}' executed", "rows": 42}

async def main():
    # Setup agent with async support
    agent = CodeMinion(use_async_executor=True)
    
    # Add async tool
    db_tool = AsyncDatabaseTool()
    agent.add_tool(db_tool)
    agent.send_tools_to_executor(agent.tools)
    
    # Execute code with async tools
    code = """
# Query database asynchronously
result = await query_db("SELECT * FROM users")
print(f"Database result: {result}")

# Process the result
if result['rows'] > 0:
    final_answer(f"Found {result['rows']} users")
else:
    final_answer("No users found")
"""
    
    output, logs, is_final = await agent.python_executor(code)
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Is final: {is_final}")

# Run the example
asyncio.run(main())
```

## Performance Considerations

- Async tools are most beneficial for I/O-bound operations
- CPU-bound operations may not see performance improvements
- The async executor has minimal overhead for sync operations
- Consider using async tools for:
  - Web requests
  - Database queries
  - File I/O operations
  - Network communications

## Migration Guide

### From Sync to Async

1. Change executor initialization:
   ```python
   # Before
   agent = CodeMinion()
   
   # After
   agent = CodeMinion(use_async_executor=True)
   ```

2. Make tools async if they perform I/O:
   ```python
   # Before
   def forward(self, url):
       return requests.get(url).text
   
   # After
   async def forward(self, url):
       async with aiohttp.ClientSession() as session:
           async with session.get(url) as response:
               return await response.text()
   ```

3. Update code to use await for async calls:
   ```python
   # Before
   result = fetch_url("https://example.com")
   
   # After
   result = await fetch_url("https://example.com")
   ```

## Limitations

- The async executor currently only handles async function calls
- Other async constructs (async generators, async context managers) are not yet fully supported
- All code execution is still sequential within a single code block
- Error handling for async operations follows the same patterns as sync operations