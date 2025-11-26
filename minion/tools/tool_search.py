#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tool Search Tool - Dynamic tool discovery for large tool libraries.

This module implements the Tool Search Tool pattern from Anthropic's "Advanced Tool Use" article:
https://www.anthropic.com/engineering/advanced-tool-use

Key features:
- Dynamic tool discovery instead of loading all tool definitions upfront
- Multiple search strategies: regex, BM25, keyword
- Deferred tool loading to reduce token consumption
- 85% token reduction compared to loading all tools upfront
"""

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Optional BM25 dependency
try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    logger.debug("rank_bm25 not installed, BM25 search will fallback to keyword search")


@dataclass
class ToolInfo:
    """
    Tool metadata for search indexing.

    Stores lightweight tool information for search without loading full tool definitions.
    This is the key to token savings - we only store metadata, not full schemas.
    """
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    tool_instance: Optional[BaseTool] = None
    defer_loading: bool = True
    category: str = ""  # Optional category for filtering

    def to_summary(self, max_desc_length: int = 200) -> Dict[str, Any]:
        """
        Return summary for search results (not full definition).

        This is what gets returned to the LLM - a compact representation
        that's enough to decide whether to load the full tool.
        """
        return {
            'name': self.name,
            'description': self.description[:max_desc_length] if len(self.description) > max_desc_length else self.description,
            'parameters': list(self.parameters.keys()) if self.parameters else [],
            'category': self.category
        }

    @classmethod
    def from_tool(cls, tool: BaseTool, defer_loading: bool = True, category: str = "") -> 'ToolInfo':
        """Create ToolInfo from a BaseTool instance.

        Note: Even with defer_loading=True, we store the tool instance
        so it can be loaded later. The 'defer_loading' flag indicates
        whether the tool should be immediately available to the agent
        or only after explicit loading via LoadToolTool.
        """
        parameters = {}
        if hasattr(tool, 'inputs') and tool.inputs:
            parameters = tool.inputs
        elif hasattr(tool, 'parameters') and tool.parameters:
            parameters = tool.parameters.get('properties', {})

        return cls(
            name=tool.name,
            description=tool.description,
            parameters=parameters,
            tool_instance=tool,  # Always store instance for later loading
            defer_loading=defer_loading,
            category=category
        )


class ToolSearchStrategy(ABC):
    """Base class for tool search strategies."""

    @abstractmethod
    def search(self, query: str, tools: Dict[str, ToolInfo], top_k: int = 5) -> List[ToolInfo]:
        """
        Search tools by query.

        Args:
            query: Search query string
            tools: Dictionary of tool name -> ToolInfo
            top_k: Maximum number of results to return

        Returns:
            List of matching ToolInfo objects
        """
        pass


class KeywordSearchStrategy(ToolSearchStrategy):
    """
    Simple keyword-based search strategy.

    Searches for tools where any keyword appears in the name or description.
    Fast and always available (no external dependencies).
    """

    def search(self, query: str, tools: Dict[str, ToolInfo], top_k: int = 5) -> List[ToolInfo]:
        keywords = query.lower().split()
        if not keywords:
            return []

        results = []
        for tool in tools.values():
            name_lower = tool.name.lower()
            desc_lower = tool.description.lower()

            # Count keyword matches for scoring
            score = 0
            for kw in keywords:
                if kw in name_lower:
                    score += 2  # Name matches are weighted higher
                if kw in desc_lower:
                    score += 1

            if score > 0:
                results.append((score, tool))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in results[:top_k]]


class RegexSearchStrategy(ToolSearchStrategy):
    """
    Regex-based search strategy.

    Searches for tools where the regex pattern matches name or description.
    Useful for precise pattern matching.
    """

    def search(self, query: str, tools: Dict[str, ToolInfo], top_k: int = 5) -> List[ToolInfo]:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{query}': {e}")
            # Fallback to literal search
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        results = []
        for tool in tools.values():
            name_match = pattern.search(tool.name)
            desc_match = pattern.search(tool.description)

            if name_match or desc_match:
                # Score: name matches are weighted higher
                score = (2 if name_match else 0) + (1 if desc_match else 0)
                results.append((score, tool))

        results.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in results[:top_k]]


class BM25SearchStrategy(ToolSearchStrategy):
    """
    BM25-based search strategy for relevance-ranked results.

    Uses the BM25 algorithm for better relevance scoring.
    Requires `rank_bm25` package: `pip install rank_bm25`

    If rank_bm25 is not installed, falls back to keyword search.
    """

    def __init__(self):
        self.bm25 = None
        self.tool_list: List[ToolInfo] = []
        self.indexed = False
        self._fallback = KeywordSearchStrategy()

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on non-alphanumeric."""
        return re.findall(r'\w+', text.lower())

    def index(self, tools: Dict[str, ToolInfo]) -> None:
        """Build BM25 index from tools."""
        if not HAS_BM25:
            logger.debug("BM25 not available, will use keyword fallback")
            return

        self.tool_list = list(tools.values())
        corpus = []
        for tool in self.tool_list:
            # Combine name and description for indexing
            text = f"{tool.name} {tool.description}"
            corpus.append(self._tokenize(text))

        if corpus:
            self.bm25 = BM25Okapi(corpus)
            self.indexed = True
            logger.debug(f"BM25 index built with {len(corpus)} tools")

    def search(self, query: str, tools: Dict[str, ToolInfo], top_k: int = 5) -> List[ToolInfo]:
        # Reindex if tools changed
        if not self.indexed or len(tools) != len(self.tool_list):
            self.index(tools)

        # Fallback if BM25 not available
        if not HAS_BM25 or self.bm25 is None:
            return self._fallback.search(query, tools, top_k)

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices
        scored_tools = list(zip(scores, self.tool_list))
        scored_tools.sort(key=lambda x: x[0], reverse=True)

        # Filter out zero-score results and return top_k
        results = [tool for score, tool in scored_tools if score > 0][:top_k]
        return results


class ToolRegistry:
    """
    Registry for managing tools with deferred loading support.

    This is the central component for the Tool Search Tool pattern:
    - Register tools without loading their full definitions
    - Search tools by various strategies
    - Load tools on-demand when actually needed
    """

    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {}
        self.loaded_tools: Dict[str, BaseTool] = {}
        self._tool_factories: Dict[str, callable] = {}

    def register(self, tool: Union[BaseTool, ToolInfo], defer_loading: bool = True, category: str = "") -> None:
        """
        Register a tool (deferred by default).

        Args:
            tool: BaseTool instance or ToolInfo
            defer_loading: If True, don't store the full tool instance
            category: Optional category for filtering
        """
        if isinstance(tool, ToolInfo):
            self.tools[tool.name] = tool
        else:
            tool_info = ToolInfo.from_tool(tool, defer_loading=defer_loading, category=category)
            if not defer_loading:
                tool_info.tool_instance = tool
                self.loaded_tools[tool.name] = tool
            self.tools[tool.name] = tool_info

    def register_factory(self, name: str, factory: callable, description: str,
                        parameters: Dict[str, Any] = None, category: str = "") -> None:
        """
        Register a tool factory for lazy instantiation.

        This allows registering tools that are expensive to instantiate
        until they're actually needed.

        Args:
            name: Tool name
            factory: Callable that returns a BaseTool instance
            description: Tool description for search
            parameters: Tool parameters schema
            category: Optional category for filtering
        """
        self._tool_factories[name] = factory
        tool_info = ToolInfo(
            name=name,
            description=description,
            parameters=parameters or {},
            defer_loading=True,
            category=category
        )
        self.tools[name] = tool_info

    def register_many(self, tools: List[BaseTool], defer_loading: bool = True, category: str = "") -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register(tool, defer_loading=defer_loading, category=category)

    def load_tool(self, name: str) -> Optional[BaseTool]:
        """
        Load a deferred tool into active use.

        Args:
            name: Tool name to load

        Returns:
            BaseTool instance or None if not found
        """
        if name in self.loaded_tools:
            return self.loaded_tools[name]

        if name not in self.tools:
            logger.warning(f"Tool '{name}' not found in registry")
            return None

        tool_info = self.tools[name]

        # Check if we have a stored instance
        if tool_info.tool_instance is not None:
            self.loaded_tools[name] = tool_info.tool_instance
            return tool_info.tool_instance

        # Check if we have a factory
        if name in self._tool_factories:
            tool = self._tool_factories[name]()
            self.loaded_tools[name] = tool
            tool_info.tool_instance = tool
            logger.info(f"Tool '{name}' loaded via factory")
            return tool

        logger.warning(f"Cannot load tool '{name}': no instance or factory available")
        return None

    def get_loaded_tools(self) -> List[BaseTool]:
        """Get all currently loaded tools."""
        return list(self.loaded_tools.values())

    def get_all_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        return list(self.tools.keys())

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        categories = set()
        for tool in self.tools.values():
            if tool.category:
                categories.add(tool.category)
        return sorted(list(categories))

    def get_tools_by_category(self, category: str) -> List[ToolInfo]:
        """Get all tools in a category."""
        return [tool for tool in self.tools.values() if tool.category == category]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'total_registered': len(self.tools),
            'total_loaded': len(self.loaded_tools),
            'categories': self.get_categories(),
            'deferred_count': sum(1 for t in self.tools.values() if t.defer_loading and t.tool_instance is None)
        }


class ToolSearchTool(BaseTool):
    """
    Tool for searching and discovering other tools dynamically.

    This implements the Tool Search Tool pattern from Anthropic's article:
    - Allows Claude to discover tools on-demand
    - Supports multiple search strategies: keyword, regex, BM25
    - Dramatically reduces token consumption (85% reduction)
    - Improves tool selection accuracy

    Example usage:
        registry = ToolRegistry()
        registry.register_many([tool1, tool2, ...], defer_loading=True)

        search_tool = ToolSearchTool(registry)
        results = search_tool.forward("github pull request")
    """

    name: str = "tool_search"
    description: str = """Search for available tools by query.

Use this tool to discover what tools are available before using them.
This helps find the right tool for your task without loading all tools upfront.

Args:
    query: Search query - keywords describing what you want to do (e.g., "create pull request", "send message")
    strategy: Search strategy to use:
        - 'keyword': Simple keyword matching (default, fastest)
        - 'regex': Regular expression matching (for precise patterns)
        - 'bm25': BM25 relevance scoring (best for natural language queries)
    top_k: Maximum number of results to return (default: 5)
    category: Optional category filter (e.g., "github", "slack")

Returns:
    List of matching tools with name, description, and parameters.
"""
    inputs: Dict[str, Dict[str, Any]] = {
        "query": {
            "type": "string",
            "description": "Search query - keywords or pattern to search for"
        },
        "strategy": {
            "type": "string",
            "description": "Search strategy: 'keyword', 'regex', or 'bm25'",
            "default": "keyword"
        },
        "top_k": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 5
        },
        "category": {
            "type": "string",
            "description": "Optional category filter",
            "default": ""
        }
    }
    output_type: str = "array"
    readonly: bool = True

    def __init__(self, registry: ToolRegistry = None):
        super().__init__()
        self.registry = registry or ToolRegistry()
        self.strategies: Dict[str, ToolSearchStrategy] = {
            'keyword': KeywordSearchStrategy(),
            'regex': RegexSearchStrategy(),
            'bm25': BM25SearchStrategy(),
        }

    def forward(self, query: str, strategy: str = 'keyword', top_k: int = 5, category: str = "") -> List[Dict]:
        """
        Search tools and return matching results.

        Args:
            query: Search query string
            strategy: Search strategy ('keyword', 'regex', 'bm25')
            top_k: Maximum results to return
            category: Optional category filter

        Returns:
            List of tool summaries (name, description, parameters)
        """
        # Get searcher
        searcher = self.strategies.get(strategy)
        if searcher is None:
            logger.warning(f"Unknown strategy '{strategy}', falling back to 'keyword'")
            searcher = self.strategies['keyword']

        # Get tools to search (optionally filtered by category)
        if category:
            tools_to_search = {
                t.name: t for t in self.registry.tools.values()
                if t.category == category
            }
        else:
            tools_to_search = self.registry.tools

        # Search
        results = searcher.search(query, tools_to_search, top_k)

        # Return summaries
        return [tool.to_summary() for tool in results]

    def list_categories(self) -> List[str]:
        """List all available categories."""
        return self.registry.get_categories()

    def get_stats(self) -> Dict[str, Any]:
        """Get search tool statistics."""
        stats = self.registry.get_stats()
        stats['bm25_available'] = HAS_BM25
        return stats


class LoadToolTool(BaseTool):
    """
    Tool for loading a discovered tool into active use.

    After using ToolSearchTool to find relevant tools, use this tool
    to actually load them so they become available for use in the agent's
    code execution environment.

    The loaded tool becomes callable in subsequent code blocks.
    """

    name: str = "load_tool"
    description: str = """Load a tool by name so it can be used in code.

After searching for tools with tool_search, use this to load
the tools you need. Once loaded, the tool becomes available as a
callable function in your code.

Args:
    tool_name: Name of the tool to load (e.g., "github.create_pull_request")

Returns:
    Confirmation with tool details. After loading, you can call the tool
    directly in code, e.g.: result = await github_create_pull_request(repo="owner/repo", ...)

Example workflow:
    1. Search: results = await tool_search(query="github pull request")
    2. Load: await load_tool(tool_name="github.create_pull_request")
    3. Use: result = await github_create_pull_request(repo="owner/repo", title="Fix bug", ...)
"""
    inputs: Dict[str, Dict[str, Any]] = {
        "tool_name": {
            "type": "string",
            "description": "Name of the tool to load"
        }
    }
    output_type: str = "object"
    readonly: bool = False  # This modifies agent state

    def __init__(self, registry: ToolRegistry, agent=None):
        super().__init__()
        self.registry = registry
        self.agent = agent  # Reference to agent for adding loaded tools
        self.needs_state = True  # We need access to agent state to add tools

    def forward(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Load a tool by name and add it to the agent's available tools."""
        tool = self.registry.load_tool(tool_name)

        if tool is None:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' not found or could not be loaded"
            }

        # Get agent from state if available (passed via needs_state mechanism)
        agent = kwargs.get('_agent') or self.agent
        state = kwargs.get('_state')

        # Try to get agent from state
        if agent is None and state is not None:
            agent = getattr(state, 'agent', None)

        # Add tool to agent if we have a reference
        tool_added_to_agent = False
        if agent is not None and hasattr(agent, 'add_tool'):
            try:
                agent.add_tool(tool)
                tool_added_to_agent = True
                logger.info(f"Tool '{tool_name}' added to agent")
            except Exception as e:
                logger.warning(f"Failed to add tool to agent: {e}")

        # Create a sanitized function name for code use
        func_name = tool_name.replace('.', '_').replace('-', '_')

        return {
            'success': True,
            'tool_name': tool.name,
            'function_name': func_name,
            'description': tool.description,
            'parameters': list(tool.inputs.keys()) if hasattr(tool, 'inputs') and tool.inputs else [],
            'added_to_agent': tool_added_to_agent,
            'message': f"Tool '{tool_name}' loaded successfully. Call it as: await {func_name}(...)"
        }
