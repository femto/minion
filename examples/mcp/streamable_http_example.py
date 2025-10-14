#!/usr/bin/env python3
"""
Example demonstrating StreamableHTTP MCP toolset usage
"""

import asyncio
import logging
from datetime import timedelta

from minion.tools.mcp.mcp_toolset import (
    MCPToolset, 
    StreamableHTTPServerParameters,
    create_streamable_http_toolset
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_streamable_http_basic():
    """Basic example using StreamableHTTPServerParameters directly"""
    
    # Create connection parameters
    params = StreamableHTTPServerParameters(
        url="http://localhost:3000/mcp",
        timeout=timedelta(seconds=30),
        sse_read_timeout=timedelta(minutes=5),
        terminate_on_close=True
    )
    
    # Create toolset
    toolset = MCPToolset(
        connection_params=params,
        name="my_http_toolset",
        structured_output=True
    )
    
    try:
        # Setup the toolset
        await toolset.ensure_setup()
        
        if toolset.is_healthy:
            # Get available tools
            tools = toolset.get_tools()
            logger.info(f"Available tools: {[tool.name for tool in tools]}")
            
            # Example tool usage with the actual available tool
            if tools:
                first_tool = tools[0]
                logger.info(f"Using tool: {first_tool.name}")
                
                # Call the notification stream tool with proper parameters
                if first_tool.name == "start-notification-stream":
                    result = await first_tool.forward(
                        interval=1.0,
                        count=3,
                        caller="streamable_http_example"
                    )
                    logger.info(f"Tool result: {result}")
                else:
                    logger.info(f"Tool {first_tool.name} requires specific parameters")
        else:
            logger.error(f"Toolset setup failed: {toolset.setup_error}")
            
    finally:
        # Clean up
        await toolset.close()


async def example_streamable_http_factory():
    """Example using the factory function"""
    
    try:
        # Create toolset using factory function
        toolset = await create_streamable_http_toolset(
            url="http://localhost:3000/mcp",
            headers={"Content-Type": "application/json"},
            timeout=30.0,  # Can use float for seconds
            sse_read_timeout=300.0,  # 5 minutes
            terminate_on_close=True,
            name="factory_http_toolset"
        )
        
        # Get tools
        tools = toolset.get_tools()
        logger.info(f"Factory toolset has {len(tools)} tools")
        
        # Use tools as needed
        for tool in tools:
            logger.info(f"Tool: {tool.name} - {tool.description}")
            
    except Exception as e:
        logger.error(f"Failed to create streamable HTTP toolset: {e}")
    finally:
        if 'toolset' in locals():
            await toolset.close()


async def example_with_authentication():
    """Example with HTTP authentication (demonstrates configuration only)"""
    
    logger.info("This example shows authentication configuration (no actual connection)")
    
    # Example configuration with authentication
    try:
        # Note: You would need to import httpx for actual auth objects
        # import httpx
        # auth = httpx.BasicAuth("username", "password")
        
        # This would be the configuration for an authenticated server
        logger.info("Example authenticated toolset configuration:")
        logger.info("  URL: https://secure-api.example.com/mcp")
        logger.info("  Headers: User-Agent, Accept, Authorization")
        logger.info("  Timeout: 60 seconds")
        logger.info("  Auth: httpx.BasicAuth or httpx.BearerAuth")
        
        # Uncomment below to test with a real authenticated server:
        """
        toolset = await create_streamable_http_toolset(
            url="https://your-secure-server.com/mcp",
            headers={
                "User-Agent": "MCP-Client/1.0",
                "Accept": "application/json"
            },
            timeout=timedelta(seconds=60),
            sse_read_timeout=timedelta(minutes=10),
            # auth=httpx.BasicAuth("username", "password"),
            name="authenticated_toolset"
        )
        
        tools = toolset.get_tools()
        logger.info(f"Authenticated toolset provides {len(tools)} tools")
        await toolset.close()
        """
        
    except Exception as e:
        logger.error(f"Authentication example failed: {e}")


async def main():
    """Run all examples"""
    logger.info("=== StreamableHTTP MCP Toolset Examples ===")
    
    logger.info("\n1. Basic StreamableHTTP example:")
    try:
        await example_streamable_http_basic()
    except Exception as e:
        logger.error(f"Basic example failed: {e}")
    
    logger.info("\n2. Factory function example:")
    try:
        await example_streamable_http_factory()
    except Exception as e:
        logger.error(f"Factory example failed: {e}")
    
    logger.info("\n3. Authentication example:")
    try:
        await example_with_authentication()
    except Exception as e:
        logger.error(f"Authentication example failed: {e}")
    
    logger.info("\n=== Examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())