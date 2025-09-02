# Gradio UI for Minion Agents

This guide explains how to use the Gradio web interface with Minion agents, particularly the CodeAgent.

## Overview

The Gradio UI provides a web-based chat interface for interacting with Minion agents. It's adapted from the smolagents library and customized to work with our agent architecture.

## Features

- 🌐 **Web-based Interface**: Easy-to-use chat interface accessible via web browser
- 🔄 **Real-time Streaming**: See agent responses as they're generated
- 📁 **File Upload Support**: Upload files for the agent to analyze (optional)
- 🧠 **Memory Management**: Option to reset or maintain conversation history
- 🛠️ **Tool Integration**: Visualize tool usage and code execution
- 📊 **Step-by-step Visualization**: See the agent's reasoning process

## Installation

First, install the gradio dependency:

```bash
# Install gradio as an optional dependency
pip install 'minion[gradio]'

# Or install gradio directly
pip install gradio
```

## Quick Start

### 1. Basic Usage

```python
import asyncio
from minion.agents.code_agent import CodeAgent
from minion.main.gradio_ui import GradioUI
from minion.main.brain import Brain
from minion.tools.default_tools import FinalAnswerTool

async def main():
    # Create a brain and agent
    brain = Brain()
    agent = CodeAgent(
        name="My Assistant",
        brain=brain,
        tools=[FinalAnswerTool()],
        max_steps=10
    )
    
    # Setup the agent
    await agent.setup()
    
    # Create and launch the UI
    ui = GradioUI(agent)
    ui.launch()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Using the Provided Launcher

The easiest way to get started is using the provided launcher:

```bash
python launch_gradio.py
```

This will:
- Set up a CodeAgent with default tools
- Launch the web interface on http://127.0.0.1:7860
- Provide a clean shutdown on Ctrl+C

### 3. Advanced Configuration

```python
from minion.agents.code_agent import CodeAgent
from minion.main.gradio_ui import GradioUI
from minion.main.brain import Brain
from minion.tools.default_tools import FinalAnswerTool

# Create agent with custom configuration
agent = CodeAgent(
    name="Advanced Assistant",
    brain=Brain(),
    tools=[FinalAnswerTool()],
    max_steps=15,
    enable_reflection=True,
    use_async_executor=True,
    enable_state_tracking=True  # Enable conversation history
)

# Create UI with file upload support
ui = GradioUI(
    agent=agent,
    file_upload_folder="uploads",  # Enable file uploads
    reset_agent_memory=False       # Keep conversation history
)

# Launch with custom settings
ui.launch(
    share=False,           # Set to True for public sharing
    server_port=8080,      # Custom port
    debug=True             # Enable debug mode
)
```

## UI Components

### Chat Interface

The main interface consists of:

- **Chat Area**: Displays the conversation with the agent
- **Input Box**: Where you type your messages
- **Submit Button**: Send your message to the agent
- **File Upload** (optional): Upload files for analysis

### Message Types

The UI displays different types of messages:

- **User Messages**: Your input queries
- **Agent Responses**: The agent's reasoning and responses
- **Tool Usage**: When the agent uses tools (🛠️)
- **Code Execution**: Python code blocks with syntax highlighting
- **Execution Logs**: Output from code execution (📝)
- **Errors**: Any errors that occur (💥)
- **Final Answers**: The agent's final response

### Step Visualization

Each agent step shows:
- Step number and type
- Reasoning/thought process
- Tool calls and arguments
- Execution results
- Timing and token usage information

## Configuration Options

### GradioUI Parameters

- `agent`: The BaseAgent instance to use
- `file_upload_folder`: Directory for uploaded files (None to disable)
- `reset_agent_memory`: Whether to reset memory between conversations

### Launch Parameters

- `share`: Create a public shareable link (default: False)
- `server_name`: Server hostname (default: "127.0.0.1")
- `server_port`: Server port (default: 7860)
- `debug`: Enable debug mode (default: True)

## Example Interactions

### Math Problem
```
User: Calculate the area of a circle with radius 5
Agent: I'll solve this step by step using Python code...
[Shows code execution and final answer]
```

### Data Analysis
```
User: Analyze this CSV data and find trends
Agent: I'll load and analyze the data...
[Shows data loading, analysis code, and visualizations]
```

### Code Generation
```
User: Write a function to sort a list of dictionaries by a key
Agent: I'll create a sorting function for you...
[Shows code implementation and testing]
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure gradio is installed
   pip install gradio
   ```

2. **Agent Setup Errors**
   ```python
   # Ensure agent is properly set up
   await agent.setup()
   ```

3. **Port Already in Use**
   ```python
   # Use a different port
   ui.launch(server_port=8080)
   ```

4. **Async Issues**
   - The UI handles async agents automatically
   - Use the provided launchers for best compatibility

### Performance Tips

- Use `enable_reflection=False` for faster responses during testing
- Limit `max_steps` for quicker iterations
- Use `reset_agent_memory=True` to prevent memory buildup

## Integration with Other Tools

The Gradio UI works with any BaseAgent subclass:

```python
# Works with different agent types
from minion.agents.code_agent import CodeAgent
from minion.agents.base_agent import BaseAgent

# Custom agent
class MyCustomAgent(BaseAgent):
    # Your custom implementation
    pass

# Use with Gradio UI
agent = MyCustomAgent()
ui = GradioUI(agent)
ui.launch()
```

## Development and Testing

### Running Tests

```bash
# Test basic functionality
python test_gradio_ui.py

# Test UI components
python test_ui_components.py
```

### Development Mode

For development, use debug mode and local hosting:

```python
ui.launch(
    debug=True,
    share=False,
    server_name="127.0.0.1"
)
```

## Security Considerations

- **File Uploads**: Only enable if needed, validate file types
- **Code Execution**: The agent can execute Python code - use in trusted environments
- **Public Sharing**: Be cautious with `share=True` in production
- **Network Access**: The agent may make network requests through tools

## Next Steps

- Explore different agent configurations
- Add custom tools to enhance capabilities
- Integrate with your existing workflows
- Customize the UI appearance and behavior

For more information, see the main Minion documentation and examples.