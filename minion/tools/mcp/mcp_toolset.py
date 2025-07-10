import json
import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union, overload, Callable

from typing_extensions import NotRequired, TypeAlias, TypedDict, Unpack

from minion.tools import BaseTool
from .mcp_integration import BrainTool, format_mcp_result

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


class MCPToolSet:
    """
    MCP工具集，参考Google ADK Python的ToolSet设计
    绑定到agent的生命周期，在agent setup时创建，agent close时清理
    """
    
    def __init__(self, name: str = "mcp_toolset"):
        """
        初始化MCP工具集
        
        Args:
            name: 工具集名称
        """
        self.name = name
        # Initialize MCP sessions as a dictionary of ClientSession objects
        self.sessions: Dict[ToolName, Any] = {}  # Use Any for ClientSession type
        self.exit_stack: Optional[AsyncExitStack] = None
        self.available_tools: List[BrainTool] = []
        self._is_initialized = False

    async def setup(self):
        """
        设置MCP工具集，在agent setup时调用
        """
        if self._is_initialized:
            logger.warning(f"MCPToolSet {self.name} already initialized")
            return
            
        self.exit_stack = AsyncExitStack()
        await self.exit_stack.__aenter__()
        self._is_initialized = True
        logger.info(f"MCPToolSet {self.name} initialized")

    async def close(self):
        """
        清理MCP工具集资源，在agent close时调用
        """
        if not self._is_initialized:
            logger.warning(f"MCPToolSet {self.name} not initialized, skipping cleanup")
            return
            
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
                logger.info(f"MCPToolSet {self.name} cleanup completed")
            except Exception as e:
                logger.error(f"Error during MCPToolSet {self.name} cleanup: {e}")
            finally:
                self.exit_stack = None
                self.sessions.clear()
                self.available_tools.clear()
                self._is_initialized = False

    async def __aenter__(self):
        """Enter the context manager"""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager"""
        await self.close()

    @property
    def is_initialized(self) -> bool:
        """检查工具集是否已初始化"""
        return self._is_initialized

    def _ensure_initialized(self):
        """确保工具集已初始化"""
        if not self._is_initialized:
            raise RuntimeError(f"MCPToolSet {self.name} not initialized. Call setup() first.")

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
        self._ensure_initialized()
        
        if not self.exit_stack:
            raise RuntimeError("exit_stack is not initialized")
            
        try:
            from mcp import ClientSession, StdioServerParameters  # type: ignore
            from mcp import types as mcp_types  # type: ignore
        except ImportError as e:
            logger.error(f"MCP library not available: {e}")
            raise RuntimeError(f"MCP library not available: {e}")

        # Determine server type and create appropriate parameters
        if type == "stdio":
            # Handle stdio server
            try:
                from mcp.client.stdio import stdio_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP stdio client not available: {e}")
                raise RuntimeError(f"MCP stdio client not available: {e}")

            logger.info(f"Connecting to stdio MCP server with command: {params['command']} {params.get('args', [])}")

            client_kwargs = {"command": params["command"]}
            for key in ["args", "env", "cwd"]:
                if params.get(key) is not None:
                    client_kwargs[key] = params[key]
            server_params = StdioServerParameters(**client_kwargs)
            read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        elif type == "sse":
            # Handle SSE server
            try:
                from mcp.client.sse import sse_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP SSE client not available: {e}")
                raise RuntimeError(f"MCP SSE client not available: {e}")

            logger.info(f"Connecting to SSE MCP server at: {params['url']}")

            client_kwargs = {"url": params["url"]}
            for key in ["headers", "timeout", "sse_read_timeout"]:
                if params.get(key) is not None:
                    client_kwargs[key] = params[key]
            read, write = await self.exit_stack.enter_async_context(sse_client(**client_kwargs))
        elif type == "http":
            # Handle StreamableHTTP server
            try:
                from mcp.client.streamable_http import streamablehttp_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP HTTP client not available: {e}")
                raise RuntimeError(f"MCP HTTP client not available: {e}")

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
                    name=f"minion.{self.name}",
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

    def get_tools(self) -> List[BrainTool]:
        """获取工具集中的所有工具"""
        self._ensure_initialized()
        return self.available_tools.copy()

    def get_tool_functions(self) -> Dict[str, Callable]:
        """Get dictionary of tool functions for direct execution"""
        self._ensure_initialized()
        return {tool.name: tool for tool in self.available_tools}

    def get_tool_specs(self) -> List[Dict[str, Any]]:
        """Get list of tool specifications in ChatCompletion format"""
        self._ensure_initialized()
        return [tool.to_function_spec() for tool in self.available_tools]

    def get_tools_dict(self) -> List[Dict[str, Any]]:
        """Get list of tools as dictionaries"""
        self._ensure_initialized()
        return [tool.to_dict() for tool in self.available_tools]

    async def add_filesystem_tool(self, workspace_paths: Optional[List[str]] = None) -> None:
        """
        Add filesystem MCP tool to the toolset
        
        Args:
            workspace_paths: List of paths to allow access to. Defaults to current directory.
        """
        self._ensure_initialized()
        
        if workspace_paths is None:
            import os
            workspace_paths = [os.path.abspath(".")]
        
        try:
            await self.add_mcp_server(
                "stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
            )
            logger.info(f"✓ Added filesystem tool with paths: {workspace_paths}")
        except Exception as e:
            logger.error(f"Failed to add filesystem tool: {e}")
            raise


class MCPToolConfig:
    """Configuration for different MCP tools"""
    
    FILESYSTEM_DEFAULT = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "workspace_paths": None  # Will be set to current directory at runtime
    }
    
    @staticmethod
    def get_filesystem_config(workspace_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get filesystem tool configuration"""
        config = MCPToolConfig.FILESYSTEM_DEFAULT.copy()
        if workspace_paths is None:
            import os
            workspace_paths = [os.path.abspath(".")]
        
        config["workspace_paths"] = workspace_paths
        config["args"] = ["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
        return config


def create_filesystem_toolset_factory(workspace_paths: Optional[List[str]] = None):
    """
    Create a factory function for the filesystem toolset
    
    Args:
        workspace_paths: List of paths to allow access to
        
    Returns:
        Async function that creates and sets up a filesystem toolset
    """
    if workspace_paths is None:
        import os
        workspace_paths = [os.path.abspath(".")]
    
    async def create_toolset() -> MCPToolSet:
        toolset = MCPToolSet("filesystem_toolset")
        await toolset.setup()
        await toolset.add_filesystem_tool(workspace_paths)
        return toolset
    
    return create_toolset