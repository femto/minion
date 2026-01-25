[![Documentation Status](https://img.shields.io/badge/documentation-brightgreen)](https://github.com/femto/minion)
[![Install](https://img.shields.io/badge/get_started-blue)](https://github.com/femto/minion#get-started)
[![Discord](https://dcbadge.limes.pink/api/server/HUC6xEK9aT?style=flat)](https://discord.gg/HUC6xEK9aT)
[![Twitter Follow](https://img.shields.io/twitter/follow/femtowin?style=social)](https://x.com/femtowin)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/femto/minion)

# Minion

[![Run in Smithery](https://smithery.ai/badge/skills/femto)](https://smithery.ai/skills?ns=femto&utm_source=github&utm_medium=badge)


Minion is Agent's Brain. Minion is designed to execute any type of queries, offering a variety of features that demonstrate its flexibility and intelligence.

<img src="assets/minion1.webp" alt="Minion" width="200" align="right">

## Installation

### Basic Installation

```bash
git clone https://github.com/femto/minion.git && cd minion
pip install -e .
cp config/config.yaml.example config/config.yaml
cp config/.env.example config/.env
```

### Docker Installation

```bash
git clone https://github.com/femto/minion.git && cd minion
cp config/config.yaml.example config/config.yaml

# Set your API key
export OPENAI_API_KEY=your-api-key

# Run with docker-compose
docker-compose run --rm minion

# Or run a specific example
docker-compose run --rm minion python examples/mcp/mcp_agent_example.py
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
from minion.agents.code_agent import CodeAgent

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
- [Auto-decay Guide](docs/auto_decay.md) - Automatic context management for large tool responses (Experimental) 

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
  "azure-gpt-4o":
    api_type: "azure"
    api_key: "${AZURE_OPENAI_API_KEY}"
    base_url: "${AZURE_OPENAI_ENDPOINT}"  # e.g., https://your-resource.openai.azure.com/
    api_version: "2024-06-01"
    model: "gpt-4o"  # deployment name
    temperature: 0
```

**Loading .env Files**: Use `env_file` to load environment variables from `.env` files (follows Docker `.env` file format):

```yaml
env_file:
  - .env        # loaded first
  - .env.local  # loaded second, can override values from .env
```

**Inline Environment Variables**: Define environment variables directly in config:

```yaml
environment:
  MY_VAR: "value"
  ANOTHER_VAR: "another_value"
```

Variables from all sources (system environment, `.env` files, inline `environment`) will be available for `${VAR_NAME}` substitution throughout the configuration.

### Supported API Types

| api_type | Description | Required Fields |
|----------|-------------|-----------------|
| `openai` | OpenAI API or compatible (Ollama, vLLM, LocalAI) | `api_key`, `base_url`, `model` |
| `azure` | Azure OpenAI Service | `api_key`, `base_url`, `api_version`, `model` |
| `azure_inference` | Azure AI Model Inference (DeepSeek, Phi) | `api_key`, `base_url`, `model` |
| `azure_anthropic` | Azure hosted Anthropic models | `api_key`, `base_url`, `model` |
| `bedrock` | AWS Bedrock (sync) | `access_key_id`, `secret_access_key`, `region`, `model` |
| `bedrock_async` | AWS Bedrock (async, better performance) | `access_key_id`, `secret_access_key`, `region`, `model` |

See [config/config.yaml.example](config/config.yaml.example) for complete examples of all supported providers.

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

## Related Projects

- [minion-agent](https://github.com/femto/minion-agent) Production agent system with multi-agent coordination, browser automation, and research capabilities

## Community and Support

[![Discord](https://dcbadge.limes.pink/api/server/HUC6xEK9aT?style=flat)](https://discord.gg/HUC6xEK9aT)

[![Twitter Follow](https://img.shields.io/twitter/follow/femtowin?style=social)](https://x.com/femtowin)

WeChat Group (minion-agent discussion):

<img src="docs/images/wechat.jpg" alt="WeChat Group" width="300">

## Optional Dependencies

The project uses optional dependency groups to avoid installing unnecessary packages. Install only what you need:

```bash
# Development tools (pytest, black, ruff)
pip install -e ".[dev]"

# Google ADK and LiteLLM support
pip install -e ".[google]"

# Browser automation (browser-use)
pip install -e ".[browser]"

# Gradio web UI
pip install -e ".[gradio]"

# UTCP support
pip install -e ".[utcp]"

# AWS Bedrock support
pip install -e ".[bedrock]"

# Anthropic Claude support
pip install -e ".[anthropic]"

# Web tools (httpx, beautifulsoup4, etc.)
pip install -e ".[web]"

# Install ALL optional dependencies
pip install -e ".[all]"

# You can also combine multiple groups:
pip install -e ".[dev,gradio,anthropic]"
```
