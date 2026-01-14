#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool hooks system for minion framework.

Provides pre/post tool execution hooks for permission control, logging,
and integration with external systems (like ACP).

"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)
import fnmatch
import logging

from minion.tools import AsyncBaseTool

logger = logging.getLogger(__name__)


class PermissionDecision(Enum):
    """Decision from a permission hook."""
    ACCEPT = "accept"
    DENY = "deny"
    ASK = "ask"  # Request user permission


@dataclass
class PreToolUseResult:
    """Result from a PreToolUse hook."""
    decision: PermissionDecision
    reason: Optional[str] = None
    modified_input: Optional[Dict[str, Any]] = None  # Optional: modify tool input
    message: Optional[str] = None  # Message to display (if denied)


@dataclass
class PostToolUseResult:
    """Result from a PostToolUse hook."""
    additional_context: Optional[str] = None  # Additional context for the model
    continue_execution: bool = True  # Whether to continue execution
    stop_reason: Optional[str] = None  # Reason if stopping execution


@dataclass
class ToolCallInfo:
    """Information about a tool call."""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_use_id: str
    session_id: Optional[str] = None


# Type alias for hook functions
# (tool_name, tool_input, tool_use_id) -> PreToolUseResult
PreToolUseHook = Callable[
    [str, Dict[str, Any], str],
    Awaitable[PreToolUseResult]
]

# (tool_name, tool_input, tool_use_id, result, error) -> PostToolUseResult
PostToolUseHook = Callable[
    [str, Dict[str, Any], str, Any, Optional[Exception]],
    Awaitable[PostToolUseResult]
]


@dataclass
class HookMatcher:
    """
    Matcher for determining which tools trigger a pre-tool-use hook.

    Args:
        matcher: Tool name pattern(s) or callable predicate
            - "*" matches all tools
            - "bash" matches only bash tool
            - ["bash", "file_*"] matches bash and file_read, file_write, etc.
            - callable: (tool_name) -> bool
        hook: The hook function to call when matched
    """
    matcher: Union[str, List[str], Callable[[str], bool]]
    hook: PreToolUseHook

    def matches(self, tool_name: str) -> bool:
        """Check if this matcher matches the given tool name."""
        if callable(self.matcher):
            return self.matcher(tool_name)

        patterns = [self.matcher] if isinstance(self.matcher, str) else self.matcher

        for pattern in patterns:
            if pattern == "*":
                return True
            if fnmatch.fnmatch(tool_name, pattern):
                return True

        return False


@dataclass
class PostHookMatcher:
    """
    Matcher for post-tool-use hooks.

    Args:
        matcher: Tool name pattern(s) or callable predicate
        hook: The post-tool-use hook function to call when matched
    """
    matcher: Union[str, List[str], Callable[[str], bool]]
    hook: PostToolUseHook

    def matches(self, tool_name: str) -> bool:
        """Check if this matcher matches the given tool name."""
        if callable(self.matcher):
            return self.matcher(tool_name)

        patterns = [self.matcher] if isinstance(self.matcher, str) else self.matcher

        for pattern in patterns:
            if pattern == "*":
                return True
            if fnmatch.fnmatch(tool_name, pattern):
                return True

        return False


@dataclass
class HookConfig:
    """
    Configuration for tool hooks.

    Example:
        config = HookConfig()
        config.add_pre_tool_use("bash", check_dangerous_commands)
        config.add_pre_tool_use("*", confirm_writes)
        config.add_post_tool_use("*", log_tool_results)
    """
    pre_tool_use: List[HookMatcher] = field(default_factory=list)
    post_tool_use: List[PostHookMatcher] = field(default_factory=list)

    def add_pre_tool_use(
        self,
        matcher: Union[str, List[str], Callable[[str], bool]],
        hook: PreToolUseHook
    ) -> "HookConfig":
        """Add a pre-tool-use hook. Returns self for chaining."""
        self.pre_tool_use.append(HookMatcher(matcher=matcher, hook=hook))
        return self

    def add_post_tool_use(
        self,
        matcher: Union[str, List[str], Callable[[str], bool]],
        hook: PostToolUseHook
    ) -> "HookConfig":
        """Add a post-tool-use hook. Returns self for chaining."""
        self.post_tool_use.append(PostHookMatcher(matcher=matcher, hook=hook))
        return self


class ToolHooks(ABC):
    """
    Abstract base class for tool hooks.

    Implement this interface to intercept tool execution for:
    - Permission checking
    - Logging and monitoring
    - Protocol integration (ACP, etc.)
    """

    @abstractmethod
    async def pre_tool_use(self, info: ToolCallInfo) -> PreToolUseResult:
        """Called before a tool is executed."""
        pass

    @abstractmethod
    async def post_tool_use(
        self,
        info: ToolCallInfo,
        result: Any,
        error: Optional[Exception] = None,
    ) -> PostToolUseResult:
        """Called after a tool is executed."""
        pass


class NoOpToolHooks(ToolHooks):
    """Default no-op implementation of ToolHooks."""

    async def pre_tool_use(self, info: ToolCallInfo) -> PreToolUseResult:
        return PreToolUseResult(decision=PermissionDecision.ACCEPT)

    async def post_tool_use(
        self,
        info: ToolCallInfo,
        result: Any,
        error: Optional[Exception] = None,
    ) -> PostToolUseResult:
        return PostToolUseResult()


# ============================================================================
# Built-in Hook Implementations
# ============================================================================

def create_auto_accept_hook() -> PreToolUseHook:
    """Create a hook that auto-accepts all tool calls."""
    async def auto_accept(tool_name: str, tool_input: Dict[str, Any], tool_use_id: str) -> PreToolUseResult:
        return PreToolUseResult(decision=PermissionDecision.ACCEPT)
    return auto_accept


def create_auto_deny_hook(reason: str = "Tool execution blocked") -> PreToolUseHook:
    """Create a hook that denies all tool calls."""
    async def auto_deny(tool_name: str, tool_input: Dict[str, Any], tool_use_id: str) -> PreToolUseResult:
        return PreToolUseResult(decision=PermissionDecision.DENY, reason=reason)
    return auto_deny


def create_dangerous_command_check_hook(
    dangerous_patterns: Optional[List[str]] = None
) -> PreToolUseHook:
    """
    Create a hook that blocks dangerous bash commands.

    Args:
        dangerous_patterns: List of dangerous command patterns to block.
    """
    if dangerous_patterns is None:
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf ~",
            "rm -rf *",
            "sudo rm",
            "mkfs",
            "dd if=",
            ":(){:|:&};:",  # fork bomb
            "> /dev/sd",
            "chmod -R 777 /",
        ]

    async def check_dangerous(tool_name: str, tool_input: Dict[str, Any], tool_use_id: str) -> PreToolUseResult:
        if tool_name != "bash":
            return PreToolUseResult(decision=PermissionDecision.ACCEPT)

        command = tool_input.get("command", "")

        for pattern in dangerous_patterns:
            if pattern.lower() in command.lower():
                logger.warning(f"Blocked dangerous command: {command}")
                return PreToolUseResult(
                    decision=PermissionDecision.DENY,
                    reason=f"Dangerous command pattern detected: {pattern}"
                )

        return PreToolUseResult(decision=PermissionDecision.ACCEPT)

    return check_dangerous


def create_logging_hook() -> PostToolUseHook:
    """Create a hook that logs tool execution results."""
    async def log_result(
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: str,
        result: Any,
        error: Optional[Exception] = None
    ) -> PostToolUseResult:
        if error:
            logger.error(f"Tool {tool_name} failed: {error}")
        else:
            logger.info(f"Tool {tool_name} completed successfully")
        return PostToolUseResult()
    return log_result


# ============================================================================
# Tool Wrapper for Hook Integration
# ============================================================================

class HookedTool(AsyncBaseTool):
    """
    Wrapper that adds pre/post-tool-use hooks to any tool.

    This wrapper intercepts tool calls and runs configured hooks before
    and after executing the actual tool.

    Inherits from AsyncBaseTool so the executor properly awaits tool calls.
    """

    def __init__(
        self,
        tool: Any,
        hooks: HookConfig,
        tools_registry: Optional[Dict[str, Any]] = None,
        tool_use_id_generator: Optional[Callable[[], str]] = None,
    ):
        # Don't call super().__init__() - we manage our own state
        self._tool = tool
        self._hooks = hooks
        self._tools_registry = tools_registry or {}
        self._id_generator = tool_use_id_generator or self._default_id_generator
        self._call_counter = 0

        # Copy tool metadata from wrapped tool
        self.name = getattr(tool, 'name', type(tool).__name__)
        self.description = getattr(tool, 'description', '')
        self.inputs = getattr(tool, 'inputs', {})
        self.output_type = getattr(tool, 'output_type', 'string')
        self.readonly = getattr(tool, 'readonly', None)
        self.needs_state = getattr(tool, 'needs_state', False)

    def _default_id_generator(self) -> str:
        """Generate a unique tool use ID."""
        import time
        self._call_counter += 1
        return f"tool_{self.name}_{int(time.time() * 1000)}_{self._call_counter}"

    async def _run_pre_hooks(self, tool_input: Dict[str, Any], tool_use_id: str) -> PreToolUseResult:
        """Run all matching pre-tool-use hooks."""
        for matcher in self._hooks.pre_tool_use:
            if matcher.matches(self.name):
                try:
                    result = await matcher.hook(self.name, tool_input, tool_use_id)

                    if result.decision == PermissionDecision.DENY:
                        logger.info(f"Hook denied tool {self.name}: {result.reason}")
                        return result

                    if result.modified_input:
                        tool_input.update(result.modified_input)

                except Exception as e:
                    logger.error(f"Hook error for {self.name}: {e}")
                    return PreToolUseResult(
                        decision=PermissionDecision.DENY,
                        reason=f"Hook error: {e}"
                    )

        return PreToolUseResult(decision=PermissionDecision.ACCEPT)

    async def _run_post_hooks(
        self,
        tool_input: Dict[str, Any],
        tool_use_id: str,
        result: Any,
        error: Optional[Exception] = None
    ) -> PostToolUseResult:
        """Run all matching post-tool-use hooks."""
        final_result = PostToolUseResult()
        contexts = []

        for matcher in self._hooks.post_tool_use:
            if matcher.matches(self.name):
                try:
                    hook_result = await matcher.hook(
                        self.name, tool_input, tool_use_id, result, error
                    )

                    if hook_result.additional_context:
                        contexts.append(hook_result.additional_context)

                    if not hook_result.continue_execution:
                        final_result.continue_execution = False
                        final_result.stop_reason = hook_result.stop_reason

                except Exception as e:
                    logger.error(f"Post-hook error for {self.name}: {e}")

        if contexts:
            final_result.additional_context = "\n".join(contexts)

        return final_result

    async def forward(self, *args, **kwargs) -> Any:
        """Execute the tool with async hook checks."""
        import asyncio

        tool_use_id = self._id_generator()
        tool_input = kwargs.copy()

        if args:
            input_names = list(self.inputs.keys())
            for i, arg in enumerate(args):
                if i < len(input_names):
                    tool_input[input_names[i]] = arg

        # Run pre-hooks
        pre_result = await self._run_pre_hooks(tool_input, tool_use_id)

        if pre_result.decision == PermissionDecision.DENY:
            await self._run_post_hooks(
                tool_input, tool_use_id, None,
                Exception(f"Permission denied: {pre_result.reason}")
            )
            return f"Permission denied: {pre_result.reason or 'Tool execution blocked'}"

        if pre_result.modified_input:
            kwargs.update(pre_result.modified_input)

        # Execute tool
        result = None
        error = None
        try:
            forward_method = self._tool.forward
            if asyncio.iscoroutinefunction(forward_method):
                result = await forward_method(*args, **kwargs)
            else:
                result = forward_method(*args, **kwargs)
        except Exception as e:
            error = e
            logger.error(f"Tool {self.name} execution failed: {e}")

        # Run post-hooks
        post_result = await self._run_post_hooks(tool_input, tool_use_id, result, error)

        if not post_result.continue_execution:
            raise RuntimeError(f"Execution stopped: {post_result.stop_reason}")

        if error:
            raise error

        return result

    # Keep backward compatibility alias
    forward_async = forward

    async def __call__(self, *args, **kwargs) -> Any:
        return await self.forward(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tool, name)

    def format_for_observation(self, output: Any) -> str:
        if hasattr(self._tool, 'format_for_observation'):
            return self._tool.format_for_observation(output)
        return str(output)


def wrap_tools_with_hooks(
    tools: List[Any],
    hooks: HookConfig,
) -> List[HookedTool]:
    """Wrap a list of tools with hook support."""
    tools_registry = {
        getattr(t, 'name', type(t).__name__): t
        for t in tools
    }

    return [
        HookedTool(tool, hooks, tools_registry)
        for tool in tools
    ]


__all__ = [
    "PermissionDecision",
    "PreToolUseResult",
    "PostToolUseResult",
    "ToolCallInfo",
    "PreToolUseHook",
    "PostToolUseHook",
    "HookMatcher",
    "PostHookMatcher",
    "HookConfig",
    "ToolHooks",
    "NoOpToolHooks",
    "HookedTool",
    "wrap_tools_with_hooks",
    "create_auto_accept_hook",
    "create_auto_deny_hook",
    "create_dangerous_command_check_hook",
    "create_logging_hook",
]
