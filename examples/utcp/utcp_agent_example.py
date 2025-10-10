#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UTCP Agent Integration Example

This example shows how to integrate UtcpManualToolset with a minion agent.
"""

import asyncio
import logging
from pathlib import Path

from minion.agents import CodeAgent
from minion.tools import create_utcp_toolset
from minion.agents.base_agent import BaseAgent
from minion.providers.openai_provider import OpenAIProvider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function showing UTCP integration with agent"""
    
    try:
        # Create UTCP toolset (async - automatically sets up)
        print("Creating and setting up UTCP toolset...")
        utcp_toolset = await create_utcp_toolset(
            config=str(Path(__file__).parent / "providers.json"),
            name="agent_utcp_toolset"
        )
        
        if not utcp_toolset.is_healthy:
            print(f"❌ UTCP toolset setup failed: {utcp_toolset.setup_error}")
            return
            
        print(f"✅ UTCP toolset ready with {len(utcp_toolset.tools)} tools")
        
        # Get tools for agent
        utcp_tools = utcp_toolset.get_tools()
        
        # Create agent with UTCP tools
        agent = await CodeAgent.create(
            llm="gpt-4o",
            tools=utcp_tools,  # Pass UTCP tools directly
            name="UTCP Agent"
        )
        
        # Example conversation
        print("\n🤖 Starting conversation with UTCP-enabled agent...")
        
        # Test with a calculation if calculator tools are available
        if True:
            response = await agent.run_async("Can you add 15 and 27 for me?")
            print(f"Agent response: {response}")
        else:
            print("No calculator tools found, testing with general query...")
            response = await agent.run("What tools do you have available?")
            print(f"Agent response: {response}")
            
    except Exception as e:
        print(f"❌ Error during UTCP agent example: {e}")
        logger.exception("Full error details:")
        
    finally:
        # Clean up
        if 'utcp_toolset' in locals():
            print("Cleaning up UTCP toolset...")
            await utcp_toolset.close()


if __name__ == "__main__":
    asyncio.run(main())