[![Documentation Status](https://img.shields.io/badge/documentation-brightgreen)](https://github.com/femto/minion)
[![Install](https://img.shields.io/badge/get_started-blue)](https://github.com/femto/minion#get-started)
[![Discord](https://dcbadge.limes.pink/api/server/HUC6xEK9aT?style=flat)](https://discord.gg/HUC6xEK9aT)
[![Twitter Follow](https://img.shields.io/twitter/follow/femtowin?style=social)](https://x.com/femtowin)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/femto/minion)

# Minion

Minion is Agent's Brain. Minion is designed to execute any type of queries, offering a variety of features that demonstrate its flexibility and intelligence.

<img src="assets/minion1.webp" alt="Minion" width="200" align="right">

## Installation

```bash
git clone https://github.com/femto/minion.git && cd minion && pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml
cp config/.env.example config/.env
```

Edit `config/config.yaml`:

```yaml
models:
  "default":
    api_type: "openai"
    base_url: "${DEFAULT_BASE_URL}"
    api_key: "${DEFAULT_API_KEY}"
    model: "gpt-4.1"
    temperature: 0
```

See [Configuration](#configuration) for more details on configuration options.

## Quick Start

### Using CodeAgent (Recommended)

```python
from minion.main.agent import CodeAgent

# Create agent
agent = await CodeAgent.create(
    name="Minion Code Assistant",
    llm="your-model",
    tools=all_tools,  # optional
)

# Run task
async for event in await agent.run_async("your task here"):
    print(event)
```

See [examples/mcp/mcp_agent_example.py](examples/mcp/mcp_agent_example.py) for a complete example with MCP tools.

### Using Brain

```python
from minion.main.brain import Brain

brain = Brain()
obs, score, *_ = await brain.step(query="what's the solution 234*568")
print(obs)
```

See [Brain Usage Guide](docs/brain_usage.md) for more examples.

## Quick Demo

[![Minion Quick Demo](https://img.youtube.com/vi/-LW7TCMUfLs/0.jpg)](https://youtu.be/-LW7TCMUfLs?si=-pL9GhNfbjFtNagJ)

*Click to watch the demo video on YouTube.*

## Working Principle

<img src="assets/sci.png" alt="Minion" align="right">

The flowchart demonstrates the complete process from query to final result:
1. First receives the user query (Query)
2. System generates a solution (Solution)
3. Performs solution verification (Check)
4. If unsatisfactory, makes improvements (Improve) and returns to generate new solutions
5. If satisfactory, outputs the final result (Final Result)

## Documentation

- [CodeAgent Documentation](docs/merged_code_agent.md) - Powerful Python code execution agent
- [Brain Usage Guide](docs/brain_usage.md) - Using brain.step() for various tasks
- [Skills Guide](docs/skills.md) - Extend agent capabilities with modular skills
- [Benchmarks](docs/benchmarks.md) - Performance results on GSM8K, Game of 24, AIME, Humaneval
- [Route Parameter Guide](docs/agent_route_parameter_guide.md) - Route options for different reasoning strategies
- [Gradio UI Guide](docs/gradio_ui_guide.md) - Web interface for Minion

## Configuration

### Configuration File Locations

1. **Project Config**: `MINION_ROOT/config/config.yaml` - Default project configuration
2. **User Config**: `~/.minion/config.yaml` - User-specific overrides

### Configuration Priority

When both configuration files exist:
- **Project Config** takes precedence over **User Config**

This allows you to:
- Keep sensitive data (API keys) in your user config
- Share project defaults through the project config

### Environment Variables

**Variable Substitution**: Use `${VAR_NAME}` syntax to reference environment variables directly in config values:

```yaml
models:
  "default":
    api_key: "${OPENAI_API_KEY}"
    base_url: "${OPENAI_BASE_URL}"
    api_type: "openai"
    model: "gpt-4.1"
    temperature: 0.3
```

**Loading .env Files**: Use `env_file` to load environment variables from `.env` files (follows Docker `.env` file format):

```yaml
env_file:
  - .env
  - .env.local
```

Variables defined in these files will be available for `${VAR_NAME}` substitution throughout the configuration.

### MINION_ROOT Detection

`MINION_ROOT` is determined automatically:
1. Checks `MINION_ROOT` environment variable (if set)
2. Auto-detects by finding `.git`, `.project_root`, or `.gitignore` in parent directories
3. Falls back to current working directory

Check the startup log:
```
INFO | minion.const:get_minion_root:44 - MINION_ROOT set to: <some_path>
```

> **Warning**: Be cautious - LLM can generate potentially harmful code.

## Community and Support

[![Discord](https://dcbadge.limes.pink/api/server/HUC6xEK9aT?style=flat)](https://discord.gg/HUC6xEK9aT)

[![Twitter Follow](https://img.shields.io/twitter/follow/femtowin?style=social)](https://x.com/femtowin)

WeChat Group (minion-agent discussion):

<img src="docs/images/wechat.png" alt="WeChat Group" width="300">
