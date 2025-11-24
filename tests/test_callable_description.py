#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test for callable description support in tools
"""
import pytest


def test_static_description():
    """Test that static string descriptions still work"""
    from minion.tools.base_tool import BaseTool

    class StaticDescriptionTool(BaseTool):
        """Tool with static string description"""
        name = "static_tool"
        description = "This is a static description"
        inputs = {"param": {"type": "string", "description": "A parameter"}}
        output_type = "string"

        def forward(self, param: str) -> str:
            return f"Result: {param}"

    tool = StaticDescriptionTool()

    # Test that the description attribute exists
    assert hasattr(tool, 'description')

    # Test that it's a string
    assert isinstance(tool.description, str)
    assert tool.description == "This is a static description"

    # Test that the callable check works correctly
    assert not callable(tool.description)


def test_callable_description():
    """Test that callable descriptions work"""
    from minion.tools.base_tool import BaseTool

    class CallableDescriptionTool(BaseTool):
        """Tool with callable description"""
        name = "callable_tool"
        inputs = {"param": {"type": "string", "description": "A parameter"}}
        output_type = "string"

        @staticmethod
        def description():
            """Dynamically generate description"""
            return "This is a dynamically generated description from callable"

        def forward(self, param: str) -> str:
            return f"Result: {param}"

    tool = CallableDescriptionTool()

    # Test that the description attribute exists
    assert hasattr(tool, 'description')

    # Test that it's callable
    assert callable(tool.description)

    # Test that calling it returns the expected string
    assert tool.description() == "This is a dynamically generated description from callable"


def test_dynamic_context_description():
    """Test that callable descriptions can access instance state"""
    from minion.tools.base_tool import BaseTool

    class DynamicContextDescriptionTool(BaseTool):
        """Tool with description that depends on instance state"""
        name = "dynamic_context_tool"
        inputs = {"param": {"type": "string", "description": "A parameter"}}
        output_type = "string"

        def __init__(self, context: str = "default"):
            super().__init__()
            self.context = context

        def description(self):
            """Description that uses instance state"""
            return f"This tool operates in {self.context} context"

        def forward(self, param: str) -> str:
            return f"Result in {self.context}: {param}"

    tool = DynamicContextDescriptionTool(context="production")

    # Test that description is callable
    assert callable(tool.description)

    # Test that it returns context-specific description
    assert tool.description() == "This tool operates in production context"

    # Test with different context
    tool2 = DynamicContextDescriptionTool(context="development")
    assert tool2.description() == "This tool operates in development context"


def test_description_formatting_logic():
    """Test the core logic for handling callable descriptions"""
    from minion.tools.base_tool import BaseTool

    class StaticTool(BaseTool):
        name = "static"
        description = "Static description"
        inputs = {}
        output_type = "string"

        def forward(self):
            return "static"

    class CallableTool(BaseTool):
        name = "callable"
        inputs = {}
        output_type = "string"

        @staticmethod
        def description():
            return "Callable description"

        def forward(self):
            return "callable"

    # Test the logic that we use in lmp_action_node
    static_tool = StaticTool()
    callable_tool = CallableTool()

    # This is the logic from lmp_action_node.py line 561
    static_desc = static_tool.description() if callable(static_tool.description) else static_tool.description
    callable_desc = callable_tool.description() if callable(callable_tool.description) else callable_tool.description

    assert static_desc == "Static description"
    assert callable_desc == "Callable description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
