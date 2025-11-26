# Advanced Tool Use Guide

This document describes the advanced tool use patterns implemented in Minion, based on Anthropic's [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) article.

## Overview

Traditional agent tool calling has two main problems:

1. **High token consumption**: Loading all tool definitions into context consumes massive tokens (50+ MCP tools can consume 55K+ tokens)
2. **Low tool selection accuracy**: As the number of tools increases, model accuracy in selecting the correct tool decreases

Minion implements two advanced patterns to solve these problems:

| Pattern | Token Savings | Accuracy Improvement | Implementation |
|---------|---------------|---------------------|----------------|
| **PTC (Programmatic Tool Calling)** | 37% | - | `CodeAgent` |
| **Tool Search Tool** | 85% | 49% → 74% | `ToolSearchTool` |

## PTC (Programmatic Tool Calling)

### Core Concept

PTC lets Claude write Python code to orchestrate tool calls, instead of using traditional JSON tool call format.

**Traditional approach**: Each tool call requires a complete JSON structure
```json
{
  "name": "get_weather",
  "arguments": {"city": "Beijing"}
}
```

**PTC approach**: Call directly in code
```python
weather = await get_weather(city="Beijing")
temperature = weather["temperature"]
if temperature > 30:
    await send_alert(message=f"High temperature: {temperature}°C")
```

### Advantages

- **More flexible**: Can use conditionals, loops, variables and other programming constructs
- **Token efficiency**: 37% reduction in token usage
- **Stronger reasoning**: Code itself embodies the thinking process

### Usage

```python
from minion import config
from minion.agents import CodeAgent
from minion.main.brain import Brain
from minion.providers import create_llm_provider
from minion.tools import BaseTool

# Define tools
class GetExpensesTool(BaseTool):
    name = "get_expenses"
    description = "Get expenses for a team member"
    inputs = {
        "employee_id": {"type": "string", "description": "Employee ID"},
        "category": {"type": "string", "description": "Expense category"}
    }
    output_type = "object"

    def forward(self, employee_id: str, category: str = None):
        # Implement expense retrieval logic
        return {"total": 1500.00, "items": [...]}

# Create Agent
llm_config = config.models.get("gpt-4.1")
llm = create_llm_provider(llm_config)
brain = Brain(llm=llm)

agent = await CodeAgent.create(
    brain=brain,
    tools=[GetExpensesTool()]
)

# Execute task
result = await agent.run_async("""
Check if all team members' travel expenses comply with the budget limit ($2000).
List members who exceeded the budget and their excess amounts.
""")
```

### Example File

See complete example: `examples/ptc_example.py`

```bash
python examples/ptc_example.py
```

## Tool Search Tool

### Core Concept

Tool Search Tool allows agents to dynamically discover and load tools, rather than loading all tool definitions into context upfront.

```
Traditional approach:
┌─────────────────────────────────────────────────┐
│  Agent Context                                   │
│  ┌─────────────────────────────────────────────┐│
│  │ Tool 1 definition (500 tokens)              ││
│  │ Tool 2 definition (500 tokens)              ││
│  │ ...                                          ││
│  │ Tool 50 definition (500 tokens)             ││
│  │ ─────────────────────────────────────────── ││
│  │ Total: ~25,000+ tokens                       ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘

Tool Search Tool approach:
┌─────────────────────────────────────────────────┐
│  Agent Context                                   │
│  ┌─────────────────────────────────────────────┐│
│  │ tool_search definition (~200 tokens)        ││
│  │ load_tool definition (~200 tokens)          ││
│  │ ─────────────────────────────────────────── ││
│  │ Total: ~400 tokens (85%+ savings)           ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  Tool Registry (not in context)                  │
│  ┌─────────────────────────────────────────────┐│
│  │ 50+ tool metadata, loaded on demand          ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

### Core Components

#### 1. ToolInfo - Tool Metadata

```python
from minion.tools import ToolInfo

# Store lightweight tool info for search
tool_info = ToolInfo(
    name="github.create_pull_request",
    description="Create a pull request on GitHub",
    parameters={"repo": {...}, "title": {...}},
    defer_loading=True,  # Deferred loading
    category="github"    # Category filter
)
```

#### 2. ToolRegistry - Tool Registry

```python
from minion.tools import ToolRegistry, BaseTool

registry = ToolRegistry()

# Register single tool (deferred loading)
registry.register(my_tool, defer_loading=True, category="utils")

# Batch register
registry.register_many([tool1, tool2, tool3], defer_loading=True, category="github")

# Use factory for lazy instantiation (for expensive-to-instantiate tools)
registry.register_factory(
    name="expensive_tool",
    factory=lambda: ExpensiveTool(),
    description="A tool that's expensive to instantiate",
    parameters={...}
)

# Load tool on demand
tool = registry.load_tool("github.create_pull_request")
```

#### 3. ToolSearchTool - Tool Search

```python
from minion.tools import ToolSearchTool

search_tool = ToolSearchTool(registry)

# Keyword search (default, fastest)
results = search_tool.forward("pull request", strategy="keyword")

# Regex search (precise pattern matching)
results = search_tool.forward(r"github\.", strategy="regex")

# BM25 search (natural language queries, most accurate)
results = search_tool.forward(
    "I want to create a new task in project management",
    strategy="bm25"
)

# Category filter
results = search_tool.forward("create", category="github")
```

#### 4. LoadToolTool - Tool Loading

```python
from minion.tools import LoadToolTool

load_tool = LoadToolTool(registry, agent=agent)

# Load tool into agent context
result = load_tool.forward("github.create_pull_request")
# Returns: {
#   'success': True,
#   'function_name': 'github_create_pull_request',  # Python-safe name
#   'message': "Tool loaded. Call as: await github_create_pull_request(...)"
# }
```

### Search Strategy Comparison

| Strategy | Use Case | Dependency | Performance |
|----------|----------|------------|-------------|
| `keyword` | Simple keyword matching | None | Fastest |
| `regex` | Precise pattern matching | None | Fast |
| `bm25` | Natural language queries | `rank_bm25` (optional) | Most accurate |

Install BM25 support:
```bash
pip install rank_bm25
```

### Complete Workflow Example

```python
from minion import config
from minion.agents import CodeAgent
from minion.main.brain import Brain
from minion.providers import create_llm_provider
from minion.tools import ToolRegistry, ToolSearchTool, LoadToolTool, BaseTool

# 1. Create tool library
class GitHubCreatePRTool(BaseTool):
    name = "github.create_pull_request"
    description = "Create a pull request on GitHub"
    inputs = {
        "repo": {"type": "string", "description": "Repository in format 'owner/repo'"},
        "title": {"type": "string", "description": "PR title"},
        "body": {"type": "string", "description": "PR description"},
        "base": {"type": "string", "description": "Base branch"},
        "head": {"type": "string", "description": "Head branch"}
    }

    def forward(self, repo, title, body, base, head):
        return {"success": True, "pr_number": 123, "url": f"https://github.com/{repo}/pull/123"}

# 2. Register tools to Registry (deferred loading)
registry = ToolRegistry()
registry.register(GitHubCreatePRTool(), defer_loading=True, category="github")
# Can register more tools...

# 3. Create search and load tools
search_tool = ToolSearchTool(registry)

# 4. Create Agent with only search tool
llm = create_llm_provider(config.models.get("gpt-4.1"))
brain = Brain(llm=llm)

agent = await CodeAgent.create(
    brain=brain,
    tools=[search_tool]  # Only search tool!
)

# 5. Add load_tool (needs agent reference)
load_tool = LoadToolTool(registry, agent=agent)
agent.add_tool(load_tool)

# 6. Agent executes task - dynamically discovers and uses tools
result = await agent.run_async("""
Create a pull request on GitHub for repository "myorg/myrepo".

Workflow:
1. Search for GitHub tools
2. Load the tool you need
3. Use it to create the PR
""")

# Agent will:
# 1. Call tool_search(query="github pull request") to discover tools
# 2. Call load_tool(tool_name="github.create_pull_request") to load tool
# 3. Call github_create_pull_request(...) to create PR
```

### Example File

See complete example: `examples/tool_search_example.py`

```bash
# Run basic demos (search strategies, category filtering, etc.)
python examples/tool_search_example.py

# Run complete demo with Agent integration
python examples/tool_search_example.py --with-agent
```

## Best Practices

### 1. Choose the Right Pattern

| Scenario | Recommended Pattern |
|----------|---------------------|
| Tool count < 10 | Standard tool calling |
| Tool count 10-30 | PTC (`CodeAgent`) |
| Tool count > 30 | Tool Search Tool |
| Need complex orchestration logic | PTC (`CodeAgent`) |
| Tools change dynamically | Tool Search Tool |

### 2. Tool Naming Convention

```python
# Recommended: Use dot-separated namespaces
"github.create_pull_request"
"slack.send_message"
"jira.create_ticket"

# Tool Search Tool automatically converts to Python-safe names
# github.create_pull_request -> github_create_pull_request
```

### 3. Organize Tools by Category

```python
# Use categories for filtering and management
registry.register_many(github_tools, category="github")
registry.register_many(slack_tools, category="slack")
registry.register_many(jira_tools, category="jira")

# Agent can search by category
results = search_tool.forward("create", category="github")
```

### 4. Optimize Tool Descriptions

```python
class WellDescribedTool(BaseTool):
    name = "github.create_pull_request"
    # Description should:
    # 1. Clearly explain functionality
    # 2. Include keywords for search
    # 3. Explain parameter requirements
    description = """Create a pull request on GitHub.

    Use this to submit code changes for review.
    Specify the repository, branches, title, and description.

    Keywords: PR, merge request, code review, submit changes
    """
```

### 5. Deferred Loading Strategy

```python
# Low instantiation cost tools - register directly
registry.register(SimpleTool(), defer_loading=True)

# High instantiation cost tools - use factory
registry.register_factory(
    name="database_tool",
    factory=lambda: DatabaseTool(connection_pool),  # Connection pool is expensive
    description="Execute database queries"
)
```

## API Reference

### ToolRegistry

| Method | Description |
|--------|-------------|
| `register(tool, defer_loading=True, category="")` | Register a single tool |
| `register_many(tools, defer_loading=True, category="")` | Batch register tools |
| `register_factory(name, factory, description, parameters, category)` | Register tool factory |
| `load_tool(name)` | Load tool instance |
| `get_loaded_tools()` | Get list of loaded tools |
| `get_all_tool_names()` | Get all registered tool names |
| `get_categories()` | Get all categories |
| `get_tools_by_category(category)` | Get tools by category |
| `get_stats()` | Get registry statistics |

### ToolSearchTool

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query |
| `strategy` | str | Search strategy: `keyword`, `regex`, `bm25` |
| `top_k` | int | Maximum number of results (default: 5) |
| `category` | str | Category filter (optional) |

### LoadToolTool

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_name` | str | Name of the tool to load |

## Related Files

- `minion/tools/tool_search.py` - Tool Search Tool core implementation
- `minion/agents/code_agent.py` - CodeAgent (PTC implementation)
- `examples/ptc_example.py` - PTC example
- `examples/tool_search_example.py` - Tool Search Tool example

## References

- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
