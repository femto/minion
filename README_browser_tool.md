# Browser Tool for Minion Framework

This module provides a class-based browser automation tool for the Minion framework with optional dependency on the `browser-use` package.

## Features

- **Class-based implementation**: Clean API through the `BrowserTool` class
- **Optional dependency**: Graceful handling when `browser-use` is not available
- **Process isolation**: Browser runs in a separate process for stability
- **Comprehensive API**: Complete set of browser automation functions
- **Async compatibility**: Works with async/await code patterns
- **Error handling**: Robust error reporting and resource management
- **Agent integration**: Seamless integration with CodeAgent

## Installation

```bash
# Install the base package
pip install -e .

# Install with browser-use dependency
pip install -e '.[browser]'
```

## Basic Usage

```python
from minion.tools import BrowserTool, HAS_BROWSER_TOOL

# Check if browser_use is available
if HAS_BROWSER_TOOL:
    # Create browser instance
    browser = BrowserTool(headless=False)
    
    # Navigate to a website
    result = browser.navigate("https://www.example.com")
    print(f"Navigation result: {result['success']} - {result['message']}")
    
    # Get page content
    html_result = browser.get_html()
    if html_result['success']:
        html_content = html_result['data']['html']
        print(f"HTML content length: {len(html_content)}")
    
    # Always clean up when done
    browser.cleanup()
else:
    print("browser_use package is not available")
```

## Available Methods

The `BrowserTool` class provides the following methods:

- `navigate(url)`: Navigate to a URL
- `click(index)`: Click an element by index
- `input_text(index, text)`: Input text into an element
- `screenshot()`: Capture a screenshot
- `get_html()`: Get page HTML content
- `get_text()`: Get text content of the page
- `read_links()`: Get all links on the page
- `execute_js(script)`: Execute JavaScript code
- `scroll(scroll_amount)`: Scroll the page
- `switch_tab(tab_id)`: Switch to a specific tab
- `new_tab(url)`: Open a new tab
- `close_tab()`: Close the current tab
- `refresh()`: Refresh the current page
- `get_current_state()`: Get the current state of the browser
- `cleanup()`: Clean up browser resources

## Checking Availability

You can check if the `browser-use` package is available:

```python
from minion.tools import BrowserTool, HAS_BROWSER_TOOL

# Check at module level
if HAS_BROWSER_TOOL:
    print("BrowserTool is available at module level")

# Check at runtime
browser = BrowserTool()
if browser.is_browser_use_available():
    print("browser_use package is installed and available")
else:
    print("browser_use package is not installed")
```

## Integration with Code Agent

The BrowserTool can be easily integrated with CodeAgent:

```python
from minion.agents.code_agent import CodeAgent
from minion.tools import BrowserTool

# Initialize browser and agent
browser = BrowserTool(headless=False)
agent = CodeAgent(name="BrowserAgent", system_prompt="You help browse websites")

# Register browser tool methods with the agent
agent.register_tool("navigate", browser.navigate, "Navigate to a URL")
agent.register_tool("get_html", browser.get_html, "Get page HTML")
agent.register_tool("read_links", browser.read_links, "Get all links")

# Run the agent with browser capabilities
response = await agent.run("Visit example.com and tell me what links are available")
```

## Examples

See the provided example files in `examples/browser_tool/`:

- `browser_tool_example.py`: Basic usage example
- `browser_tool_multistep_async_example.py`: Advanced multistep async example
- `model_price_comparison.py`: Standard browser tool for price comparison
- `model_price_comparison_code_agent.py`: CodeAgent integration example

## Implementation Details

- The BrowserTool class is a wrapper around the browser_use functionality
- Browser operations run in a separate process for stability
- All operations return a standardized result format with success/error status
- Resources are properly cleaned up when the tool is no longer needed