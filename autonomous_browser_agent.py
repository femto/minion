#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Autonomous Browser Agent Example

This example demonstrates how to create an autonomous agent with search and browse capabilities 
using Brain directly without StateCodeAgent. It includes:

1. Creating a Brain instance with proper configuration
2. Creating browser tools and search tools
3. Adding tools to Brain
4. Executing tasks through Brain.step()
5. Processing and displaying results
"""

import asyncio
import os
from typing import Dict, Any, List, Optional

from minion import config
from minion.main.brain import Brain
from minion.main.input import Input
from minion.main.local_python_env import LocalPythonEnv
from minion.providers import create_llm_provider
from minion.tools.base_tool import BaseTool
from minion.tools import BrowserTool, HAS_BROWSER_TOOL
from minion.tools.default_tools import FinalAnswerTool
from minion.tools.async_base_tool import async_tool, AsyncBaseTool
from minion.tools.mcp import (
    MCPToolset, 
    create_brave_search_toolset,
    create_filesystem_toolset,
)

# Constants for configuration
ENABLE_BROWSER = HAS_BROWSER_TOOL  # Only enable if browser-use is available
USE_BRAVE_SEARCH = False  # Set to True and provide API key to use Brave Search
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "your_api_key_here")

# Create a custom search tool as fallback when Brave Search is not available
class WebSearchTool(BaseTool):
    """Simple web search tool that returns mock results when real search is not available."""
    
    name = "web_search"
    description = "Search the web for information"
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query"
        },
        "num_results": {
            "type": "number",
            "description": "Number of results to return",
            "default": 5
        }
    }
    
    def forward(self, query: str, num_results: int = 5) -> dict:
        """Perform a web search."""
        # In a real implementation, this would connect to a search API
        # For this example, we return mock results
        return {
            "query": query,
            "results": [
                {
                    "title": f"Result 1 for '{query}'",
                    "url": f"https://example.com/result1?q={query}",
                    "snippet": f"This is a sample result for the query '{query}'. It contains relevant information."
                },
                {
                    "title": f"Result 2 for '{query}'",
                    "url": f"https://example.com/result2?q={query}",
                    "snippet": f"Another sample result with information about '{query}'."
                },
                {
                    "title": f"Result 3 for '{query}'",
                    "url": f"https://example.com/result3?q={query}",
                    "snippet": f"A third sample result about '{query}' with additional context."
                }
            ][:num_results],
            "total_results": num_results
        }

# Create async version of web search tool
@async_tool
async def async_web_search(query: str, num_results: int = 5) -> dict:
    """Async web search function."""
    # Simulate network delay
    await asyncio.sleep(0.5)
    
    # Return mock results (same as the sync version)
    return {
        "query": query,
        "results": [
            {
                "title": f"Result 1 for '{query}'",
                "url": f"https://example.com/result1?q={query}",
                "snippet": f"This is a sample result for the query '{query}'. It contains relevant information."
            },
            {
                "title": f"Result 2 for '{query}'",
                "url": f"https://example.com/result2?q={query}",
                "snippet": f"Another sample result with information about '{query}'."
            },
            {
                "title": f"Result 3 for '{query}'",
                "url": f"https://example.com/result3?q={query}",
                "snippet": f"A third sample result about '{query}' with additional context."
            }
        ][:num_results],
        "total_results": num_results
    }

# Custom browser tools using BaseTool interface for Brain
class NavigateTool(BaseTool):
    """Tool for navigating to URLs."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "navigate"
        self.description = "Navigate to a URL"
        self.browser = browser
        self.inputs = {
            "url": {
                "type": "string",
                "description": "The URL to navigate to"
            }
        }
    
    def forward(self, url):
        """Navigate to the specified URL."""
        return self.browser.navigate(url)

class GetHtmlTool(BaseTool):
    """Tool for retrieving page HTML."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "get_html"
        self.description = "Get the HTML content of the current page"
        self.browser = browser
    
    def forward(self):
        """Get the HTML content of the current page."""
        return self.browser.get_html()

class GetTextTool(BaseTool):
    """Tool for retrieving page text."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "get_text"
        self.description = "Get the text content of the current page"
        self.browser = browser
    
    def forward(self):
        """Get the text content of the current page."""
        return self.browser.get_text()

class ReadLinksTool(BaseTool):
    """Tool for extracting links from a page."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "read_links"
        self.description = "Get all links on the current page"
        self.browser = browser
    
    def forward(self):
        """Get all links on the current page."""
        return self.browser.read_links()

async def setup_autonomous_browser_agent():
    """Set up an autonomous browser agent with Brain."""
    print("Setting up autonomous browser agent...")
    
    # Initialize Brain with appropriate LLM
    llm = create_llm_provider(config.models.get("gpt-4o-mini"))
    
    # Use LocalPythonEnv for tool execution
    python_env = LocalPythonEnv(verbose=False, is_agent=True)
    
    # Initialize Brain
    brain = Brain(
        python_env=python_env,
        llm=llm,
        tools=[]  # We'll add tools after initialization
    )
    
    # Add the essential FinalAnswerTool
    final_answer_tool = FinalAnswerTool()
    brain.add_tool(final_answer_tool)
    
    # Add web search capabilities
    search_tools = []
    
    # Add Brave Search if enabled and API key is provided
    if USE_BRAVE_SEARCH and BRAVE_API_KEY != "your_api_key_here":
        print("Setting up Brave Search toolset...")
        try:
            brave_toolset = create_brave_search_toolset(BRAVE_API_KEY)
            search_tools.append(brave_toolset)
        except Exception as e:
            print(f"Failed to initialize Brave Search: {e}")
            print("Using fallback search tool instead.")
            search_tools.append(WebSearchTool())
            search_tools.append(async_web_search)
    else:
        print("Using fallback search tools...")
        search_tools.append(WebSearchTool())
        search_tools.append(async_web_search)
    
    # Add all search tools to Brain
    for tool in search_tools:
        brain.add_tool(tool)
    
    # Add browser tools if browser-use is available
    browser = None
    if ENABLE_BROWSER:
        print("Setting up browser tools...")
        try:
            browser = BrowserTool(headless=False)
            
            # Create browser tools
            browser_tools = [
                NavigateTool(browser),
                GetHtmlTool(browser),
                GetTextTool(browser),
                ReadLinksTool(browser)
            ]
            
            # Add browser tools to Brain
            for tool in browser_tools:
                brain.add_tool(tool)
                
        except Exception as e:
            print(f"Failed to initialize browser: {e}")
    
    return brain, browser

async def run_autonomous_task(brain, query):
    """Run an autonomous task using the Brain."""
    print(f"\nExecuting task: {query}")
    
    # Create system prompt for the agent
    system_prompt = """
    You are an autonomous web research assistant that can search for information and browse websites.
    When asked a question:
    1. First search for relevant information using search tools
    2. If needed, visit websites to gather more detailed information
    3. Compile your findings into a concise, informative answer
    
    Use appropriate tools based on the task:
    - web_search or async_web_search: To search for information
    - navigate: To visit a specific URL
    - get_text: To get the text content of a webpage
    - get_html: To get the HTML of a webpage when needed
    - read_links: To extract links from the current page
    - final_answer: To provide your final response
    
    Always provide accurate information and cite your sources.
    """
    
    # Execute the task using brain.step
    result = await brain.step(
        query=query,
        system_prompt=system_prompt,
        route="native",  # Use native routing for direct tool access
        check=False      # Disable checking to avoid StateCodeAgent
    )
    
    print("\nTask completed!")
    print("=" * 60)
    print("RESULTS:")
    print(result.answer)
    print("=" * 60)
    
    # Return the result for further processing if needed
    return result

async def main():
    """Main function to run the autonomous browser agent."""
    try:
        # Set up the autonomous browser agent
        brain, browser = await setup_autonomous_browser_agent()
        
        # List of sample tasks to run
        tasks = [
            "What are the latest developments in AI research?",
            "Find information about Python programming best practices.",
            "Research the history and key features of TypeScript."
        ]
        
        # Run each task
        for task in tasks:
            await run_autonomous_task(brain, task)
            
    except Exception as e:
        print(f"Error running autonomous browser agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up browser resources if applicable
        if browser:
            browser.cleanup()
            print("\nBrowser resources cleaned up")

if __name__ == "__main__":
    print("Autonomous Browser Agent Example")
    print("=" * 60)
    asyncio.run(main())