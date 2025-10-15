# MCP StreamableHTTP Support Guide

This guide explains how to use the StreamableHTTP connection type with MCPToolset in the minion framework.

## Overview

The MCPToolset now supports three connection types:
- **stdio**: Standard input/output for local MCP servers
- **sse**: Server-Sent Events for HTTP-based MCP servers  
- **streamable_http**: StreamableHTTP for advanced HTTP-based MCP servers with streaming capabilities

## StreamableHTTP Parameters

The `StreamableHTTPServerParameters` class supports the following parameters:

```python
StreamableHTTPServerParameters(
    url: str,                                    # Required: Server URL
    headers: Optional[Dict[str, str]] = None,    # Optional: HTTP headers
    timeout: Optional[Union[float, timedelta]] = 30,           # Connection timeout
    sse_read_timeout: Optional[Union[float, timedelta]] = 300, # SSE read timeout  
    terminate_on_close: bool = True,             # Terminate connection on close
    auth: Optional[httpx.Auth] = None            # HTTP authentication
)
```

### Parameter Details

- **url**: The base URL of your StreamableHTTP MCP server
- **headers**: Custom HTTP headers (e.g., authentication tokens, content types)
- **timeout**: Connection timeout - accepts float (seconds) or timedelta object
- **sse_read_timeout**: Server-Sent Events read timeout - accepts float (seconds) or timedelta object  
- **terminate_on_close**: Whether to terminate the connection when the context closes
- **auth**: httpx authentication object for authenticated connections

## Usage Examples

### Basic Usage

```python
from minion.tools.mcp.mcp_toolset import MCPToolset, StreamableHTTPServerParameters

# Create connection parameters
params = StreamableHTTPServerParameters(
    url="http://localhost:3000/mcp",
    headers={"Content-Type": "application/json"},
    timeout=30.0,
    sse_read_timeout=300.0
)

# Create toolset
toolset = MCPToolset(
    connection_params=params,
    name="my_http_toolset"
)

# Setup and use
await toolset.ensure_setup()
tools = toolset.get_tools()
```

### Using the Factory Function

```python
from minion.tools.mcp.mcp_toolset import create_streamable_http_toolset
from datetime import timedelta

# Create toolset using factory function
toolset = await create_streamable_http_toolset(
    url="http://localhost:3000/mcp",
    headers={"Authorization": "Bearer your-token"},
    timeout=timedelta(seconds=60),
    sse_read_timeout=timedelta(minutes=10),
    name="api_toolset"
)

# Tools are ready to use
tools = toolset.get_tools()
```

### With Authentication

```python
import httpx
from minion.tools.mcp.mcp_toolset import create_streamable_http_toolset

# Create authentication
auth = httpx.BasicAuth("username", "password")
# or
# auth = httpx.BearerAuth("your-token")

toolset = await create_streamable_http_toolset(
    url="https://secure-api.example.com/mcp",
    auth=auth,
    headers={"User-Agent": "MCP-Client/1.0"},
    name="secure_toolset"
)
```

### Integration with Agents

```python
from minion.agents import CodeAgent
from minion.tools.mcp.mcp_toolset import create_streamable_http_toolset

# Create HTTP toolset
http_toolset = await create_streamable_http_toolset(
    url="http://localhost:8080/mcp",
    name="agent_http_tools"
)

# Get tools for agent
http_tools = http_toolset.get_tools()

# Create agent with HTTP tools
agent = await CodeAgent.create(
    llm="gpt-4o",
    tools=http_tools,
    name="HTTP MCP Agent"
)

# Use the agent
response = await agent.run_async("Use the available HTTP tools to help me")
```

## Error Handling

The StreamableHTTP connection includes robust error handling:

```python
from minion.tools.mcp.mcp_toolset import MCPToolset, StreamableHTTPServerParameters

toolset = MCPToolset(
    connection_params=StreamableHTTPServerParameters(
        url="http://localhost:3000/mcp"
    ),
    ignore_setup_errors=True  # Continue even if setup fails
)

await toolset.ensure_setup()

if toolset.is_healthy:
    # Use tools
    tools = toolset.get_tools()
else:
    print(f"Setup failed: {toolset.setup_error}")
```

## Timeout Configuration

You can configure timeouts using either float (seconds) or timedelta objects:

```python
from datetime import timedelta

# Using float (seconds)
params = StreamableHTTPServerParameters(
    url="http://localhost:3000/mcp",
    timeout=30.0,           # 30 seconds
    sse_read_timeout=300.0  # 5 minutes
)

# Using timedelta objects
params = StreamableHTTPServerParameters(
    url="http://localhost:3000/mcp", 
    timeout=timedelta(seconds=30),
    sse_read_timeout=timedelta(minutes=5)
)
```

## Best Practices

1. **Always use context management**: Ensure proper cleanup with `await toolset.close()`

2. **Handle connection failures**: Use `ignore_setup_errors=True` for non-critical toolsets

3. **Set appropriate timeouts**: Configure timeouts based on your server's response characteristics

4. **Use authentication**: Secure your connections with proper authentication headers or httpx auth objects

5. **Monitor health**: Check `toolset.is_healthy` before using tools

## Complete Example

```python
import asyncio
from datetime import timedelta
from minion.tools.mcp.mcp_toolset import create_streamable_http_toolset

async def main():
    toolset = None
    try:
        # Create StreamableHTTP toolset
        toolset = await create_streamable_http_toolset(
            url="http://localhost:3000/mcp",
            headers={
                "Authorization": "Bearer your-token",
                "Content-Type": "application/json"
            },
            timeout=timedelta(seconds=30),
            sse_read_timeout=timedelta(minutes=5),
            name="example_toolset"
        )
        
        # Get and use tools
        tools = toolset.get_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Use a tool (example)
        if tools:
            result = await tools[0].forward(param="example")
            print(f"Tool result: {result}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if toolset:
            await toolset.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure your StreamableHTTP MCP server is running and accessible
2. **Timeout errors**: Increase timeout values for slow servers
3. **Authentication failures**: Verify your authentication headers or httpx auth objects
4. **Import errors**: Ensure the MCP library with StreamableHTTP support is installed

### Debug Logging

Enable debug logging to troubleshoot connection issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show detailed connection and communication logs from the MCP client.