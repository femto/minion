import logging
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from minion.tools import AsyncBaseTool, Toolset

logger = logging.getLogger(__name__)


class AsyncUtcpTool(AsyncBaseTool):
    """
    Adapter class to convert UTCP tools to minion framework compatible format
    """
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], utcp_client, original_name: str):
        super().__init__()
        self.name = name.replace(".", "_")  # Replace dots with underscores for valid method names
        self.description = description
        self.parameters = parameters
        self.utcp_client = utcp_client
        self.original_name = original_name  # Keep original name for UTCP calls
        
        # Add attributes expected by minion framework
        self.__name__ = self.name
        self.__doc__ = description
        self.__input_schema__ = parameters

    async def forward(self, **kwargs) -> Dict[str, Any]:
        """Execute the UTCP tool with given parameters"""
        try:
            logger.info(f"Executing tool call: {self.original_name}")
            result = await self.utcp_client.call_tool(self.original_name, kwargs)
            logger.info(f"Tool execution successful!")
            logger.info(f"Result: {result}")
            
            # Format the tool result as expected by the framework
            return result
        except Exception as e:
            logger.error(f"Error executing UTCP tool {self.original_name}: {e}")
            return {"error": f"Error: {str(e)}"}

class UtcpManualToolset(Toolset):
    """
    UTCP toolset that follows Google ADK pattern.
    Can be passed directly in the tools parameter when creating an agent.
    """
    
    def __init__(
        self, 
        config: Optional[Union[str, Path, Dict[str, Any]]] = None,
        root_dir: Optional[str] = None,
        name: Optional[str] = None,
        setup_timeout: float = 30,  # 30 seconds timeout for setup
        ignore_setup_errors: bool = False,
    ):
        """
        Initialize UtcpManualToolset with configuration
        
        Args:
            config: UTCP configuration - can be a path to config file, dict config, or UtcpClientConfig
            root_dir: Root directory for UTCP client
            name: Optional name for the toolset
            setup_timeout: Timeout in seconds for toolset setup
            ignore_setup_errors: If True, setup errors will be logged but not raised
        """
        # Initialize with empty tools list first
        super().__init__([])
        
        self.config = config
        self.root_dir = root_dir
        self.name = name or f"utcp_toolset_{id(self)}"
        self._utcp_client = None
        self._is_setup = False
        self._setup_timeout = setup_timeout
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

    async def initialize_utcp_client(self):
        """Initialize the UTCP client with configuration."""
        try:
            from utcp.utcp_client import UtcpClient
            #from utcp.data.utcp_client_config import UtcpClientConfigSerializer
            from utcp.data.tool import Tool
        except ImportError as e:
            logger.error(f"UTCP library not available: {e}")
            raise RuntimeError(f"UTCP library not available: {e}")
        
        # Use provided config or default to providers.json in same directory
        config = self.config

        logger.info(f"Initializing UTCP client with config: {config}")
        client = await UtcpClient.create(
            root_dir=self.root_dir,
            config=config
        )
        return client

    async def _setup(self):
        """Internal setup method that does the actual work"""
        # Initialize UTCP client
        self._utcp_client = await self.initialize_utcp_client()
        
        # Get available tools from UTCP client
        try:
            # Assuming UTCP client has a method to list available tools
            # This might need to be adjusted based on actual UTCP API
            tools_info = await self._utcp_client.list_tools()
            logger.info(f"Connected to UTCP with {len(tools_info)} tools")
            
            # Convert to AsyncUtcpTool objects
            self.tools = []
            for tool_info in tools_info:
                # Extract tool information - adjust based on actual UTCP tool format
                original_name = tool_info.get("name", "")
                safe_name = original_name.replace(".", "_")  # Make name valid for method calls
                description = tool_info.get("description", "")
                parameters = tool_info.get("parameters", {})
                
                utcp_tool = AsyncUtcpTool(
                    name=safe_name,
                    description=description,
                    parameters=parameters,
                    utcp_client=self._utcp_client,
                    original_name=original_name
                )
                self.tools.append(utcp_tool)
            
            logger.info(f"UtcpManualToolset '{self.name}' setup completed with {len(self.tools)} tools")
            
        except AttributeError:
            # If list_tools method doesn't exist, we'll need to handle this differently
            logger.warning("UTCP client doesn't have list_tools method, creating empty toolset")
            self.tools = []

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
            logger.error(f"Failed to setup UtcpManualToolset {self.name}: {e}")
            if not self._ignore_setup_errors:
                raise

    def get_tools(self) -> List[AsyncBaseTool]:
        """
        Get list of tools, returns empty list if setup failed and errors are ignored
        """
        if not self.is_healthy:
            logger.warning(f"UtcpManualToolset {self.name} is not healthy, returning empty tool list")
            return []
        return self.tools

    async def close(self):
        """Close the toolset and clean up resources"""
        if self._utcp_client:
            # Close UTCP client if it has a close method
            if hasattr(self._utcp_client, 'close'):
                await self._utcp_client.close()
            self._utcp_client = None
            self._is_setup = False
        self.tools.clear()
        logger.info(f"UtcpManualToolset '{self.name}' closed")

    def __repr__(self):
        return f"UtcpManualToolset(name={self.name}, setup={self._is_setup})"


# Factory function for creating UTCP toolset
async def create_utcp_toolset(
    config: Optional[Union[str, Path, Dict[str, Any]]] = None,
    root_dir: Optional[str] = None,
    name: Optional[str] = None
) -> UtcpManualToolset:
    """
    Create a UTCP toolset and set it up
    
    Args:
        config: UTCP configuration - can be a path to config file, dict config, or UtcpClientConfig
        root_dir: Root directory for UTCP client
        name: Optional name for the toolset
        
    Returns:
        UtcpManualToolset configured and setup with the provided parameters
    """
    toolset = UtcpManualToolset(
        config=config,
        root_dir=root_dir,
        name=name or "utcp_toolset"
    )
    
    # Automatically setup the toolset
    await toolset._ensure_setup()
    
    return toolset