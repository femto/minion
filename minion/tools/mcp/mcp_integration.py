import json
import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union, overload, Callable

from typing_extensions import NotRequired, TypeAlias, TypedDict, Unpack

from minion.tools import BaseTool

if TYPE_CHECKING:
    from mcp import ClientSession

logger = logging.getLogger(__name__)

# Type alias for tool names
ToolName: TypeAlias = str

ServerType: TypeAlias = Literal["stdio", "sse", "http"]


class StdioServerParameters_T(TypedDict):
    command: str
    args: NotRequired[List[str]]
    env: NotRequired[Dict[str, str]]
    cwd: NotRequired[Union[str, Path, None]]


class SSEServerParameters_T(TypedDict):
    url: str
    headers: NotRequired[Dict[str, Any]]
    timeout: NotRequired[float]
    sse_read_timeout: NotRequired[float]


class StreamableHTTPParameters_T(TypedDict):
    url: str
    headers: NotRequired[dict[str, Any]]
    timeout: NotRequired[timedelta]
    sse_read_timeout: NotRequired[timedelta]
    terminate_on_close: NotRequired[bool]


def format_mcp_result(result: Any) -> str:
    #should we format mcp.types result to some result format handled by our framework?
    return str(result)
    """Format MCP tool result for minion brain.step"""
    # if isinstance(result, dict):
    #     # Handle MCP result format
    #     if "content" in result:
    #         content_items = result["content"]
    #         if isinstance(content_items, list):
    #             texts = []
    #             for item in content_items:
    #                 if isinstance(item, dict) and item.get("type") == "text":
    #                     texts.append(item.get("text", ""))
    #             return "\n".join(texts)
    #         elif isinstance(content_items, str):
    #             return content_items
    #
    #     # Handle other dict formats
    #     if "text" in result:
    #         return result["text"]
    #
    #     # Fallback to JSON string
    #     return json.dumps(result, indent=2)
    #
    # elif isinstance(result, str):
    #     return result
    # else:
    #     return str(result)


class BrainTool(BaseTool):
    """
    Adapter class to convert MCP tools to brain.step compatible format
    """
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], session: "ClientSession"):
        super().__init__()
        self.name = name
        self.description = description
        self.parameters = parameters
        self.session = session

        # Add attributes expected by minion framework
        self.__name__ = name
        self.__doc__ = description
        self.__input_schema__ = parameters

    async def forward(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        try:
            result = await self.session.call_tool(self.name, kwargs)
            return format_mcp_result(result)
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            return f"Error: {str(e)}"
    
    def to_function_spec(self) -> Dict[str, Any]:
        """Convert to function specification format for brain.step"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class MCPBrainClient:
    """
    Client for connecting to MCP servers and providing tools to minion brain.step
    """
    
    def __init__(self):
        # Initialize MCP sessions as a dictionary of ClientSession objects
        self.sessions: Dict[ToolName, "ClientSession"] = {}
        self.exit_stack = AsyncExitStack()
        self.available_tools: List[BrainTool] = []

    async def __aenter__(self):
        """Enter the context manager"""
        await self.exit_stack.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager"""
        await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

    @overload
    async def add_mcp_server(self, type: Literal["stdio"], **params: Unpack[StdioServerParameters_T]): ...

    @overload
    async def add_mcp_server(self, type: Literal["sse"], **params: Unpack[SSEServerParameters_T]): ...

    @overload
    async def add_mcp_server(self, type: Literal["http"], **params: Unpack[StreamableHTTPParameters_T]): ...

    async def add_mcp_server(self, type: ServerType, **params: Any):
        """Connect to an MCP server and add its tools to available tools

        Args:
            type (`str`):
                Type of the server to connect to. Can be one of:
                - "stdio": Standard input/output server (local)
                - "sse": Server-sent events (SSE) server
                - "http": StreamableHTTP server
            **params (`Dict[str, Any]`):
                Server parameters that can be either:
                    - For stdio servers:
                        - command (str): The command to run the MCP server
                        - args (List[str], optional): Arguments for the command
                        - env (Dict[str, str], optional): Environment variables for the command
                        - cwd (Union[str, Path, None], optional): Working directory for the command
                    - For SSE servers:
                        - url (str): The URL of the SSE server
                        - headers (Dict[str, Any], optional): Headers for the SSE connection
                        - timeout (float, optional): Connection timeout
                        - sse_read_timeout (float, optional): SSE read timeout
                    - For StreamableHTTP servers:
                        - url (str): The URL of the StreamableHTTP server
                        - headers (Dict[str, Any], optional): Headers for the StreamableHTTP connection
                        - timeout (timedelta, optional): Connection timeout
                        - sse_read_timeout (timedelta, optional): SSE read timeout
                        - terminate_on_close (bool, optional): Whether to terminate on close
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp import types as mcp_types

        # Determine server type and create appropriate parameters
        if type == "stdio":
            # Handle stdio server
            from mcp.client.stdio import stdio_client

            logger.info(f"Connecting to stdio MCP server with command: {params['command']} {params.get('args', [])}")

            client_kwargs = {"command": params["command"]}
            for key in ["args", "env", "cwd"]:
                if params.get(key) is not None:
                    client_kwargs[key] = params[key]
            server_params = StdioServerParameters(**client_kwargs)
            read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        elif type == "sse":
            # Handle SSE server
            from mcp.client.sse import sse_client

            logger.info(f"Connecting to SSE MCP server at: {params['url']}")

            client_kwargs = {"url": params["url"]}
            for key in ["headers", "timeout", "sse_read_timeout"]:
                if params.get(key) is not None:
                    client_kwargs[key] = params[key]
            read, write = await self.exit_stack.enter_async_context(sse_client(**client_kwargs))
        elif type == "http":
            # Handle StreamableHTTP server
            from mcp.client.streamable_http import streamablehttp_client

            logger.info(f"Connecting to StreamableHTTP MCP server at: {params['url']}")

            client_kwargs = {"url": params["url"]}
            for key in ["headers", "timeout", "sse_read_timeout", "terminate_on_close"]:
                if params.get(key) is not None:
                    client_kwargs[key] = params[key]
            read, write, _ = await self.exit_stack.enter_async_context(streamablehttp_client(**client_kwargs))
        else:
            raise ValueError(f"Unsupported server type: {type}")

        session = await self.exit_stack.enter_async_context(
            ClientSession(
                read_stream=read,
                write_stream=write,
                client_info=mcp_types.Implementation(
                    name="minion.MCPBrainClient",
                    version="1.0.0",
                ),
            )
        )

        logger.debug("Initializing session...")
        await session.initialize()

        # List available tools
        response = await session.list_tools()
        logger.debug("Connected to server with tools:", [tool.name for tool in response.tools])

        for tool in response.tools:
            if tool.name in self.sessions:
                logger.warning(f"Tool '{tool.name}' already defined by another server. Skipping.")
                continue

            # Map tool names to their server for later lookup
            self.sessions[tool.name] = session

            # Create BrainTool wrapper
            brain_tool = BrainTool(
                name=tool.name,
                description=tool.description,
                parameters=tool.inputSchema,
                session=session
            )
            
            # Add tool to the list of available tools
            self.available_tools.append(brain_tool)

    def get_tools_for_brain(self) -> List[BrainTool]:
        """Get list of tools in the format expected by brain.step"""
        return self.available_tools

    def get_tool_functions(self) -> Dict[str, Callable]:
        """Get dictionary of tool functions for direct execution"""
        return {tool.name: tool for tool in self.available_tools}

    def get_tool_specs(self) -> List[Dict[str, Any]]:
        """Get list of tool specifications in ChatCompletion format"""
        return [tool.to_function_spec() for tool in self.available_tools]

    def get_tools_dict(self) -> List[Dict[str, Any]]:
        """Get list of tools as dictionaries"""
        return [tool.to_dict() for tool in self.available_tools]


# Helper function to create final answer tool (example implementation)
def create_final_answer_tool() -> BrainTool:
    """
    Create a final answer tool that can be used with brain.step
    This is an example of how to create a local tool without MCP
    """
    class FinalAnswerSession:
        async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": args.get("answer", "No answer provided")
                    }
                ]
            }
    
    session = FinalAnswerSession()
    
    tool = BrainTool(
        name="final_answer",
        description="Provide the final answer to the user's question",
        parameters={
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The final answer to provide to the user"
                }
            },
            "required": ["answer"]
        },
        session=session
    )
    
    return tool


def create_calculator_tool() -> BrainTool:
    """
    Create a local calculator tool for basic arithmetic
    """
    class CalculatorSession:
        async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
            expression = args.get("expression", "")
            try:
                # Simple and safe evaluation for basic arithmetic
                allowed_chars = set("0123456789+-*/()., ")
                if not all(c in allowed_chars for c in expression):
                    raise ValueError("Invalid characters in expression")
                
                result = eval(expression)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Calculation result: {expression} = {result}"
                        }
                    ]
                }
            except Exception as e:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Unable to calculate '{expression}': {str(e)}"
                        }
                    ]
                }
    
    session = CalculatorSession()
    
    tool = BrainTool(
        name="calculator",
        description="Perform basic arithmetic calculations",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                }
            },
            "required": ["expression"]
        },
        session=session
    )
    
    return tool


async def add_filesystem_tool(mcp_client: MCPBrainClient, workspace_paths: List[str] = None) -> None:
    """
    Add filesystem MCP tool to the client
    
    Args:
        mcp_client: The MCP client to add the tool to
        workspace_paths: List of paths to allow access to. Defaults to current directory.
    """
    if workspace_paths is None:
        import os
        workspace_paths = [os.path.abspath(".")]
    
    try:
        await mcp_client.add_mcp_server(
            "stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
        )
        logger.info(f"✓ Added filesystem tool with paths: {workspace_paths}")
    except Exception as e:
        logger.error(f"Failed to add filesystem tool: {e}")
        raise


def create_filesystem_tool_factory(workspace_paths: List[str] = None):
    """
    Create a factory function for the filesystem tool
    
    Args:
        workspace_paths: List of paths to allow access to
        
    Returns:
        Async function that adds filesystem tool to an MCP client
    """
    if workspace_paths is None:
        import os
        workspace_paths = [os.path.abspath(".")]
    
    async def add_to_client(mcp_client: MCPBrainClient):
        return await add_filesystem_tool(mcp_client, workspace_paths)
    
    return add_to_client


class MCPToolConfig:
    """Configuration for different MCP tools"""
    
    FILESYSTEM_DEFAULT = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "workspace_paths": None  # Will be set to current directory at runtime
    }
    
    @staticmethod
    def get_filesystem_config(workspace_paths: List[str] = None) -> Dict[str, Any]:
        """Get filesystem tool configuration"""
        config = MCPToolConfig.FILESYSTEM_DEFAULT.copy()
        if workspace_paths is None:
            import os
            workspace_paths = [os.path.abspath(".")]
        
        config["workspace_paths"] = workspace_paths
        config["args"] = ["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
        return config


# Example usage:
"""
# Initialize MCP client
async def example_usage():
    async with MCPBrainClient() as mcp_client:
        # Add MCP servers
        await mcp_client.add_mcp_server("sse", url="http://localhost:8080/sse")
        
        # Get tools for brain.step
        mcp_tools = mcp_client.get_tools_for_brain()
        
        # Add final answer tool
        final_answer_tool = create_final_answer_tool()
        all_tools = mcp_tools + [final_answer_tool]
        
        # Use with brain.step
        from minion.main.brain import Brain
        from minion.main import LocalPythonEnv
        from minion.providers import create_llm_provider
        
        # Create brain instance (you'll need to configure this)
        # brain = Brain(...)
        
        # obs, score, *_ = await brain.step(
        #     query="what's the solution 234*568",
        #     route="raw",
        #     check=False,
        #     tools=all_tools
        # )
""" 