"""
Code Agent with Browser Tool: GPT-4o vs DeepSeek Price Comparison

This example demonstrates using StateCodeAgent with BrowserTool to:
1. Create browser-based tools for web scraping
2. Execute analysis on pricing data
3. Generate comparison and recommendations
"""

import asyncio
import json
import datetime
from typing import Dict, Any, List

from minion.agents.state_code_agent import StateCodeAgent
from minion.tools import BrowserTool, HAS_BROWSER_TOOL
from minion.tools.base_tool import BaseTool
from minion.main.input import Input
from minion.main.local_python_executor import LocalPythonExecutor

# Model prices as of July 2023 (fallback data)
FALLBACK_PRICES = {
    "gpt-4o": {
        "input": 0.01,
        "output": 0.03,
        "context_window": "128K tokens",
        "features": ["Multimodal", "Advanced reasoning", "Real-time knowledge"]
    },
    "deepseek-coder": {
        "input": 0.005,
        "output": 0.02,
        "context_window": "32K tokens",
        "features": ["Specialized for code", "Lower cost", "Strong programming"]
    }
}

# Create custom tool classes that extend BaseTool
class NavigateTool(BaseTool):
    """Tool for navigating to URLs."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "navigate"
        self.description = "Navigate to a URL"
        self.browser = browser
    
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

class GetPricingDataTool(BaseTool):
    """Tool that returns the fallback pricing data."""
    
    def __init__(self):
        super().__init__()
        self.name = "get_pricing_data"
        self.description = "Get fallback pricing data for GPT-4o and DeepSeek-Coder"
    
    def forward(self):
        """Return the fallback pricing data."""
        return {
            "data": FALLBACK_PRICES,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d")
        }

async def run_price_comparison():
    """Run the code agent to compare model pricing."""
    
    # Check if browser_use is available
    if not HAS_BROWSER_TOOL:
        print("Error: BrowserTool is not available.")
        print("Please install the browser-use package to run this example:")
        print("  pip install -e '.[browser]'")
        return
    
    # Initialize the browser tool
    browser = BrowserTool(headless=True)
    
    try:
        # Initialize the code agent with LocalPythonExecutor for Brain
        from minion.main.brain import Brain
        
        # Create Brain with LocalPythonExecutor
        brain = Brain(python_env=LocalPythonExecutor(additional_authorized_imports=["numpy", "pandas", "json"]))
        
        # Initialize state with history
        state = {
            "history": [],
            "step_count": 0
        }
        
        # Initialize the code agent
        agent = StateCodeAgent(
            name="PriceComparisonAgent",
            brain=brain,
            use_async_executor=True  # Use LocalPythonExecutor instead of AsyncPythonExecutor
        )
        
        # Create pricing data tool
        pricing_tool = GetPricingDataTool()
        # Register it directly - this is what was missing before
        agent.add_tool(pricing_tool)
        
        # Add browser tools to the agent
        agent.add_tool(NavigateTool(browser))
        agent.add_tool(GetHtmlTool(browser))
        agent.add_tool(GetTextTool(browser))
        agent.add_tool(ReadLinksTool(browser))
        agent.add_tool(GetPricingDataTool())
        
        # Set up the agent (required after adding tools)
        await agent.setup()
        
        # Create the task prompt
        task_prompt = """
        I need you to create a detailed price comparison between OpenAI's GPT-4o and DeepSeek-Coder models.
        
        First, get the fallback pricing data using the get_pricing_data tool.
        
        Then, analyze the pricing data and create a comparison with the following:
        
        1. Basic price comparison (input and output token prices)
        2. Calculate costs for these scenarios:
           - Small: 1K input + 0.5K output tokens
           - Medium: 5K input + 2K output tokens
           - Large: 20K input + 5K output tokens
        3. Calculate savings when using the cheaper model
        4. Provide recommendations for different use cases
        
        Format your response as a detailed comparison with clear sections.
        """
        
        # Create system prompt
        system_prompt = """
        You are an AI pricing analyst that helps developers compare costs between different 
        LLM models. You have access to browser tools and pricing data tools to gather and
        analyze pricing information.
        
        When analyzing pricing:
        1. Show your calculations clearly
        2. Compare models fairly and objectively
        3. Make practical recommendations based on use cases
        4. Format your output in a readable way with clear sections
        
        Output your analysis as JSON when requested.
        """
        
        # Create the input
        input_obj = Input(
            query=task_prompt,
        )
        
        # Run the agent
        print("Running price comparison analysis...")
        result = await agent.run_async(input_obj, state=state, max_steps=5, reset=True)
        
        # Display the result
        print("\n" + "=" * 60)
        print("MODEL PRICING COMPARISON RESULTS")
        print("=" * 60)
        print(result.answer)
        
    except Exception as e:
        print(f"Error running the code agent: {str(e)}")
    finally:
        # Clean up browser resources
        browser.cleanup()
        print("\nBrowser resources cleaned up")

if __name__ == "__main__":
    print("Code Agent with Browser Tool: Model Price Comparison")
    print("=" * 60)
    asyncio.run(run_price_comparison())
