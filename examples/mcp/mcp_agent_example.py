#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP Agent Integration Example

This example shows how to integrate MCP filesystem toolset with a minion agent.
"""

import asyncio
import logging
from pathlib import Path

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
        
        # Get tools for agent
        mcp_tools = mcp_toolset.get_tools()
        
        # Create agent with MCP tools
        agent = await CodeAgent.create(
            llm="gpt-4o",
            tools=mcp_tools,  # Pass MCP tools directly
            name="MCP Filesystem Agent"
        )
        
        # Example conversation
        print("\n🤖 Starting conversation with MCP-enabled agent...")
        
        # Test with filesystem operations
        response = await agent.run_async("Can you list the files in the current directory and tell me what this project is about based on the README.md file?")
        print(f"Agent response: {response.content}")
            
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