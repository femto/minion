#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : base_tool.py
"""
import warnings
#modified from smolagents

from abc import ABC, abstractmethod
import inspect
import json
import textwrap
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable, List, Union, Set, TypeVar, get_type_hints
import functools
import ast
import sys

from minion.tools.tool_decorator import get_imports


class BaseTool(ABC):
    """工具基类，定义所有工具的基本接口"""
    
    name: str = "base_tool"
    description: str = "基础工具类，所有工具应继承此类"
    inputs: Dict[str, Dict[str, Any]] = {}
    output_type: str
    output_schema: dict[str, Any] | None = None #not used now
    readonly: bool | None = None
    needs_state: bool = False  # 是否需要接收agent state
    
    def __init__(self):
        """初始化工具"""
        self.is_initialized = False
        
    def __call__(self, *args, **kwargs) -> Any:
        """
        调用工具执行，这是工具的主入口
        
        Returns:
            工具执行结果
        """
        if not self.is_initialized:
            self.setup()
            
        # 处理传入单一字典的情况
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            potential_kwargs = args[0]
            if all(key in self.inputs for key in potential_kwargs):
                args = ()
                kwargs = potential_kwargs
                
        return self.forward(*args, **kwargs)
    
    @abstractmethod
    def forward(self, *args, **kwargs) -> Any:
        """
        实际的工具执行逻辑，子类必须实现此方法

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            工具执行结果
        """
        raise NotImplementedError("工具子类必须实现forward方法")

    def format_for_observation(self, output: Any) -> str:
        """
        Format tool output for LLM observation (when tool call is the last item in code).

        This method can be overridden by tools to provide LLM-friendly formatting
        of their output when used as observations. For example:
        - file_read tool can add line numbers
        - search tool can format results with highlighting
        - calculator tool can show step-by-step computation

        Args:
            output: The raw output from forward() method

        Returns:
            Formatted string suitable for LLM observation

        Default behavior: Convert output to string
        """
        return str(output) if output is not None else ""
    
    def setup(self):
        """
        在首次使用前执行初始化操作
        用于执行耗时的初始化操作（如加载模型）
        """
        self.is_initialized = True
        
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示
        
        Returns:
            工具的字典表示
        """
        imports = set()
        tool_code = f"""
class {self.__class__.__name__}(BaseTool):
    name = "{self.name}"
    description = "{self.description}"
    inputs = {repr(self.inputs)}
    output_type = "{self.output_type}"
    readonly = {self.readonly}
    
    def __init__(self):
        super().__init__()
        self.is_initialized = True
        
    def forward(self, *args, **kwargs):
        # 实现工具的逻辑
        pass
"""
        imports = get_imports(tool_code)
        requirements = {el for el in imports if el not in sys.stdlib_module_names}
        
        return {
            "name": self.name,
            "code": tool_code,
            "requirements": sorted(list(requirements))
        }

class ToolCollection:
    """工具集合，用于管理多个工具"""
    
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools
        
    @classmethod
    def from_directory(cls, directory_path: str) -> 'ToolCollection':
        """从目录加载所有工具"""
        # 实现从目录加载工具的逻辑
        pass


#from smolagents
class Toolset:
    """
    Tool collections enable loading a collection of tools in the agent's toolbox.

    Collections can be loaded from a collection in the Hub or from an MCP server, see:
    - [`Toolset.from_hub`]
    - [`Toolset.from_mcp`]

    For example and usage, see: [`Toolset.from_hub`] and [`Toolset.from_mcp`]
    """

    def __init__(self, tools: list[BaseTool]):
        self.tools = tools

    @classmethod
    async def create(cls, *args, **kwargs):
        """
        异步创建并设置实例

        Args:
            *args: 传递给构造函数的位置参数
            **kwargs: 传递给构造函数的关键字参数

        Returns:
            instance: 已设置完成的实例
        """
        instance = cls(*args, **kwargs)
        await instance.setup()
        return instance

    @classmethod
    def from_hub(
        cls,
        collection_slug: str,
        token: Optional[str] = None,
        trust_remote_code: bool = False,
    ) -> "Toolset":
        """Loads a tool collection from the Hub.

        it adds a collection of tools from all Spaces in the collection to the agent's toolbox

        > [!NOTE]
        > Only Spaces will be fetched, so you can feel free to add models and datasets to your collection if you'd
        > like for this collection to showcase them.

        Args:
            collection_slug (str): The collection slug referencing the collection.
            token (str, *optional*): The authentication token if the collection is private.
            trust_remote_code (bool, *optional*, defaults to False): Whether to trust the remote code.

        Returns:
            Toolset: A tool collection instance loaded with the tools.

        Example:
        ```py
        >>> from smolagents import Toolset, CodeAgent

        >>> image_tool_collection = Toolset.from_hub("huggingface-tools/diffusion-tools-6630bb19a942c2306a2cdb6f")
        >>> agent = CodeAgent(tools=[*image_tool_collection.tools], add_base_tools=True)

        >>> agent.run("Please draw me a picture of rivers and lakes.")
        ```
        """
        _collection = get_collection(collection_slug, token=token)
        _hub_repo_ids = {item.item_id for item in _collection.items if item.item_type == "space"}

        tools = [Tool.from_hub(repo_id, token, trust_remote_code) for repo_id in _hub_repo_ids]

        return cls(tools)

    @classmethod
    @contextmanager
    def from_mcp(
        cls,
        server_parameters: Union["mcp.StdioServerParameters", dict],
        trust_remote_code: bool = False,
        structured_output: Optional[bool] = None,
    ) -> "Toolset":
        """Automatically load a tool collection from an MCP server.

        This method supports Stdio, Streamable HTTP, and legacy HTTP+SSE MCP servers. Look at the `server_parameters`
        argument for more details on how to connect to each MCP server.

        Note: a separate thread will be spawned to run an asyncio event loop handling
        the MCP server.

        Args:
            server_parameters (`mcp.StdioServerParameters` or `dict`):
                Configuration parameters to connect to the MCP server. This can be:

                - An instance of `mcp.StdioServerParameters` for connecting a Stdio MCP server via standard input/output using a subprocess.

                - A `dict` with at least:
                  - "url": URL of the server.
                  - "transport": Transport protocol to use, one of:
                    - "streamable-http": Streamable HTTP transport (default).
                    - "sse": Legacy HTTP+SSE transport (deprecated).
            trust_remote_code (`bool`, *optional*, defaults to `False`):
                Whether to trust the execution of code from tools defined on the MCP server.
                This option should only be set to `True` if you trust the MCP server,
                and undertand the risks associated with running remote code on your local machine.
                If set to `False`, loading tools from MCP will fail.
            structured_output (`bool`, *optional*, defaults to `False`):
                Whether to enable structured output features for MCP tools. If True, enables:
                - Support for outputSchema in MCP tools
                - Structured content handling (structuredContent from MCP responses)
                - JSON parsing fallback for structured data
                If False, uses the original simple text-only behavior for backwards compatibility.

        Returns:
            Toolset: A tool collection instance.

        Example with a Stdio MCP server:
        ```py
        >>> import os
        >>> from smolagents import Toolset, CodeAgent, InferenceClientModel
        >>> from mcp import StdioServerParameters

        >>> model = InferenceClientModel()

        >>> server_parameters = StdioServerParameters(
        >>>     command="uvx",
        >>>     args=["--quiet", "pubmedmcp@0.1.3"],
        >>>     env={"UV_PYTHON": "3.12", **os.environ},
        >>> )

        >>> with Toolset.from_mcp(server_parameters, trust_remote_code=True) as tool_collection:
        >>>     agent = CodeAgent(tools=[*tool_collection.tools], add_base_tools=True, model=model)
        >>>     agent.run("Please find a remedy for hangover.")
        ```

        Example with structured output enabled:
        ```py
        >>> with Toolset.from_mcp(server_parameters, trust_remote_code=True, structured_output=True) as tool_collection:
        >>>     agent = CodeAgent(tools=[*tool_collection.tools], add_base_tools=True, model=model)
        >>>     agent.run("Please find a remedy for hangover.")
        ```

        Example with a Streamable HTTP MCP server:
        ```py
        >>> with Toolset.from_mcp({"url": "http://127.0.0.1:8000/mcp", "transport": "streamable-http"}, trust_remote_code=True) as tool_collection:
        >>>     agent = CodeAgent(tools=[*tool_collection.tools], add_base_tools=True, model=model)
        >>>     agent.run("Please find a remedy for hangover.")
        ```
        """
        # Handle future warning for structured_output default value change
        if structured_output is None:
            warnings.warn(
                "Parameter 'structured_output' was not specified. "
                "Currently it defaults to False, but in version 1.25, the default will change to True. "
                "To suppress this warning, explicitly set structured_output=True (new behavior) or structured_output=False (legacy behavior). "
                "See documentation at https://huggingface.co/docs/smolagents/tutorials/tools#structured-output-and-output-schema-support for more details.",
                FutureWarning,
                stacklevel=2,
            )
            structured_output = False

        try:
            from mcpadapt.core import MCPAdapt
            from mcpadapt.smolagents_adapter import SmolAgentsAdapter
        except ImportError:
            raise ImportError(
                """Please install 'mcp' extra to use Toolset.from_mcp: `pip install 'smolagents[mcp]'`."""
            )
        if isinstance(server_parameters, dict):
            transport = server_parameters.get("transport")
            if transport is None:
                transport = "streamable-http"
                server_parameters["transport"] = transport
            if transport not in {"sse", "streamable-http"}:
                raise ValueError(
                    f"Unsupported transport: {transport}. Supported transports are 'streamable-http' and 'sse'."
                )
        if not trust_remote_code:
            raise ValueError(
                "Loading tools from MCP requires you to acknowledge you trust the MCP server, "
                "as it will execute code on your local machine: pass `trust_remote_code=True`."
            )
        with MCPAdapt(server_parameters, SmolAgentsAdapter(structured_output=structured_output)) as tools:
            yield cls(tools)