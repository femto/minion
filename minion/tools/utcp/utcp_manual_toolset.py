import logging
import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

from minion.tools import AsyncBaseTool, Toolset

logger = logging.getLogger(__name__)

DEBUG = False  # Set to True for debug output


def format_tools_for_bedrock(tools: List[AsyncBaseTool]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Convert minion AsyncBaseTool tools to Bedrock tool format.
    
    Args:
        tools: List of minion AsyncBaseTool tools
        
    Returns:
        Tuple containing:
        - List of tools formatted for Bedrock
        - Mapping between modified tool names and original names
    """
    bedrock_tools = []
    tool_name_mapping = {}
    
    for tool in tools:
        # Create the input schema JSON from tool.inputs
        input_schema_json = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Add inputs to the input schema
        if hasattr(tool, 'inputs') and tool.inputs:
            input_schema_json["properties"] = tool.inputs
            # Extract required fields from tool inputs
            # In minion framework, we need to determine required fields
            # This could be based on tool signature or explicit marking
            required_fields = []
            for field_name, field_info in tool.inputs.items():
                # Check if field is marked as required (you may need to adjust this logic)
                if isinstance(field_info, dict) and not field_info.get("nullable", False):
                    required_fields.append(field_name)
            input_schema_json["required"] = required_fields
        
        # Replace periods in tool name with underscores
        original_name = tool.name
        bedrock_tool_name = original_name.replace(".", "_")
        
        # Truncate if longer than 64 characters (Bedrock's limit)
        if len(bedrock_tool_name) > 64:
            short_uuid = str(uuid.uuid4())[:8]
            short_name = f"{bedrock_tool_name[:55]}_{short_uuid}"
            if DEBUG:
                print(f"Tool name '{bedrock_tool_name}' is too long, using '{short_name}' instead")
            bedrock_tool_name = short_name
        
        # Store the mapping between the modified name and original name
        tool_name_mapping[bedrock_tool_name] = original_name
        
        # Format the tool for Bedrock
        tool_spec = {
            "name": bedrock_tool_name,
            "description": tool.description,
            "inputSchema": {
                "json": input_schema_json
            }
        }
        
        bedrock_tools.append({"toolSpec": tool_spec})
    
    return bedrock_tools, tool_name_mapping


class AsyncUtcpTool(AsyncBaseTool):
    """
    Adapter class to convert UTCP tools to minion framework compatible format
    """
    
    def __init__(self, name: str, description: str, utcp_tool, utcp_client, original_name: str):
        super().__init__()
        self.name = name.replace(".", "_")  # Replace dots with underscores for valid method names
        self.description = description
        self.utcp_client = utcp_client
        self.original_name = original_name  # Keep original name for UTCP calls
        self.utcp_tool = utcp_tool  # Store the original UTCP tool
        
        # Convert UTCP tool inputs to minion format
        self.inputs = self._convert_utcp_inputs_to_minion_format(utcp_tool)
        
        # Add attributes expected by minion framework
        self.__name__ = self.name
        self.__doc__ = description
        self.__input_schema__ = self.inputs
    
    def _convert_utcp_inputs_to_minion_format(self, utcp_tool) -> Dict[str, Dict[str, Any]]:
        """
        Convert UTCP tool inputs to minion framework format
        
        Args:
            utcp_tool: The original UTCP tool object
            
        Returns:
            Dict in minion format for tool inputs
        """
        minion_inputs = {}
        
        # Extract inputs from UTCP tool
        if hasattr(utcp_tool, 'inputs') and utcp_tool.inputs:
            if hasattr(utcp_tool.inputs, 'properties') and utcp_tool.inputs.properties:
                for field_name, field_info in utcp_tool.inputs.properties.items():
                    # Convert UTCP field format to minion format
                    minion_field = {}
                    
                    if hasattr(field_info, 'type'):
                        minion_field["type"] = field_info.type
                    if hasattr(field_info, 'description'):
                        minion_field["description"] = field_info.description
                    
                    # Check if field is required
                    required_fields = getattr(utcp_tool.inputs, 'required', [])
                    if field_name not in required_fields:
                        minion_field["nullable"] = True
                    
                    minion_inputs[field_name] = minion_field
        
        return minion_inputs

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

    async def setup(self):
        """Internal setup method that does the actual work"""
        # Initialize UTCP client
        self._utcp_client = await self.initialize_utcp_client()
        
        # Get available tools from UTCP client
        try:
            # Assuming UTCP client has a method to list available tools
            # This might need to be adjusted based on actual UTCP API
            tools_info = await self._utcp_client.search_tools("Please give me all tools")
            logger.info(f"Connected to UTCP with {len(tools_info)} tools")
            
            # Convert to AsyncUtcpTool objects
            self.tools = []
            for tool_info in tools_info:
                # Extract tool information - adjust based on actual UTCP tool format
                original_name = tool_info.name
                safe_name = original_name.replace(".", "_")  # Make name valid for method calls
                description = tool_info.description
                
                utcp_tool = AsyncUtcpTool(
                    name=safe_name,
                    description=description,
                    utcp_tool=tool_info,  # Pass the entire UTCP tool object
                    utcp_client=self._utcp_client,
                    original_name=original_name
                )
                self.tools.append(utcp_tool)
            
            logger.info(f"UtcpManualToolset '{self.name}' setup completed with {len(self.tools)} tools")
            
        except AttributeError:
            # If list_tools method doesn't exist, we'll need to handle this differently
            logger.warning("UTCP client doesn't have list_tools method, creating empty toolset")
            self.tools = []
        self._is_setup = True

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
    await toolset.ensure_setup()
    
    return toolset