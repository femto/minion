#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick integration test for MinionCodeAgent and coding tools.
This test verifies that all components can be imported and instantiated.
"""
import asyncio
import tempfile
import os


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        # Test tool imports
        from minion.tools.coding_tools import (
            FileReadTool,
            FileWriteTool,
            FileEditTool,
            GrepTool,
            GlobTool,
            BashCommandTool,
        )
        print("  ✓ Coding tools imported successfully")

        # Test agent import
        from minion.agents import MinionCodeAgent
        print("  ✓ MinionCodeAgent imported successfully")

        # Test that tools can be instantiated
        file_read = FileReadTool()
        file_write = FileWriteTool()
        file_edit = FileEditTool()
        grep = GrepTool()
        glob_tool = GlobTool()
        print("  ✓ All tools instantiated successfully")

        return True

    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_tool_functionality():
    """Test basic tool functionality without requiring LLM"""
    print("\nTesting tool functionality...")

    try:
        from minion.tools.coding_tools import (
            FileReadTool,
            FileWriteTool,
            FileEditTool,
            GrepTool,
            GlobTool,
        )

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            test_file = f.name
            f.write("Hello, World!\nThis is a test file.\nHello again!")

        try:
            # Test FileReadTool
            file_read = FileReadTool()
            content = file_read(test_file)
            assert "Hello, World!" in content, "FileReadTool failed to read file"
            print("  ✓ FileReadTool works")

            # Test FileWriteTool
            file_write = FileWriteTool()
            new_file = tempfile.mktemp(suffix='.txt')
            result = file_write(new_file, "Test content")
            assert "Successfully wrote" in result, "FileWriteTool failed"
            print("  ✓ FileWriteTool works")

            # Test FileEditTool
            file_edit = FileEditTool()
            result = file_edit(test_file, "Hello", "Hi")
            assert "Successfully replaced" in result, "FileEditTool failed"
            print("  ✓ FileEditTool works")

            # Test GrepTool
            grep = GrepTool()
            result = grep("test", test_file)
            assert "Found" in result or "match" in result.lower(), "GrepTool failed"
            print("  ✓ GrepTool works")

            # Test GlobTool
            glob_tool = GlobTool()
            temp_dir = os.path.dirname(test_file)
            result = glob_tool("*.txt", temp_dir)
            assert "Found" in result or test_file in result, "GlobTool failed"
            print("  ✓ GlobTool works")

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(new_file):
                os.remove(new_file)

        return True

    except Exception as e:
        print(f"  ✗ Tool functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_creation():
    """Test that MinionCodeAgent can be created and setup"""
    print("\nTesting agent creation...")

    try:
        from minion.agents import MinionCodeAgent

        # Create agent without requiring API keys
        agent = MinionCodeAgent(
            name="test_agent",
            include_coding_tools=True,
        )

        # Check that tools were added
        tool_names = {tool.name for tool in agent.tools if hasattr(tool, 'name')}
        expected_tools = {'file_read', 'file_write', 'file_edit', 'grep', 'glob', 'bash_command'}

        if not expected_tools.issubset(tool_names):
            missing = expected_tools - tool_names
            print(f"  ✗ Missing tools: {missing}")
            return False

        print(f"  ✓ Agent created with {len(tool_names)} tools")
        print(f"  ✓ Coding tools included: {sorted(tool_names & expected_tools)}")

        # Test selective tools
        agent2 = MinionCodeAgent(
            name="selective_agent",
            coding_tools_to_include=['file_read', 'grep'],
        )

        tool_names2 = {tool.name for tool in agent2.tools if hasattr(tool, 'name')}
        assert 'file_read' in tool_names2, "file_read not included"
        assert 'grep' in tool_names2, "grep not included"
        assert 'file_write' not in tool_names2, "file_write should not be included"

        print(f"  ✓ Selective tool inclusion works")

        return True

    except Exception as e:
        print(f"  ✗ Agent creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("=" * 80)
    print("MinionCodeAgent Integration Test")
    print("=" * 80)

    results = []

    # Test imports
    results.append(("Imports", test_imports()))

    # Test tool functionality
    results.append(("Tool Functionality", test_tool_functionality()))

    # Test agent creation
    results.append(("Agent Creation", asyncio.run(test_agent_creation())))

    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary:")
    print("=" * 80)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n🎉 All tests passed! Integration successful.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
