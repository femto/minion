#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Browser Toolset Demo

This example demonstrates how to use BrowserToolset with a Minion agent
to perform web automation tasks.
"""

import asyncio
from minion.tools.browser import BrowserToolset
from minion.agents.tool_calling_agent import ToolCallingAgent
from minion.main.input import Input


async def demo_toolset_basic():
    """Basic demo showing toolset usage."""
    print("=" * 60)
    print("Browser Toolset Basic Demo")
    print("=" * 60)

    # Check if browser-use is available
    if not BrowserToolset.is_available():
        print("Error: browser-use is not installed.")
        print("Please install it: pip install browser-use")
        return

    # Create toolset with visible browser
    async with BrowserToolset(headless=False) as toolset:
        print(f"Created toolset with {len(toolset.tools)} tools:")
        for tool in toolset.tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")

        # Get specific tool by name
        navigate_tool = toolset.get_tool("browser_navigate")
        if navigate_tool:
            print(f"\nUsing {navigate_tool.name} to navigate to example.com")
            result = await navigate_tool("https://example.com")
            print(f"Result: {result}")

        # Get page text
        get_text_tool = toolset.get_tool("browser_get_text")
        if get_text_tool:
            print(f"\nUsing {get_text_tool.name} to get page text")
            text = await get_text_tool()
            print(f"Page text (first 200 chars): {text[:200]}...")

        # Get page state
        get_state_tool = toolset.get_tool("browser_get_state")
        if get_state_tool:
            print(f"\nUsing {get_state_tool.name} to get page state")
            state = await get_state_tool()
            print(f"State: {state}")

    print("\nBrowser cleaned up automatically via context manager")


async def demo_with_agent():
    """Demo showing toolset usage with an agent."""
    print("=" * 60)
    print("Browser Toolset with Agent Demo")
    print("=" * 60)

    if not BrowserToolset.is_available():
        print("Error: browser-use is not installed.")
        return

    async with BrowserToolset(headless=False) as toolset:
        # Create agent with browser tools using async create
        agent = await ToolCallingAgent.create(
            name="BrowserAgent",
            tools=toolset.tools,
            llm="gpt-4o",  # Or any compatible model
            system_prompt="""You are a web browsing assistant.
            Use the browser tools to navigate websites and extract information.
            Always get the page state after navigating to confirm the URL.
            """
        )

        # Create task
        task = Input(
            query="Navigate to https://example.com and tell me what the page title is."
        )

        print(f"\nTask: {task.query}")
        print("\nRunning agent...")

        # Run agent (with streaming)
        async for event in (await agent.run_async(task, stream=True)):
            if hasattr(event, 'content') and event.content:
                print(event.content, end='', flush=True)

        print("\n\nAgent completed.")


async def demo_manual_workflow():
    """Demo showing a manual browser workflow."""
    print("=" * 60)
    print("Manual Browser Workflow Demo")
    print("=" * 60)

    if not BrowserToolset.is_available():
        print("Error: browser-use is not installed.")
        return

    toolset = BrowserToolset(headless=False)

    try:
        # Navigate to a search page
        navigate = toolset.get_tool("browser_navigate")
        get_text = toolset.get_tool("browser_get_text")
        get_links = toolset.get_tool("browser_read_links")
        scroll = toolset.get_tool("browser_scroll")

        # Step 1: Navigate
        print("\n1. Navigating to example.com...")
        result = await navigate("https://example.com")
        print(f"   {result}")

        # Step 2: Get text
        print("\n2. Getting page text...")
        text = await get_text()
        print(f"   Text length: {len(text)} chars")

        # Step 3: Get links
        print("\n3. Getting links...")
        links = await get_links()
        print(f"   Found {links.get('count', 0)} links")

        # Step 4: Scroll
        print("\n4. Scrolling down...")
        scroll_result = await scroll(300)
        print(f"   {scroll_result}")

        print("\nWorkflow completed!")

    finally:
        # Clean up
        toolset.cleanup()
        print("Browser cleaned up.")


def main():
    """Main entry point."""
    import sys

    demos = {
        "basic": demo_toolset_basic,
        "agent": demo_with_agent,
        "workflow": demo_manual_workflow,
    }

    if len(sys.argv) > 1:
        demo_name = sys.argv[1]
        if demo_name in demos:
            asyncio.run(demos[demo_name]())
        else:
            print(f"Unknown demo: {demo_name}")
            print(f"Available demos: {', '.join(demos.keys())}")
    else:
        # Run basic demo by default
        #asyncio.run(demo_toolset_basic())
        asyncio.run(demo_with_agent())


if __name__ == "__main__":
    main()
