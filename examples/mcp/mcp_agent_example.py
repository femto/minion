#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP Agent Integration Example

This example shows how to integrate MCP filesystem toolset with a minion agent.
"""

import asyncio
import logging
from pathlib import Path
from typing import Union

from minion.agents import CodeAgent
from minion.tools.mcp.mcp_toolset import create_filesystem_toolset
from minion.agents.base_agent import BaseAgent
from minion.providers.openai_provider import OpenAIProvider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function showing MCP integration with agent"""
    
    try:
        # Create MCP filesystem toolset (async - automatically sets up)
        print("Creating and setting up MCP filesystem toolset...")
        workspace_paths = [str(Path(__file__).parent.parent.parent)]  # Project root
        mcp_toolset = await create_filesystem_toolset(
            workspace_paths=workspace_paths,
            name="agent_mcp_filesystem_toolset"
        )
        
        if not mcp_toolset.is_healthy:
            print(f"❌ MCP toolset setup failed: {mcp_toolset.setup_error}")
            return
            
        print(f"✅ MCP toolset ready with {len(mcp_toolset.tools)} tools")
        
        # Get MCP tools
        mcp_tools = mcp_toolset.get_tools()
        
        # Add simple function tools (minion will auto-convert them)
        custom_tools = [calc, async_func]
        
        # Combine all tools
        all_tools = mcp_tools + custom_tools
        
        # Create agent with all tools (MCP + custom functions)
        agent = await CodeAgent.create(
            llm="gpt-4o",
            tools=all_tools,
            name="Enhanced MCP Agent"
        )
        
        # Example conversations
        print("\n🤖 Starting conversation with enhanced MCP agent...")
        
        # Test filesystem operations
        print("\n📁 Testing filesystem operations:")
        response = await agent.run_async("Can you list the files in the current directory?")
        print(response.answer)
        
        # Test synchronous calc tool
        print("\n🧮 Testing synchronous calc tool:")
        response = await agent.run_async("Calculate 15 + 27 using the calc tool")
        print(response.answer)
        
        # Test asynchronous func tool
        print("\n⚡ Testing asynchronous func tool:")
        response = await agent.run_async("Use the async_func tool to process the message 'hello world' with a 2 second delay")
        print(response.answer)
            
    except Exception as e:
        print(f"❌ Error during MCP agent example: {e}")
        logger.exception("Full error details:")
        
    finally:
        # Clean up
        if 'mcp_toolset' in locals():
            print("Cleaning up MCP toolset...")
            await mcp_toolset.close()


if __name__ == "__main__":
    asyncio.run(main())