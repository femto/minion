# Auto-compact: Automatic Context Window Management

## Overview

As agent conversations grow longer, the context window fills up with historical messages. **Auto-compact** automatically manages context by summarizing older messages when the conversation approaches the context limit.

**Auto-compact** helps prevent:
- Context overflow errors
- Performance degradation from processing excessive tokens
- Increased API costs from large context windows

## How It Works

### 1. Monitor Phase

After each step, the system monitors context usage:
- Calculates current token count
- Compares against the model's context window limit
- Triggers compaction when usage exceeds threshold (default: 92%)

### 2. Compact Phase

When compaction is triggered:
1. **Preserve system messages** - Always kept intact
2. **Keep recent messages** - Last N messages (default: 10) stay unchanged
3. **Summarize old messages** - Use LLM to create a concise summary
4. **Replace history** - Old messages → summary message + recent messages

### Example Flow

**Before compaction** (120K tokens, 92% of 128K limit):
```
[System] You are a helpful assistant.
[User] Message 1
[Assistant] Response 1
... (100 more messages) ...
[User] Message 102
[Assistant] Response 102
```

**After compaction** (~30K tokens):
```
[System] You are a helpful assistant.
[System] [Conversation Summary] The user asked about... The assistant helped with...
[User] Message 93
[Assistant] Response 93
... (last 10 messages) ...
[User] Message 102
[Assistant] Response 102
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auto_compact_enabled` | bool | `True` | Enable/disable auto-compact |
| `auto_compact_threshold` | float | `0.92` | Trigger at X% of context window |
| `auto_compact_keep_recent` | int | `10` | Keep last N messages unchanged |
| `default_context_window` | int | `128000` | Default context size (128K tokens) |
| `compact_model` | str | `None` | Model for summarization, None uses agent's LLM |

## Usage Examples

### Basic Usage

```python
from minion.agents.code_agent import CodeAgent

# Uses default config (auto-compact enabled)
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o",
)
```

### Custom Configuration

```python
# More aggressive compaction for smaller context models
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o-mini",
    auto_compact_enabled=True,
    auto_compact_threshold=0.80,      # Trigger at 80%
    auto_compact_keep_recent=5,       # Keep only 5 recent messages
    compact_model="gpt-4o-mini",      # Use cheaper model for summarization
)
```

### Disable Auto-compact

```python
# Disable (for debugging or when using very large context models)
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o",
    auto_compact_enabled=False,
)
```

### Manual Compaction

```python
# Trigger compaction manually at any time
await agent.compact_now()

# Or with specific state
await agent.compact_now(state=my_state)
```

## Best Practices

### 1. Threshold Settings

- **Small context models (8K-32K)**: `auto_compact_threshold=0.70-0.80`
- **Medium context models (128K)**: `auto_compact_threshold=0.85-0.92` (default)
- **Large context models (200K+)**: `auto_compact_threshold=0.90-0.95`

### 2. Keep Recent Settings

- **Fast-paced conversations**: `auto_compact_keep_recent=5-8`
- **Standard tasks**: `auto_compact_keep_recent=10` (default)
- **Tasks requiring more context**: `auto_compact_keep_recent=15-20`

### 3. Compact Model Selection

Using a cheaper/faster model for summarization can reduce costs:

```python
agent = await CodeAgent.create(
    llm="gpt-4o",                    # Main reasoning model
    compact_model="gpt-4o-mini",     # Cheaper model for summaries
)
```

### 4. Combined with Auto-decay

Auto-compact and Auto-decay work together for multi-level context management:

```python
agent = await CodeAgent.create(
    # Auto-decay: Large single tool outputs -> files
    decay_enabled=True,
    decay_ttl_steps=3,
    decay_min_size=100_000,

    # Auto-compact: Overall history compression
    auto_compact_enabled=True,
    auto_compact_threshold=0.92,
)
```

**Processing order**:
1. Decay first (save large outputs to files)
2. Then check if compact is needed (compress overall history)

## Technical Details

### Token Calculation

Token count is calculated using the `tiktoken` library with model-specific encoding:
- Uses actual model encoding when available
- Falls back to `cl100k_base` encoding for unknown models

### Context Window Detection

The system automatically detects context window size:
1. Looks up model in known model database
2. Falls back to `default_context_window` if unknown

### Summary Message Format

The summary is inserted as a system message:
```python
{
    "role": "system",
    "content": "[Conversation Summary]\n...\n\n[End of Summary - Recent messages follow]"
}
```

## FAQ

### Q: Will important information be lost during compaction?

A: The LLM generates a comprehensive summary that captures key information, decisions, and context. Recent messages are always preserved unchanged.

### Q: Can I see when compaction happens?

A: Yes, check the logs:
```
INFO - Auto compact triggered: 118000 tokens >= 117760 (92% of 128000)
INFO - Manual compaction completed
```

### Q: Does compaction affect tool call history?

A: Tool calls are summarized along with other messages. The agent can still access original tool outputs if they were saved by auto-decay.

### Q: What if the summary LLM call fails?

A: The system gracefully falls back to keeping the original history unchanged.

## Related Documentation

- [Auto-decay Guide](auto_decay.md) - Managing large tool responses
- [CodeAgent Documentation](merged_code_agent.md) - Complete CodeAgent documentation
