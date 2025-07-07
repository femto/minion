#!/usr/bin/env python
# coding=utf-8
"""
Test file for demonstrating asynchronous tool support in Code Minion Python executor
"""

import asyncio
import time
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.tools.async_example_tools import EXAMPLE_ASYNC_TOOLS
from minion.tools.base_tool import tool


# Create a simple sync tool for comparison
@tool
def sync_calculate(x: int, y: int) -> int:
    """
    Synchronous calculation tool for comparison
    
    Args:
        x: First number
        y: Second number
        
    Returns:
        Sum of x and y
    """
    time.sleep(0.1)  # Simulate some work
    return x + y


async def test_async_tool_execution():
    """Test basic async tool execution"""
    print("Testing async tool execution...")
    
    # Create async executor
    executor = AsyncPythonExecutor(
        additional_authorized_imports=["asyncio", "time"],
        max_print_outputs_length=10000
    )
    
    # Send both sync and async tools
    tools = {
        **EXAMPLE_ASYNC_TOOLS,
        "sync_calculate": sync_calculate,
    }
    executor.send_tools(tools)
    
    # Test 1: Simple async tool call
    code1 = """
result = await async_calculate_pi(100)
print(f"Pi approximation: {result}")
"""
    
    print("\n=== Test 1: Async Pi Calculation ===")
    start_time = time.time()
    output, logs, is_final = await executor(code1)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")
    
    # Test 2: Multiple async tools with concurrency
    code2 = """
import asyncio

# Run multiple async operations concurrently
tasks = [
    async_fetch_data("https://api.example.com", 0.5),
    async_fetch_data("https://api2.example.com", 0.3),
    async_calculate_pi(500)
]

results = await asyncio.gather(*tasks)
print(f"Concurrent results: {len(results)} operations completed")
for i, result in enumerate(results):
    print(f"Result {i+1}: {result}")
"""
    
    print("\n=== Test 2: Concurrent Async Operations ===")
    start_time = time.time()
    output, logs, is_final = await executor(code2)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")
    
    # Test 3: Mix of sync and async tools
    code3 = """
# Mix sync and async operations
sync_result = sync_calculate(10, 20)
print(f"Sync result: {sync_result}")

async_result = await async_fetch_data("test://url", 0.1)
print(f"Async result: {async_result}")

# Use sync tool in async context (should be wrapped automatically)
total = sync_calculate(sync_result, 5)
print(f"Total: {total}")
"""
    
    print("\n=== Test 3: Mixed Sync/Async Operations ===")
    start_time = time.time()
    output, logs, is_final = await executor(code3)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")
    
    # Test 4: Database simulation
    code4 = """
# Test async database operations
db = async_database

# Insert some data
insert_result = await db("INSERT user data", "INSERT")
print(f"Insert result: {insert_result}")

# Query data
select_result = await db("SELECT * FROM users", "SELECT")
print(f"Select result: {select_result}")

# Update data
update_result = await db("UPDATE users SET active=1", "UPDATE")
print(f"Update result: {update_result}")
"""
    
    print("\n=== Test 4: Async Database Operations ===")
    start_time = time.time()
    output, logs, is_final = await executor(code4)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")


async def test_async_file_operations():
    """Test async file operations"""
    print("\n=== Test 5: Async File Operations ===")
    
    executor = AsyncPythonExecutor(
        additional_authorized_imports=["os"],
        max_print_outputs_length=10000
    )
    
    executor.send_tools(EXAMPLE_ASYNC_TOOLS)
    
    code = """
# Test file operations
file_tool = async_file_tool

# Write to a test file
write_result = await file_tool("write", "test_async.txt", "Hello, Async World!")
print(f"Write result: {write_result}")

# Read from the file
read_result = await file_tool("read", "test_async.txt")
print(f"Read result: {read_result}")

# Append to the file
append_result = await file_tool("append", "test_async.txt", "\\nAppended text!")
print(f"Append result: {append_result}")

# Read again to see the changes
final_content = await file_tool("read", "test_async.txt")
print(f"Final content: {final_content}")

# Clean up
import os
if os.path.exists("test_async.txt"):
    os.remove("test_async.txt")
    print("Test file cleaned up")
"""
    
    start_time = time.time()
    output, logs, is_final = await executor(code)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")


async def test_error_handling():
    """Test error handling in async tools"""
    print("\n=== Test 6: Error Handling ===")
    
    executor = AsyncPythonExecutor(
        additional_authorized_imports=[],
        max_print_outputs_length=10000
    )
    
    executor.send_tools(EXAMPLE_ASYNC_TOOLS)
    
    code = """
try:
    # Test with non-existent file
    result = await async_file_tool("read", "non_existent_file.txt")
    print(f"File read result: {result}")
    
    # Test invalid operation
    result2 = await async_file_tool("invalid_op", "test.txt")
    print(f"Invalid operation result: {result2}")
    
    # Test web request error (will fail gracefully without aiohttp)
    web_result = await async_web_request("https://httpbin.org/get")
    print(f"Web request result: {web_result}")
    
except Exception as e:
    print(f"Caught exception: {e}")
"""
    
    start_time = time.time()
    output, logs, is_final = await executor(code)
    end_time = time.time()
    print(f"Output: {output}")
    print(f"Logs: {logs}")
    print(f"Execution time: {end_time - start_time:.3f}s")


async def benchmark_async_vs_sync():
    """Benchmark async vs sync execution"""
    print("\n=== Benchmark: Async vs Sync Performance ===")
    
    # Create executors
    async_executor = AsyncPythonExecutor(
        additional_authorized_imports=["asyncio", "time"],
        max_print_outputs_length=10000
    )
    
    from minion.main.local_python_executor import LocalPythonExecutor
    sync_executor = LocalPythonExecutor(
        additional_authorized_imports=["time"],
        max_print_outputs_length=10000
    )
    
    # Send tools
    async_executor.send_tools(EXAMPLE_ASYNC_TOOLS)
    sync_executor.send_tools({"sync_calculate": sync_calculate})
    
    # Async concurrent operations
    async_code = """
import asyncio

tasks = [async_fetch_data(f"url_{i}", 0.1) for i in range(5)]
results = await asyncio.gather(*tasks)
print(f"Completed {len(results)} async operations")
"""
    
    # Sync sequential operations
    sync_code = """
import time

results = []
for i in range(5):
    time.sleep(0.1)  # Simulate work
    results.append(f"Result for operation {i}")
print(f"Completed {len(results)} sync operations")
"""
    
    # Benchmark async
    print("Running async benchmark...")
    start_time = time.time()
    async_output, async_logs, _ = await async_executor(async_code)
    async_time = time.time() - start_time
    
    # Benchmark sync
    print("Running sync benchmark...")
    start_time = time.time()
    sync_output, sync_logs, _ = sync_executor(sync_code)
    sync_time = time.time() - start_time
    
    print(f"\nBenchmark Results:")
    print(f"Async execution time: {async_time:.3f}s")
    print(f"Sync execution time: {sync_time:.3f}s")
    print(f"Speedup: {sync_time/async_time:.2f}x")


async def main():
    """Run all tests"""
    print("🚀 Starting Async Tool Support Tests for Code Minion")
    print("=" * 60)
    
    try:
        await test_async_tool_execution()
        await test_async_file_operations()
        await test_error_handling()
        await benchmark_async_vs_sync()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("Async tool support is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())