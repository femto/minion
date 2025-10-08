import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
import os
import asyncio
from datetime import timedelta

from minion.tools import AsyncBaseTool
from minion.tools.base_tool import Toolset
from minion.tools.base_tool import Toolset

if TYPE_CHECKING:
    from mcp import ClientSession

logger = logging.getLogger(__name__)


def format_mcp_result(result) -> str:
    """Format MCP tool result for display"""
    if hasattr(result, 'content'):
        return result.content
    elif isinstance(result, list):
        return '\n'.join(str(item) for item in result)
    else:
        return str(result)


class AsyncMcpTool(AsyncBaseTool):
    """
    Adapter class to convert MCP tools to brain.step compatible format
    """
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], session: "ClientSession", timeout: float = 10):
        super().__init__()
        self.name = name
        self.description = description
        self.parameters = parameters
        self.session = session
        self.timeout = timeout

        # Add attributes expected by minion framework
        self.__name__ = name
        self.__doc__ = description
        self.__input_schema__ = parameters

    async def forward(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.session.call_tool(self.name, kwargs)
                return format_mcp_result(result)
        except asyncio.TimeoutError:
            error_msg = f"Tool {self.name} execution timed out after {self.timeout} seconds"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            return f"Error: {str(e)}"


class StdioServerParameters:
    """Connection parameters for stdio MCP servers"""
    def __init__(self, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None, cwd: Optional[Union[str, Path]] = None):
        self.command = command
        self.args = args or []
        # Merge with current environment variables instead of replacing
        self.env = {**os.environ, **(env or {})}
        self.cwd = cwd


class SSEServerParameters:
    """Connection parameters for SSE MCP servers"""
    def __init__(self, url: str, headers: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, sse_read_timeout: Optional[float] = None):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout


class MCPToolset(Toolset):
    """
    Simplified MCP toolset that follows Google ADK pattern.
    Can be passed directly in the tools parameter when creating an agent.
    """
    
    def __init__(
        self, 
        connection_params: Union[StdioServerParameters, SSEServerParameters], 
        name: Optional[str] = None,
        setup_timeout: float = 10,  # 10 seconds timeout for setup
        session_timeout: float = 10,  # 10 seconds timeout for session operations
        ignore_setup_errors: bool = False,  # Whether to ignore setup errors
    ):
        """
        Initialize MCPToolset with connection parameters
        
        Args:
            connection_params: Either StdioServerParameters or SSEServerParameters
            name: Optional name for the toolset
            setup_timeout: Timeout in seconds for toolset setup
            session_timeout: Timeout in seconds for all session operations (tool calls, etc)
            ignore_setup_errors: If True, setup errors will be logged but not raised
        """
        # Initialize with empty tools list first
        super().__init__([])
        
        self.connection_params = connection_params
        self.name = name or f"mcp_toolset_{id(self)}"
        self._exit_stack: Optional[AsyncExitStack] = None
        self._is_setup = False
        self._setup_timeout = setup_timeout
        self._session_timeout = timedelta(seconds=session_timeout)  # Convert to timedelta
        self._ignore_setup_errors = ignore_setup_errors
        self._setup_error: Optional[Exception] = None

    @property
    def is_healthy(self) -> bool:
        """Return True if the toolset is setup and healthy"""
        return self._is_setup and not self._setup_error

    @property
    def setup_error(self) -> Optional[Exception]:
        """Return the setup error if any"""
        return self._setup_error

    async def _setup(self):
        """Internal setup method that does the actual work"""
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        
        try:
            from mcp import ClientSession, StdioServerParameters as MCPStdioParams  # type: ignore
            from datetime import timedelta  # Add import at top of file
        except ImportError as e:
            logger.error(f"MCP library not available: {e}")
            raise RuntimeError(f"MCP library not available: {e}")
        
        # Connect to MCP server
        if isinstance(self.connection_params, StdioServerParameters):
            try:
                from mcp.client.stdio import stdio_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP stdio client not available: {e}")
                raise RuntimeError(f"MCP stdio client not available: {e}")
            
            logger.info(f"Connecting to stdio MCP server: {self.connection_params.command} {self.connection_params.args}")
            
            server_params = MCPStdioParams(
                command=self.connection_params.command,
                args=self.connection_params.args,
                env=self.connection_params.env,
                cwd=self.connection_params.cwd
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            
        elif isinstance(self.connection_params, SSEServerParameters):
            try:
                from mcp.client.sse import sse_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP SSE client not available: {e}")
                raise RuntimeError(f"MCP SSE client not available: {e}")
            
            logger.info(f"Connecting to SSE MCP server: {self.connection_params.url}")
            
            client_kwargs = {"url": self.connection_params.url}
            if self.connection_params.headers:
                client_kwargs["headers"] = self.connection_params.headers
            if self.connection_params.timeout is not None:
                client_kwargs["timeout"] = self.connection_params.timeout
            if self.connection_params.sse_read_timeout is not None:
                client_kwargs["sse_read_timeout"] = self.connection_params.sse_read_timeout
            
            read, write = await self._exit_stack.enter_async_context(sse_client(**client_kwargs))
        else:
            raise ValueError(f"Unsupported connection parameters type: {type(self.connection_params)}")
        
        # Create session with timeout
        session = await self._exit_stack.enter_async_context(
            ClientSession(
                read_stream=read, 
                write_stream=write,
                read_timeout_seconds=self._session_timeout  # Now it's a timedelta
            )
        )
        
        # Initialize session
        await session.initialize()
        
        # Get tools
        response = await session.list_tools()
        logger.info(f"Connected to MCP server with {len(response.tools)} tools")
        
        # Convert to AsyncMcpTool objects - no need to pass timeout since it's handled by session
        self.tools = []
        for tool in response.tools:
            mcp_tool = AsyncMcpTool(
                name=tool.name,
                description=tool.description,
                parameters=tool.inputSchema,
                session=session
            )
            self.tools.append(mcp_tool)
        
        logger.info(f"MCPToolset '{self.name}' setup completed with {len(self.tools)} tools")

    async def _ensure_setup(self) -> None:
        """Ensure toolset is setup, with timeout handling"""
        if self._is_setup:
            return

        try:
            async with asyncio.timeout(self._setup_timeout):
                await self._setup()
                self._is_setup = True
                self._setup_error = None
        except Exception as e:
            self._setup_error = e
            logger.error(f"Failed to setup MCPToolset {self.name}: {e}")
            if not self._ignore_setup_errors:
                raise

    def get_tools(self) -> List[AsyncBaseTool]:
        """
        Get list of tools, returns empty list if setup failed and errors are ignored
        """
        if not self.is_healthy:
            logger.warning(f"MCPToolset {self.name} is not healthy, returning empty tool list")
            return []
        return self.tools

    async def close(self):
        """Close the toolset and clean up resources"""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._is_setup = False
        self.tools.clear()
        logger.info(f"MCPToolset '{self.name}' closed")

    def __repr__(self):
        return f"MCPToolset(name={self.name}, setup={self._is_setup})"


# Factory functions for common MCP servers
def create_filesystem_toolset(workspace_paths: Optional[List[str]] = None, name: Optional[str] = None) -> MCPToolset:
    """
    Create a filesystem MCP toolset
    
    Args:
        workspace_paths: List of paths to allow access to
        name: Optional name for the toolset
        
    Returns:
        MCPToolset configured for filesystem access
    """
    if workspace_paths is None:
        import os
        workspace_paths = [os.path.abspath(".")]
    else:
        import os
        # Convert all paths to absolute paths
        workspace_paths = [os.path.abspath(path) for path in workspace_paths]
    
    return MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
        ),
        name=name or "filesystem_toolset"
    )


def create_brave_search_toolset(api_key: str, name: Optional[str] = None) -> MCPToolset:
    """
    Create a Brave Search MCP toolset
    
    Args:
        api_key: Brave Search API key
        name: Optional name for the toolset
        
    Returns:
        MCPToolset configured for Brave Search
    """
    return MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": api_key}
        ),
        name=name or "brave_search_toolset"
    )