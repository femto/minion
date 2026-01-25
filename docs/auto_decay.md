# Auto-decay: Context Management for Large Tool Responses (Experimental)

## Overview

During agent execution, tool responses can be very large (e.g., reading large files, web scraping, database query results). These large outputs quickly consume the LLM's context window, leading to performance degradation or context overflow.

**Auto-decay** automatically manages context by:
- Detecting large tool responses (default ≥100KB)
- Saving content to local files after a configurable TTL (time-to-live) in steps
- Replacing original content with a brief file reference
- Allowing agents to access full content via `file_read` tool when needed

## How It Works

### 1. Mark Phase

When a tool returns a large response, the system adds `_decay_meta` metadata to the message:

```python
message["_decay_meta"] = {
    "step_created": 5,        # Step number when created
    "content_size": 150000,   # Content size in bytes
    "decayable": True         # Marked as decayable
}
```

### 2. Check Phase

After each step, the system checks historical messages:
- Calculates the "age" of each message (current step - creation step)
- Triggers decay when age >= `decay_ttl_steps`

### 3. Decay Phase

When decay is triggered:
1. Save full content to a file (e.g., `~/.minion/decay-cache/decay-step5-a1b2c3d4.txt`)
2. Replace original content with:
   ```
   [Large output (146KB) saved to: /path/to/decay-step5-a1b2c3d4.txt]
   Use file_read to access full content if needed.
   ```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `decay_enabled` | bool | `True` | Enable/disable auto-decay |
| `decay_ttl_steps` | int | `3` | Number of steps to retain content |
| `decay_min_size` | int | `100_000` | Minimum bytes to trigger decay (100KB) |
| `decay_cache_dir` | str | `None` | Cache directory, None uses `~/.minion/decay-cache` |

## Usage Examples

### Basic Usage

```python
from minion.agents.code_agent import CodeAgent

# Uses default config (auto-decay enabled)
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o",
)
```

### Custom Configuration

```python
# Adjust TTL and minimum size
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o",
    decay_enabled=True,
    decay_ttl_steps=5,        # Decay after 5 steps
    decay_min_size=50_000,    # Trigger at 50KB
    decay_cache_dir="/tmp/my-cache",  # Custom cache directory
)
```

### Disable Auto-decay

```python
# Completely disable (not recommended unless context is large enough)
agent = await CodeAgent.create(
    name="My Agent",
    llm="gpt-4o",
    decay_enabled=False,
)
```

## Cache File Management

### File Location

Default cache directory: `~/.minion/decay-cache/`

File naming format: `decay-step{step_number}-{uuid}.txt`

Example:
```
~/.minion/decay-cache/
├── decay-step3-a1b2c3d4.txt
├── decay-step5-e5f6g7h8.txt
└── decay-step8-i9j0k1l2.txt
```

### Cleaning Cache

Cache files are not automatically cleaned. Manual cleanup:

```bash
# Clean all cache
rm -rf ~/.minion/decay-cache/*

# Clean files older than 7 days
find ~/.minion/decay-cache -name "decay-*.txt" -mtime +7 -delete
```

## Best Practices

### 1. TTL Settings

- **Short tasks (<10 steps)**: `decay_ttl_steps=2-3`
- **Long tasks (>20 steps)**: `decay_ttl_steps=5-7`
- **Tasks requiring frequent review**: Increase TTL or consider disabling

### 2. Size Threshold

- **Standard scenarios**: 100KB (default)
- **Large context window models (200K+)**: Can increase to 200-500KB
- **Small context window models (8K-32K)**: Consider lowering to 50KB

### 3. Combined with Auto-compact

Auto-decay and Auto-compact can work together for multi-level context management:

```python
agent = await CodeAgent.create(
    # Auto-decay: Large single messages -> files
    decay_enabled=True,
    decay_ttl_steps=3,
    decay_min_size=100_000,

    # Auto-compact: Overall history compression
    auto_compact_enabled=True,
    compact_threshold=0.8,
)
```

**Processing order**:
1. Decay first (save large outputs to files)
2. Then check if compact is needed (compress overall history)

## Technical Details

### Message Structure

**Before decay**:
```python
{
    "role": "user",
    "content": "<very long tool output...>",
    "_decay_meta": {
        "step_created": 5,
        "content_size": 150000,
        "decayable": True
    }
}
```

**After decay**:
```python
{
    "role": "user",
    "content": "[Large output (146KB) saved to: /path/to/file.txt]\nUse file_read to access full content if needed.",
    "_decayed": True,
    "_decay_file": "/path/to/file.txt",
    "_decay_original_size": 150000
}
```

### Log Output

Enable debug logging to see the decay process:

```
DEBUG - Marked message as decayable: 146KB at step 5
INFO - Decayed message from step 5: 146KB -> /home/user/.minion/decay-cache/decay-step5-a1b2c3d4.txt
INFO - Decayed 1 large outputs at step 8
```

## FAQ

### Q: Why is Auto-decay needed?

A: LLM context windows are limited. A single large file read (e.g., 1MB code file) can consume a significant number of tokens. As the conversation progresses, context fills up quickly, causing:
- Performance degradation (processing more tokens)
- Increased costs (billed per token)
- Context overflow errors

### Q: Can decayed content still be accessed?

A: Yes. The agent can use the `file_read` tool to read saved files. The message includes a file path hint.

### Q: Does it affect the agent's reasoning ability?

A: Usually not. Because:
- Only "old" large outputs are decayed
- Tool outputs from 3+ steps ago have typically been processed
- Agent can re-read files when needed

### Q: Can decay be triggered manually?

A: There is no public API to manually trigger decay. If needed, you can directly call the `_check_and_decay()` method.

## Related Documentation

- [CodeAgent Documentation](merged_code_agent.md) - Complete CodeAgent documentation
- [Streaming Architecture](STREAMING_ARCHITECTURE_UPDATE.md) - Streaming architecture
