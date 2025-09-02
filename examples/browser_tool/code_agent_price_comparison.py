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
from minion.tools.async_base_tool import AsyncBaseTool
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
class NavigateTool(AsyncBaseTool):
    """Tool for navigating to URLs."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "navigate"
        self.description = "Navigate to a URL"
        self.browser = browser
    
    async def forward(self, url):
        """Navigate to the specified URL."""
        try:
            # BrowserTool的navigate方法是同步的
            result = self.browser.navigate(url)
            return f"Navigated to {url}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"

class GetHtmlTool(AsyncBaseTool):
    """Tool for retrieving page HTML."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "get_html"
        self.description = "Get the HTML content of the current page"
        self.browser = browser
    
    async def forward(self, *args, **kwargs):
        """Get the HTML content of the current page."""
        # BrowserTool的get_html方法是同步的
        result = self.browser.get_html()
        # 从结果中提取HTML内容
        html = result.get("data", {}).get("html", "")
        return html[:20000] if len(html) > 20000 else html  # 截断太长的内容

class GetTextTool(AsyncBaseTool):
    """Tool for retrieving page text."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "get_text"
        self.description = "Get the text content of the current page"
        self.browser = browser
    
    async def forward(self, *args, **kwargs):
        """Get the text content of the current page."""
        try:
            # BrowserTool的get_text方法是同步的
            result = self.browser.get_text()
            # 从结果中提取text内容
            text = result.get("data", {}).get("text", "")
            return text[:15000] if len(text) > 15000 else text  # 截断太长的内容
        except Exception as e:
            return f"Error getting text: {str(e)}"

class ReadLinksTool(AsyncBaseTool):
    """Tool for extracting links from a page."""
    
    def __init__(self, browser):
        super().__init__()
        self.name = "read_links"
        self.description = "Get all links on the current page"
        self.browser = browser
    
    async def forward(self, *args, **kwargs):
        """Get all links on the current page."""
        # BrowserTool的read_links方法是同步的
        result = self.browser.read_links()
        # 从结果中提取links内容
        links = result.get("data", {}).get("links", [])
        return links

class GetPricingDataTool(AsyncBaseTool):
    """Tool that returns the fallback pricing data."""
    
    def __init__(self):
        super().__init__()
        self.name = "get_pricing_data"
        self.description = "Get fallback pricing data for GPT-4o and DeepSeek-Coder"
    
    async def forward(self, *args, **kwargs):
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
    browser = BrowserTool(headless=False)
    
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
        #agent.add_tool(pricing_tool)
        
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
        I need you to create a detailed price comparison between OpenAI's GPT-4o and DeepSeek-Coder models by actively searching for current pricing information online.
        
        Your task is to:
        
        1. **Use browser tools to search for current pricing:**
           - Navigate to OpenAI's pricing page (https://openai.com/pricing) to get GPT-4o pricing
           - Navigate to DeepSeek's website or documentation to find DeepSeek-Coder pricing
           - Extract the current token prices for both input and output tokens
           - Look for any recent pricing updates or announcements
        
        2. **If web scraping fails, use fallback data:**
           - Only use the get_pricing_data tool as a backup if you cannot find current pricing online
           - Clearly indicate when you're using fallback vs. current data
        
        3. **Perform detailed analysis:**
           - Basic price comparison (input and output token prices per 1K tokens)
           - Calculate costs for these usage scenarios:
             * Small: 1K input + 0.5K output tokens
             * Medium: 5K input + 2K output tokens  
             * Large: 20K input + 5K output tokens
             * Enterprise: 100K input + 20K output tokens
           - Calculate percentage savings when using the cheaper model
           - Monthly cost estimates for different usage levels
        
        4. **Provide actionable recommendations:**
           - Best model for different use cases (coding, general tasks, cost-sensitive projects)
           - Break-even analysis for switching between models
           - Considerations beyond just price (quality, features, context window)
        
        **Important:** Prioritize using browser tools to get the most current pricing information. Navigate to official pricing pages, extract text content, and parse the pricing details before falling back to static data.
        
        Format your response as a comprehensive comparison with clear sections and show your web scraping process.
        """
        
        # Create system prompt
        system_prompt = """
        You are an AI pricing analyst that helps developers compare costs between different 
        LLM models. You have access to browser tools for web scraping and pricing data tools.
        
        **Your primary approach should be:**
        1. **Always try browser tools first** - Navigate to official pricing pages and extract current data
        2. Use navigate tool to go to pricing pages
        3. Use get_text or get_html tools to extract pricing information
        4. Parse the extracted content to find token prices
        5. Only use fallback pricing data if web scraping completely fails
        
        **When analyzing pricing:**
        1. Show your web scraping process and what you found
        2. Display calculations step-by-step with clear math
        3. Compare models objectively with current market data
        4. Provide practical recommendations for different developer scenarios
        5. Format output with clear sections and readable structure
        6. Indicate data sources and freshness (web-scraped vs fallback)
        
        **Web scraping strategy:**
        - Start with OpenAI pricing page: https://openai.com/pricing
        - Look for DeepSeek pricing on their official site or documentation
        - Extract specific token pricing (per 1K tokens for input/output)
        - Note any special pricing tiers or volume discounts
        """
        
        # Create the input with additional context about where to find pricing
        additional_context = """
        
        **Suggested URLs to check for current pricing:**
        - OpenAI GPT-4o: https://openai.com/pricing
        - DeepSeek: https://www.deepseek.com/ or https://platform.deepseek.com/pricing
        - Alternative sources: GitHub repos, documentation sites, or API documentation
        
        **What to look for:**
        - Price per 1K input tokens
        - Price per 1K output tokens  
        - Any volume discounts or special pricing tiers
        - Context window limits
        - Model capabilities and features
        """
        
        full_prompt = task_prompt + additional_context
        
        # Create the input
        input_obj = Input(
            query=full_prompt,
        )
        
        # Run the agent with stream support
        print("Running price comparison analysis...")
        result = await agent.run_async(input_obj, state=state, max_steps=5, reset=True, stream=True)
        
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
