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


def convert_mcp_to_python_types(obj):
    """Convert MCP types to common Python types for code execution"""
    # Handle None
    if obj is None:
        return None
    
    # Handle basic Python types
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Handle lists
    if isinstance(obj, list):
        return [convert_mcp_to_python_types(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: convert_mcp_to_python_types(value) for key, value in obj.items()}
    
    # Handle MCP TextContent objects
    if hasattr(obj, 'text'):
        return obj.text
    
    # Handle MCP objects with content attribute
    if hasattr(obj, 'content'):
        return convert_mcp_to_python_types(obj.content)
    
    # Handle objects that can be converted to dict (like pydantic models)
    if hasattr(obj, 'model_dump'):
        try:
            return convert_mcp_to_python_types(obj.model_dump())
        except:
            pass
    
    if hasattr(obj, 'dict'):
        try:
            return convert_mcp_to_python_types(obj.dict())
        except:
            pass
    
    # Handle objects with __dict__
    if hasattr(obj, '__dict__'):
        try:
            return convert_mcp_to_python_types(obj.__dict__)
        except:
            pass
    
    # Fallback to string representation
    return str(obj)


def format_mcp_result_new(mcp_output, structured_output: bool = True) -> str:
    """Format MCP CallToolResult to string, based on SmolAgentsAdapter logic"""
    import json
    
    # Early exit for empty content
    if not mcp_output.content:
        raise ValueError("MCP tool returned empty content")
    
    # Handle structured features if enabled
    if structured_output:
        # Prioritize structuredContent if available
        if (
            hasattr(mcp_output, "structuredContent")
            and mcp_output.structuredContent is not None
        ):
            return mcp_output.structuredContent

    
    # Handle multiple content warning (unified for both modes)
    if len(mcp_output.content) > 1:
        warning_msg = (
            f"MCP tool returned multiple content items but no structuredContent. Using the first content item."
            if structured_output
            else f"MCP tool returned multiple content, using the first one"
        )
        logger.warning(warning_msg)
    
    # Get the first content item
    content_item = mcp_output.content[0]
    
    # Handle different content types
    if hasattr(content_item, 'text'):  # TextContent
        text_content = content_item.text
        
        # Always try to parse JSON if structured features are enabled and structuredContent is absent
        if structured_output and text_content:
            try:
                parsed_data = json.loads(text_content)
                return parsed_data
            except json.JSONDecodeError:
                logger.debug(
                    f"MCP tool expected structured output but got unparseable text: {text_content[:100]}..."
                )
                # Fall through to return text as-is for backwards compatibility
        
        # Return simple text content (works for both modes)
        return text_content
    
    else:
        # Handle different content types - following SmolAgentsAdapter logic exactly
        try:
            import mcp.types
            
            if isinstance(content_item, mcp.types.ImageContent):
                try:
                    from PIL import Image
                    import base64
                    from io import BytesIO
                    
                    image_data = base64.b64decode(content_item.data)
                    image = Image.open(BytesIO(image_data))
                    return image
                except ImportError:
                    return f"[ImageContent: {getattr(content_item, 'mimeType', 'unknown')} - PIL not available]"
                except Exception as e:
                    return f"[ImageContent: Error processing image - {str(e)}]"
            
            elif isinstance(content_item, mcp.types.AudioContent):
                try:
                    # Check if torchaudio is available
                    try:
                        import torchaudio
                    except ImportError:
                        return f"[AudioContent: {getattr(content_item, 'mimeType', 'unknown')} - torchaudio not available， please install torchaudio package]"
                    
                    import base64
                    from io import BytesIO
                    
                    audio_data = base64.b64decode(content_item.data)
                    audio_io = BytesIO(audio_data)
                    audio_tensor, _ = torchaudio.load(audio_io)
                    return audio_tensor
                except Exception as e:
                    return f"[AudioContent: Error processing audio - {str(e)}]"
            
            else:
                # Fallback for unknown content types
                raise ValueError(
                    f"tool call returned an unsupported content type: {type(content_item)}"
                )
                #return str(content_item)
                
        except ImportError:
            # If mcp.types is not available, fall back to attribute checking
            if hasattr(content_item, 'data'):  # ImageContent or AudioContent
                content_type = type(content_item).__name__
                return f"[{content_type}: {getattr(content_item, 'mimeType', 'unknown')}]"
            else:
                return str(content_item)


def format_mcp_result(result) -> str:
    """Format MCP tool result for display and code execution"""
    # Convert MCP types to Python types first
    converted = convert_mcp_to_python_types(result)
    
    # If the converted result is a simple type, return it as string
    if isinstance(converted, (str, int, float, bool)):
        return str(converted)
    
    # Special handling for single-item lists containing strings
    if isinstance(converted, list) and len(converted) == 1 and isinstance(converted[0], str):
        return converted[0]
    
    # If it's a list or dict, format it nicely
    if isinstance(converted, (list, dict)):
        import json
        try:
            # For lists of strings, join them with newlines for better readability
            if isinstance(converted, list) and all(isinstance(item, str) for item in converted):
                return '\n'.join(converted)
            else:
                return json.dumps(converted, indent=2, ensure_ascii=False)
        except:
            return str(converted)
    
    # Fallback
    return str(converted)


class AsyncMcpTool(AsyncBaseTool):
    """
    Adapter class to convert MCP tools to brain.step compatible format
    """
    def __init__(self, name: str, description: str, inputs: Dict[str, Any], session: "ClientSession", timeout: float = 10, structured_output: bool = True):
        super().__init__()
        self.tool_name = name
        self.name = name.replace('-', '_') #name should be valid python method name

        self.description = description
        self.inputs = inputs['properties']
        self.session = session
        self.timeout = timeout
        self.structured_output = structured_output

        # Add attributes expected by minion framework
        # Convert hyphens to underscores for Python-compatible function names
        self.__name__ = name
        self.__doc__ = description
        self.__input_schema__ = inputs

    async def forward(self, *args, **kwargs):
        """Execute the tool with given parameters"""
        try:
            # Handle both positional and keyword arguments
            # If there's a single positional argument that's a dict, use it as kwargs
            if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
                kwargs = args[0]
            elif len(args) > 0:
                # If there are positional arguments, we need to map them to parameter names
                # For now, we'll assume the first positional argument is the main parameter
                # This is a simplified approach - in practice, you might want to inspect
                # the tool's input schema to map positional args correctly
                if len(args) == 1 and not kwargs:
                    # Try to determine the parameter name from the schema
                    if self.parameters and 'properties' in self.parameters:
                        param_names = list(self.parameters['properties'].keys())
                        if len(param_names) == 1:
                            kwargs = {param_names[0]: args[0]}
                        else:
                            # Multiple parameters, use the first one or a common name
                            kwargs = {param_names[0]: args[0]}
                    else:
                        # Fallback: use a common parameter name
                        kwargs = {'path': args[0]} if isinstance(args[0], str) else {'input': args[0]}
                else:
                    # Multiple args - this is more complex, for now just pass as is
                    logger.warning(f"Tool {self.name} received multiple positional args, may not work correctly")
            
            async with asyncio.timeout(self.timeout):
                result = await self.session.call_tool(self.name, kwargs)
                # Use the new format function based on structured_output setting
                return format_mcp_result_new(result, self.structured_output)
                    
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


class StreamableHTTPServerParameters:
    """Connection parameters for StreamableHTTP MCP servers"""
    def __init__(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        timeout: Optional[Union[float, timedelta]] = 30,
        sse_read_timeout: Optional[Union[float, timedelta]] = 300,  # 5 minutes
        terminate_on_close: bool = True,
        auth: Optional[Any] = None  # httpx.Auth type
    ):
        self.url = url
        self.headers = headers or {}
        # Convert to timedelta if needed
        self.timeout = timeout if isinstance(timeout, timedelta) else timedelta(seconds=timeout) if timeout else timedelta(seconds=30)
        self.sse_read_timeout = sse_read_timeout if isinstance(sse_read_timeout, timedelta) else timedelta(seconds=sse_read_timeout) if sse_read_timeout else timedelta(seconds=300)
        self.terminate_on_close = terminate_on_close
        self.auth = auth


class MCPToolset(Toolset):
    """
    Simplified MCP toolset that follows Google ADK pattern.
    Can be passed directly in the tools parameter when creating an agent.
    """
    
    def __init__(
        self, 
        connection_params: Union[StdioServerParameters, SSEServerParameters, StreamableHTTPServerParameters], 
        name: Optional[str] = None,
        setup_timeout: float = 10,  # 10 seconds timeout for setup
        session_timeout: float = 10,  # 10 seconds timeout for session operations
        ignore_setup_errors: bool = False,  # Whether to ignore setup errors
        structured_output: bool = True,  # Enable structured output by default
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
        self.structured_output = structured_output

    @property
    def is_healthy(self) -> bool:
        """Return True if the toolset is setup and healthy"""
        return self._is_setup and not self._setup_error

    @property
    def setup_error(self) -> Optional[Exception]:
        """Return the setup error if any"""
        return self._setup_error

    async def setup(self):
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
            
        elif isinstance(self.connection_params, StreamableHTTPServerParameters):
            try:
                from mcp.client.streamable_http import streamablehttp_client  # type: ignore
            except ImportError as e:
                logger.error(f"MCP streamable HTTP client not available: {e}")
                raise RuntimeError(f"MCP streamable HTTP client not available: {e}")
            
            logger.info(f"Connecting to StreamableHTTP MCP server: {self.connection_params.url}")
            
            client_kwargs = {"url": self.connection_params.url}
            if self.connection_params.headers:
                client_kwargs["headers"] = self.connection_params.headers
            if self.connection_params.timeout is not None:
                client_kwargs["timeout"] = self.connection_params.timeout
            if self.connection_params.sse_read_timeout is not None:
                client_kwargs["sse_read_timeout"] = self.connection_params.sse_read_timeout
            if hasattr(self.connection_params, 'terminate_on_close'):
                client_kwargs["terminate_on_close"] = self.connection_params.terminate_on_close
            if hasattr(self.connection_params, 'auth') and self.connection_params.auth is not None:
                client_kwargs["auth"] = self.connection_params.auth
            
            read, write, get_session_id = await self._exit_stack.enter_async_context(streamablehttp_client(**client_kwargs))
            
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
                inputs=tool.inputSchema,
                session=session,
                structured_output=self.structured_output
            )
            self.tools.append(mcp_tool)
        self._is_setup = True
        logger.info(f"MCPToolset '{self.name}' setup completed with {len(self.tools)} tools")

    async def ensure_setup(self) -> None:
        """Ensure toolset is setup, with timeout handling"""
        if self._is_setup:
            return

        try:
            async with asyncio.timeout(self._setup_timeout):
                await self.setup()
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
async def create_filesystem_toolset(workspace_paths: Optional[List[str]] = None, name: Optional[str] = None, structured_output: bool = True) -> MCPToolset:
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
    
    toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"] + workspace_paths
        ),
        name=name or "filesystem_toolset",
        structured_output=structured_output
    )
    await toolset.setup()
    return toolset


async def create_brave_search_toolset(api_key: str, name: Optional[str] = None, structured_output: bool = True) -> MCPToolset:
    """
    Create a Brave Search MCP toolset
    
    Args:
        api_key: Brave Search API key
        name: Optional name for the toolset
        
    Returns:
        MCPToolset configured for Brave Search
    """
    toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": api_key}
        ),
        name=name or "brave_search_toolset",
        structured_output=structured_output
    )
    await toolset.setup()
    return toolset


async def create_streamable_http_toolset(
    url: str, 
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[Union[float, timedelta]] = 30,
    sse_read_timeout: Optional[Union[float, timedelta]] = 300,
    terminate_on_close: bool = True,
    auth: Optional[Any] = None,
    name: Optional[str] = None, 
    structured_output: bool = True
) -> MCPToolset:
    """
    Create a StreamableHTTP MCP toolset
    
    Args:
        url: The URL of the StreamableHTTP server
        headers: Optional headers for the HTTP connection
        timeout: Connection timeout (float in seconds or timedelta)
        sse_read_timeout: SSE read timeout (float in seconds or timedelta)
        terminate_on_close: Whether to terminate on close
        auth: Optional httpx.Auth authentication
        name: Optional name for the toolset
        structured_output: Enable structured output
        
    Returns:
        MCPToolset configured for StreamableHTTP connection
    """
    toolset = MCPToolset(
        connection_params=StreamableHTTPServerParameters(
            url=url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            terminate_on_close=terminate_on_close,
            auth=auth
        ),
        name=name or "streamable_http_toolset",
        structured_output=structured_output
    )
    await toolset.setup()
    return toolset