# CodeAgent with State Tracking

## Overview

The `CodeAgent` class now includes all functionality previously separated into `StateCodeAgent`, allowing for optional state tracking and conversation management. This consolidation simplifies the codebase and provides a more flexible agent implementation.

## Key Features

- **Optional State Tracking**: Enable or disable state tracking with the `enable_state_tracking` parameter
- **Conversation History**: When state tracking is enabled, maintains conversation history
- **Persistent State**: Stores variables and learned patterns across interactions
- **Reset Capability**: Can reset state while preserving learned patterns
- **Context Enhancement**: Automatically enhances inputs with conversation context

## Usage

### Basic Usage (No State Tracking)

```python
from minion.agents.code_agent import CodeAgent

# Create a CodeAgent without state tracking (default behavior)
agent = CodeAgent()
await agent.setup()

# Run a task
result = await agent.solve_problem("Calculate 2 + 2")
```

### With State Tracking Enabled

```python
from minion.agents.code_agent import CodeAgent

# Create a CodeAgent with state tracking enabled
agent = CodeAgent(enable_state_tracking=True)
await agent.setup()

# First query
result1 = await agent.solve_problem("What is the capital of France?")

# Second query - will have context from the first interaction
result2 = await agent.solve_problem("What is its population?")

# Reset state if needed
agent.reset_state()

# Get conversation statistics
stats = agent.get_statistics()
```

### State Management Methods

When `enable_state_tracking=True`, the following methods are available:

- `reset_state()`: Clears conversation history while preserving learned patterns
- `clear_history()`: Clears only conversation history
- `get_conversation_history()`: Returns the full conversation history
- `get_recent_history(limit=n)`: Returns the n most recent conversation entries
- `get_state()`: Returns the current state dictionary
- `load_state(state_dict)`: Loads a previously saved state
- `get_statistics()`: Returns usage statistics

## Migration from StateCodeAgent

`StateCodeAgent` is now deprecated and will be removed in a future version. To migrate existing code:

```python
# Before
from minion.agents.state_code_agent import StateCodeAgent
agent = StateCodeAgent()

# After
from minion.agents.code_agent import CodeAgent
agent = CodeAgent(enable_state_tracking=True)
```

All functionality from `StateCodeAgent` is now available in `CodeAgent` when `enable_state_tracking` is set to `True`.