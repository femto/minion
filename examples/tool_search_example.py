#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tool Search Tool Example

This example demonstrates the Tool Search Tool pattern from Anthropic's "Advanced Tool Use" article:
https://www.anthropic.com/engineering/advanced-tool-use

Key benefits:
- 85% token reduction compared to loading all tools upfront
- Better tool selection accuracy (49% -> 74% for Opus 4)
- Dynamic tool discovery instead of loading all definitions at startup

The Tool Search Tool allows Claude to:
1. Search for relevant tools by keyword, regex, or BM25
2. Load only the tools it needs for the current task
3. Avoid consuming context with unused tool definitions
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.tools import (
    BaseTool,
    ToolRegistry,
    ToolSearchTool,
    LoadToolTool,
    HAS_BM25
)


# =============================================================================
# Simulated Large Tool Library
# =============================================================================
# In a real scenario, these would be actual tool implementations.
# Here we create mock tools to demonstrate the pattern.

class GitHubCreatePRTool(BaseTool):
    name = "github.create_pull_request"
    description = "Create a pull request on GitHub. Specify the repository, base branch, head branch, title, and body."
    inputs = {
        "repo": {"type": "string", "description": "Repository in format 'owner/repo'"},
        "title": {"type": "string", "description": "PR title"},
        "body": {"type": "string", "description": "PR description"},
        "base": {"type": "string", "description": "Base branch"},
        "head": {"type": "string", "description": "Head branch"}
    }
    output_type = "object"

    def forward(self, repo: str, title: str, body: str, base: str, head: str):
        return {"success": True, "pr_number": 123, "url": f"https://github.com/{repo}/pull/123"}


class GitHubListIssuesTool(BaseTool):
    name = "github.list_issues"
    description = "List issues in a GitHub repository. Filter by state, labels, and assignee."
    inputs = {
        "repo": {"type": "string", "description": "Repository in format 'owner/repo'"},
        "state": {"type": "string", "description": "Filter by state: open, closed, all"},
        "labels": {"type": "array", "description": "Filter by labels"}
    }
    output_type = "array"

    def forward(self, repo: str, state: str = "open", labels: list = None):
        return [{"number": 1, "title": "Bug fix needed", "state": state}]


class GitHubGetRepoTool(BaseTool):
    name = "github.get_repository"
    description = "Get information about a GitHub repository including stars, forks, and description."
    inputs = {"repo": {"type": "string", "description": "Repository in format 'owner/repo'"}}
    output_type = "object"

    def forward(self, repo: str):
        return {"name": repo, "stars": 1000, "forks": 100}


class SlackSendMessageTool(BaseTool):
    name = "slack.send_message"
    description = "Send a message to a Slack channel or user. Supports markdown formatting."
    inputs = {
        "channel": {"type": "string", "description": "Channel ID or name"},
        "text": {"type": "string", "description": "Message text"},
        "thread_ts": {"type": "string", "description": "Thread timestamp for replies"}
    }
    output_type = "object"

    def forward(self, channel: str, text: str, thread_ts: str = None):
        return {"success": True, "ts": "1234567890.123456"}


class SlackListChannelsTool(BaseTool):
    name = "slack.list_channels"
    description = "List all channels in the Slack workspace. Filter by type (public, private)."
    inputs = {"types": {"type": "string", "description": "Channel types: public_channel, private_channel"}}
    output_type = "array"

    def forward(self, types: str = "public_channel"):
        return [{"id": "C123", "name": "general"}, {"id": "C456", "name": "random"}]


class SlackGetUserTool(BaseTool):
    name = "slack.get_user"
    description = "Get information about a Slack user by their ID or email."
    inputs = {"user_id": {"type": "string", "description": "User ID or email"}}
    output_type = "object"

    def forward(self, user_id: str):
        return {"id": user_id, "name": "John Doe", "email": "john@example.com"}


class JiraCreateTicketTool(BaseTool):
    name = "jira.create_ticket"
    description = "Create a new Jira ticket. Specify project, issue type, summary, and description."
    inputs = {
        "project": {"type": "string", "description": "Project key"},
        "issue_type": {"type": "string", "description": "Issue type: Bug, Story, Task"},
        "summary": {"type": "string", "description": "Ticket summary"},
        "description": {"type": "string", "description": "Ticket description"}
    }
    output_type = "object"

    def forward(self, project: str, issue_type: str, summary: str, description: str):
        return {"key": f"{project}-123", "url": f"https://jira.example.com/browse/{project}-123"}


class JiraSearchTicketsTool(BaseTool):
    name = "jira.search_tickets"
    description = "Search for Jira tickets using JQL (Jira Query Language)."
    inputs = {"jql": {"type": "string", "description": "JQL query string"}}
    output_type = "array"

    def forward(self, jql: str):
        return [{"key": "PROJ-1", "summary": "Fix bug", "status": "Open"}]


class JiraUpdateTicketTool(BaseTool):
    name = "jira.update_ticket"
    description = "Update an existing Jira ticket. Change status, assignee, or add comments."
    inputs = {
        "ticket_key": {"type": "string", "description": "Ticket key (e.g., PROJ-123)"},
        "fields": {"type": "object", "description": "Fields to update"}
    }
    output_type = "object"

    def forward(self, ticket_key: str, fields: dict):
        return {"success": True, "key": ticket_key}


class GoogleDriveUploadTool(BaseTool):
    name = "gdrive.upload_file"
    description = "Upload a file to Google Drive. Specify the file path and destination folder."
    inputs = {
        "file_path": {"type": "string", "description": "Local file path"},
        "folder_id": {"type": "string", "description": "Destination folder ID"}
    }
    output_type = "object"

    def forward(self, file_path: str, folder_id: str = None):
        return {"file_id": "abc123", "url": "https://drive.google.com/file/d/abc123"}


class GoogleDriveSearchTool(BaseTool):
    name = "gdrive.search_files"
    description = "Search for files in Google Drive by name, type, or content."
    inputs = {"query": {"type": "string", "description": "Search query"}}
    output_type = "array"

    def forward(self, query: str):
        return [{"id": "abc123", "name": "document.pdf", "mimeType": "application/pdf"}]


class GoogleDriveShareTool(BaseTool):
    name = "gdrive.share_file"
    description = "Share a Google Drive file with users or make it public."
    inputs = {
        "file_id": {"type": "string", "description": "File ID"},
        "email": {"type": "string", "description": "Email to share with"},
        "role": {"type": "string", "description": "Permission role: reader, writer, commenter"}
    }
    output_type = "object"

    def forward(self, file_id: str, email: str, role: str = "reader"):
        return {"success": True, "permission_id": "perm123"}


class NotionCreatePageTool(BaseTool):
    name = "notion.create_page"
    description = "Create a new page in Notion. Specify the parent page or database."
    inputs = {
        "parent_id": {"type": "string", "description": "Parent page or database ID"},
        "title": {"type": "string", "description": "Page title"},
        "content": {"type": "string", "description": "Page content in markdown"}
    }
    output_type = "object"

    def forward(self, parent_id: str, title: str, content: str = ""):
        return {"page_id": "page123", "url": "https://notion.so/page123"}


class NotionSearchTool(BaseTool):
    name = "notion.search"
    description = "Search for pages and databases in Notion workspace."
    inputs = {"query": {"type": "string", "description": "Search query"}}
    output_type = "array"

    def forward(self, query: str):
        return [{"id": "page123", "title": "Meeting Notes", "type": "page"}]


class SentryGetIssuesTool(BaseTool):
    name = "sentry.get_issues"
    description = "Get recent issues from Sentry. Filter by project and status."
    inputs = {
        "project": {"type": "string", "description": "Project slug"},
        "status": {"type": "string", "description": "Issue status: unresolved, resolved, ignored"}
    }
    output_type = "array"

    def forward(self, project: str, status: str = "unresolved"):
        return [{"id": "123", "title": "TypeError", "count": 42}]


class GrafanaQueryTool(BaseTool):
    name = "grafana.query"
    description = "Execute a query against Grafana data sources."
    inputs = {
        "datasource": {"type": "string", "description": "Data source name"},
        "query": {"type": "string", "description": "Query string"}
    }
    output_type = "object"

    def forward(self, datasource: str, query: str):
        return {"data": [{"time": "2024-01-01", "value": 100}]}


# =============================================================================
# Example Functions
# =============================================================================

def create_tool_registry() -> ToolRegistry:
    """Create a registry with all simulated tools."""
    registry = ToolRegistry()

    # Register GitHub tools
    github_tools = [GitHubCreatePRTool(), GitHubListIssuesTool(), GitHubGetRepoTool()]
    registry.register_many(github_tools, defer_loading=True, category="github")

    # Register Slack tools
    slack_tools = [SlackSendMessageTool(), SlackListChannelsTool(), SlackGetUserTool()]
    registry.register_many(slack_tools, defer_loading=True, category="slack")

    # Register Jira tools
    jira_tools = [JiraCreateTicketTool(), JiraSearchTicketsTool(), JiraUpdateTicketTool()]
    registry.register_many(jira_tools, defer_loading=True, category="jira")

    # Register Google Drive tools
    gdrive_tools = [GoogleDriveUploadTool(), GoogleDriveSearchTool(), GoogleDriveShareTool()]
    registry.register_many(gdrive_tools, defer_loading=True, category="gdrive")

    # Register Notion tools
    notion_tools = [NotionCreatePageTool(), NotionSearchTool()]
    registry.register_many(notion_tools, defer_loading=True, category="notion")

    # Register monitoring tools
    monitoring_tools = [SentryGetIssuesTool(), GrafanaQueryTool()]
    registry.register_many(monitoring_tools, defer_loading=True, category="monitoring")

    return registry


def demo_keyword_search():
    """Demonstrate keyword search strategy."""
    print("\n" + "=" * 60)
    print("Demo 1: Keyword Search Strategy")
    print("=" * 60)

    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)

    print(f"\nRegistry stats: {search_tool.get_stats()}")

    # Search for pull request related tools
    print("\n--- Searching for 'pull request' ---")
    results = search_tool.forward("pull request", strategy="keyword")
    for r in results:
        print(f"  - {r['name']}: {r['description'][:60]}...")

    # Search for message sending tools
    print("\n--- Searching for 'send message' ---")
    results = search_tool.forward("send message", strategy="keyword")
    for r in results:
        print(f"  - {r['name']}: {r['description'][:60]}...")

    # Search for ticket/issue tools
    print("\n--- Searching for 'ticket issue' ---")
    results = search_tool.forward("ticket issue", strategy="keyword")
    for r in results:
        print(f"  - {r['name']}: {r['description'][:60]}...")


def demo_regex_search():
    """Demonstrate regex search strategy."""
    print("\n" + "=" * 60)
    print("Demo 2: Regex Search Strategy")
    print("=" * 60)

    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)

    # Search for all GitHub tools
    print("\n--- Searching with regex 'github\\.' ---")
    results = search_tool.forward(r"github\.", strategy="regex")
    for r in results:
        print(f"  - {r['name']}")

    # Search for all search/list tools
    print("\n--- Searching with regex 'search|list' ---")
    results = search_tool.forward(r"search|list", strategy="regex")
    for r in results:
        print(f"  - {r['name']}")


def demo_bm25_search():
    """Demonstrate BM25 search strategy."""
    print("\n" + "=" * 60)
    print("Demo 3: BM25 Search Strategy")
    print("=" * 60)

    if not HAS_BM25:
        print("\nNote: rank_bm25 not installed. BM25 will fallback to keyword search.")
        print("Install with: pip install rank_bm25")

    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)

    # Natural language query
    print("\n--- Searching for 'I want to create a new task in project management' ---")
    results = search_tool.forward("I want to create a new task in project management", strategy="bm25")
    for r in results:
        print(f"  - {r['name']}: {r['description'][:60]}...")

    # Another natural language query
    print("\n--- Searching for 'upload documents and share with team' ---")
    results = search_tool.forward("upload documents and share with team", strategy="bm25")
    for r in results:
        print(f"  - {r['name']}: {r['description'][:60]}...")


def demo_category_filter():
    """Demonstrate category filtering."""
    print("\n" + "=" * 60)
    print("Demo 4: Category Filtering")
    print("=" * 60)

    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)

    print(f"\nAvailable categories: {search_tool.list_categories()}")

    # Search within GitHub category only
    print("\n--- Searching 'create' in 'github' category ---")
    results = search_tool.forward("create", strategy="keyword", category="github")
    for r in results:
        print(f"  - {r['name']}")

    # Search within Slack category only
    print("\n--- Searching 'message' in 'slack' category ---")
    results = search_tool.forward("message", strategy="keyword", category="slack")
    for r in results:
        print(f"  - {r['name']}")


def demo_tool_loading():
    """Demonstrate dynamic tool loading."""
    print("\n" + "=" * 60)
    print("Demo 5: Dynamic Tool Loading")
    print("=" * 60)

    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)
    load_tool = LoadToolTool(registry)

    print(f"\nInitial state:")
    print(f"  - Total registered: {len(registry.tools)}")
    print(f"  - Total loaded: {len(registry.loaded_tools)}")

    # Search for a tool
    print("\n--- Searching for 'create pull request' ---")
    results = search_tool.forward("create pull request")
    print(f"Found: {results[0]['name']}")

    # Load the tool
    print(f"\n--- Loading tool: {results[0]['name']} ---")
    result = load_tool.forward(results[0]['name'])
    print(f"Load result: {result}")

    print(f"\nAfter loading:")
    print(f"  - Total loaded: {len(registry.loaded_tools)}")
    print(f"  - Loaded tools: {list(registry.loaded_tools.keys())}")

    # Use the loaded tool
    print("\n--- Using the loaded tool ---")
    tool = registry.loaded_tools.get("github.create_pull_request")
    if tool:
        result = tool.forward(
            repo="owner/repo",
            title="Fix bug",
            body="This PR fixes the bug",
            base="main",
            head="fix-branch"
        )
        print(f"Tool result: {result}")


def demo_token_savings():
    """Demonstrate token savings calculation."""
    print("\n" + "=" * 60)
    print("Demo 6: Token Savings Estimation")
    print("=" * 60)

    registry = create_tool_registry()

    # Estimate tokens for full tool definitions
    total_chars = 0
    for tool_info in registry.tools.values():
        # Rough estimate: name + description + parameters
        chars = len(tool_info.name) + len(tool_info.description)
        chars += sum(len(str(p)) for p in tool_info.parameters.values())
        total_chars += chars

    # Rough token estimate (1 token ≈ 4 characters)
    full_tokens = total_chars // 4

    # Tool Search Tool tokens (just the search tool definition)
    search_tool_tokens = 500  # Approximate

    print(f"\nToken estimation:")
    print(f"  - Full tool library: ~{full_tokens:,} tokens ({len(registry.tools)} tools)")
    print(f"  - Tool Search Tool only: ~{search_tool_tokens} tokens")
    print(f"  - Estimated savings: ~{((full_tokens - search_tool_tokens) / full_tokens * 100):.1f}%")
    print(f"\nWith Tool Search Tool:")
    print(f"  - Only search tool loaded at startup")
    print(f"  - Other tools discovered and loaded on-demand")
    print(f"  - Context preserved for actual task execution")


async def demo_with_agent():
    """
    Demonstrate using Tool Search Tool with CodeAgent.

    This shows the complete flow:
    1. Agent starts with only tool_search (not all 16+ tools)
    2. Agent searches for relevant tools based on task
    3. Agent uses the discovered tools to complete the task

    This is the key pattern from Anthropic's article - the agent
    dynamically discovers what it needs instead of having everything
    loaded upfront.
    """
    print("\n" + "=" * 60)
    print("Demo 7: Integration with CodeAgent")
    print("=" * 60)

    try:
        from minion import config
        from minion.agents import CodeAgent
        from minion.main.brain import Brain
        from minion.providers import create_llm_provider
    except ImportError as e:
        print(f"\nSkipping agent demo: {e}")
        print("This demo requires the full minion package to be configured.")
        return

    # Create registry with all tools (but they won't be loaded into agent context)
    registry = create_tool_registry()
    search_tool = ToolSearchTool(registry)

    print(f"\nTool Registry Stats:")
    print(f"  - Total tools available: {len(registry.tools)}")
    print(f"  - Categories: {search_tool.list_categories()}")
    print(f"  - Initially loaded: {len(registry.loaded_tools)} (only search tool in agent)")

    # Setup LLM
    llm_config = config.models.get("gpt-4.1")
    if not llm_config:
        print("\nSkipping agent demo: No LLM configured")
        return

    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create agent with ONLY the search tool
    # This is the key insight: agent doesn't see all 16 tool definitions,
    # just the search tool (~500 tokens instead of ~5000+ tokens)
    agent = await CodeAgent.create(
        brain=brain,
        tools=[search_tool]
    )

    # Task that requires discovering and using tools
    task = """
    I need to find out what tools are available for working with GitHub.

    Steps:
    1. Use tool_search to find GitHub-related tools
    2. List what tools are available and their purposes
    3. Show which tool would be best for creating a pull request

    Use the tool_search function with query="github" to discover available tools.
    """

    print(f"\nTask: {task}")
    print("\n" + "-" * 40)
    print("Executing with Tool Search Tool pattern...")
    print("(Agent will discover tools dynamically)")
    print("-" * 40)

    try:
        result = await agent.run_async(task)
        print(f"\n{'=' * 40}")
        print("RESULT:")
        print("=" * 40)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def demo_agent_with_dynamic_loading():
    """
    Advanced demo: Agent that searches, loads, and uses tools dynamically.

    This demonstrates the FULL Tool Search Tool workflow where the agent:
    1. Searches for relevant tools
    2. Loads the tool into its execution environment
    3. Actually CALLS the loaded tool to complete the task

    This is the complete pattern from Anthropic's article.
    """
    print("\n" + "=" * 60)
    print("Demo 8: Full Workflow - Search, Load, and USE Tools")
    print("=" * 60)

    try:
        from minion import config
        from minion.agents import CodeAgent
        from minion.main.brain import Brain
        from minion.providers import create_llm_provider
    except ImportError as e:
        print(f"\nSkipping agent demo: {e}")
        return

    # Create registry with all tools
    registry = create_tool_registry()

    # Create search and load tools, passing registry
    search_tool = ToolSearchTool(registry)

    # Setup LLM
    llm_config = config.models.get("gpt-4.1")
    if not llm_config:
        print("\nSkipping agent demo: No LLM configured")
        return

    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create agent with search tool
    # LoadToolTool needs agent reference to add tools dynamically
    agent = await CodeAgent.create(
        brain=brain,
        tools=[search_tool]
    )

    # Create load_tool with agent reference so it can add tools
    load_tool = LoadToolTool(registry, agent=agent)
    agent.add_tool(load_tool)

    print(f"\nInitial agent tools: {[t.name for t in agent.tools]}")
    print(f"Total tools in registry: {len(registry.tools)}")

    # Task that requires the FULL workflow: search -> load -> use
    task = """
    Create a pull request on GitHub for repository "myorg/myrepo".

    
    """

    print(f"\nTask: {task}")
    print("\n" + "-" * 40)
    print("Executing FULL workflow: Search → Load → Use")
    print("-" * 40)

    try:
        result = await agent.run_async(task)
        print(f"\n{'=' * 40}")
        print("RESULT:")
        print("=" * 40)
        print(result)

        # Show what tools were loaded and added to agent
        print(f"\n{'=' * 40}")
        print("Tools loaded into registry:")
        for name in registry.loaded_tools:
            print(f"  - {name}")

        print(f"\nAgent's final tool list:")
        for tool in agent.tools:
            print(f"  - {tool.name}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all demos."""
    print("=" * 60)
    print("Tool Search Tool Examples")
    print("Based on: https://www.anthropic.com/engineering/advanced-tool-use")
    print("=" * 60)
    print("""
The Tool Search Tool pattern allows Claude to:
- Discover tools on-demand instead of loading all upfront
- Reduce token consumption by ~85%
- Improve tool selection accuracy

Supported search strategies:
- keyword: Fast, simple keyword matching
- regex: Pattern-based matching
- bm25: Relevance-ranked search (requires rank_bm25)
    """)

    # Run basic demos
    demo_keyword_search()
    demo_regex_search()
    demo_bm25_search()
    demo_category_filter()
    demo_tool_loading()
    demo_token_savings()

    print("\n" + "=" * 60)
    print("Basic demos completed!")
    print("=" * 60)
    print("\nTo run agent integration demos, use:")
    print("  python examples/tool_search_example.py --with-agent")


async def main_with_agent():
    """Run demos including agent integration."""
    # Run basic demos first
    main()

    # Then run agent demos
    print("\n" + "=" * 60)
    print("Running Agent Integration Demos...")
    print("=" * 60)

    # Demo 7: Basic search demo
    await demo_with_agent()

    # Demo 8: Full workflow - search, load, and USE the tool
    await demo_agent_with_dynamic_loading()


if __name__ == "__main__":
    import sys
    if "--with-agent" in sys.argv:
        asyncio.run(main_with_agent())
    else:
        main()
