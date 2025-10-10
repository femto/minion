# UTCP Manual Toolset

The `UtcpManualToolset` provides integration between the minion framework and UTCP (Universal Tool Calling Protocol) tools.

## Features

- **Async Support**: Built on `AsyncBaseTool` for non-blocking tool execution
- **Name Mapping**: Automatically converts UTCP tool names with dots (e.g., `calculator.add`) to valid Python method names (e.g., `calculator_add`)
- **Error Handling**: Robust error handling with timeout support
- **Framework Integration**: Seamlessly integrates with minion agents and providers
- **Auto Setup**: Factory function automatically sets up the toolset

## Installation

Make sure you have the UTCP dependencies installed:

```bash
pip install utcp utcp-http utcp-cli
```

Or install with the utcp extra:

```bash
pip install minionx[utcp]
```

## Configuration

Create a `providers.json` file with your UTCP configuration:

```json
{
  "providers": {
    "bedrock": {
      "type": "bedrock",
      "region": "us-east-1",
      "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
      "tools": [
        {
          "name": "calculator.add",
          "description": "Add two numbers together",
          "parameters": {
            "type": "object",
            "properties": {
              "a": {"type": "number", "description": "First number"},
              "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"]
          }
        }
      ]
    }
  }
}
```

## Usage

### Basic Usage

```python
import asyncio
from minion.tools import create_utcp_toolset

async def main():
    # Create and setup toolset (async)
    utcp_toolset = await create_utcp_toolset(
        config="path/to/providers.json",
        name="my_utcp_toolset"
    )
    
    # Get tools (toolset is already setup)
    tools = utcp_toolset.get_tools()
    
    # Use a tool
    if tools:
        result = await tools[0].forward(a=5, b=3)
        print(result)
    
    # Cleanup
    await utcp_toolset.close()

asyncio.run(main())
```

### Integration with Agents

```python
from minion.tools import create_utcp_toolset
from minion.agents.base_agent import BaseAgent
from minion.providers.openai_provider import OpenAIProvider

async def main():
    # Create and setup UTCP toolset (async)
    utcp_toolset = await create_utcp_toolset(config="providers.json")
    
    # Create agent with UTCP tools
    agent = BaseAgent(
        provider=OpenAIProvider(model="gpt-4"),
        tools=utcp_toolset.get_tools()
    )
    
    # Use agent
    response = await agent.run("Add 15 and 27")
    print(response)
    
    # Cleanup
    await utcp_toolset.close()
```

### Manual Toolset Creation

```python
from minion.tools.utcp.utcp_manual_toolset import UtcpManualToolset

async def main():
    # Create toolset manually
    utcp_toolset = UtcpManualToolset(
        config="providers.json",
        root_dir="/path/to/root",
        setup_timeout=30,
        ignore_setup_errors=False
    )
    
    # Setup manually
    await utcp_toolset._ensure_setup()
    
    # Use toolset...
```

## API Reference

### create_utcp_toolset (Async Factory Function)

```python
async def create_utcp_toolset(
    config: Optional[Union[str, Path, Dict[str, Any]]] = None,
    root_dir: Optional[str] = None,
    name: Optional[str] = None
) -> UtcpManualToolset
```

**Parameters:**
- `config`: UTCP configuration - can be a path to config file, dict config, or UtcpClientConfig
- `root_dir`: Root directory for UTCP client
- `name`: Optional name for the toolset

**Returns:** Fully setup `UtcpManualToolset` instance

### UtcpManualToolset

#### Constructor Parameters

- `config`: UTCP configuration - can be a path to config file, dict config, or UtcpClientConfig
- `root_dir`: Root directory for UTCP client
- `name`: Optional name for the toolset
- `setup_timeout`: Timeout in seconds for setup (default: 30)
- `ignore_setup_errors`: Whether to ignore setup errors (default: False)

#### Properties

- `is_healthy`: Returns True if toolset is setup and healthy
- `setup_error`: Returns setup error if any

#### Methods

- `get_tools()`: Get list of available tools
- `close()`: Close toolset and cleanup resources
- `_ensure_setup()`: Manually setup the toolset (called automatically by factory function)

### AsyncUtcpTool

Adapter class that converts UTCP tools to minion-compatible async tools.

#### Key Features

- Converts tool names with dots to underscores for valid Python identifiers
- Maintains original tool name for UTCP calls
- Provides structured error handling
- Returns results in expected format

## Error Handling

The toolset includes comprehensive error handling:

- **Setup Errors**: Logged and optionally ignored based on `ignore_setup_errors`
- **Tool Execution Errors**: Caught and returned as structured error responses
- **Timeout Handling**: Setup operations have configurable timeouts
- **Resource Cleanup**: Automatic cleanup on close

## Examples

See the `examples/utcp/` directory for complete usage examples:

- `utcp_toolset_example.py`: Basic toolset usage
- `utcp_agent_example.py`: Integration with agents

## Notes

- **Async Factory**: `create_utcp_toolset()` is now async and automatically sets up the toolset
- **Tool Names**: Tool names with dots (e.g., `calculator.add`) are converted to underscores (`calculator_add`) for Python compatibility
- **Original Names**: The original tool name is preserved for UTCP API calls
- **Non-blocking**: All tool operations are async and non-blocking
- **Resource Management**: Always call `close()` when done to properly cleanup resources