#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MinionCodeAgent Example: Demonstrates using the MinionCodeAgent for coding tasks.

This example shows how to use MinionCodeAgent with its built-in coding tools
to perform file operations and code analysis tasks.
"""
import asyncio
import os
from pathlib import Path

# Import the MinionCodeAgent
from minion.agents import MinionCodeAgent
from minion.types.llm_types import ModelType


async def example_basic_usage():
    """Basic usage of MinionCodeAgent"""
    print("\n=== Example 1: Basic File Operations ===\n")

    # Create the agent with automatic coding tools
    agent = MinionCodeAgent(
        name="file_assistant",
        model="gpt-4o",  # or ModelType.GPT4O
    )

    # Setup the agent
    await agent.setup()

    # Test file reading
    task = """
    Please read the README.md file in the current directory and tell me:
    1. How many lines are in the file
    2. What is the main topic of the file
    """

    print(f"Task: {task}\n")
    result = await agent.run_async(task)
    print(f"Result: {result}\n")

    # Cleanup
    await agent.close()


async def example_file_analysis():
    """Example of analyzing code files"""
    print("\n=== Example 2: Code File Analysis ===\n")

    agent = MinionCodeAgent(
        name="code_analyzer",
        model="gpt-4o",
    )

    await agent.setup()

    # Find and analyze Python files
    task = """
    Use the glob tool to find all Python files (*.py) in the minion/agents directory,
    then read the first file and tell me what classes are defined in it.
    """

    print(f"Task: {task}\n")
    result = await agent.run_async(task)
    print(f"Result: {result}\n")

    await agent.close()


async def example_search_and_replace():
    """Example of searching and replacing in files"""
    print("\n=== Example 3: Search and Replace ===\n")

    agent = MinionCodeAgent(
        name="refactor_assistant",
        model="gpt-4o",
    )

    await agent.setup()

    # Create a test file first
    test_file = "/tmp/test_code.py"
    test_content = '''
def old_function_name():
    """This is the old function name."""
    return "Hello, World!"

# Call the old function
result = old_function_name()
print(result)
'''

    # Write the test file
    with open(test_file, 'w') as f:
        f.write(test_content)

    # Task to rename function
    task = f"""
    Please do the following:
    1. Read the file {test_file}
    2. Use grep to find all occurrences of 'old_function_name'
    3. Use file_edit to replace 'old_function_name' with 'new_function_name'
    4. Read the file again to verify the changes
    """

    print(f"Task: {task}\n")
    result = await agent.run_async(task)
    print(f"Result: {result}\n")

    # Cleanup
    os.remove(test_file)
    await agent.close()


async def example_with_custom_tools():
    """Example of MinionCodeAgent with additional custom tools"""
    print("\n=== Example 4: Custom Tools ===\n")

    from minion.tools import tool

    # Define a custom tool
    @tool
    def count_lines(file_path: str) -> str:
        """
        Count the number of lines in a file.

        Args:
            file_path: Path to the file

        Returns:
            Number of lines in the file
        """
        try:
            with open(file_path, 'r') as f:
                lines = len(f.readlines())
            return f"File has {lines} lines."
        except Exception as e:
            return f"Error: {str(e)}"

    # Create agent with custom tool
    agent = MinionCodeAgent(
        name="enhanced_assistant",
        model="gpt-4o",
        tools=[count_lines],  # Add custom tool alongside coding tools
    )

    await agent.setup()

    # The agent now has both coding tools and the custom count_lines tool
    task = """
    Use the count_lines tool to count lines in README.md,
    then use file_read to read the first 5 lines of the file.
    """

    print(f"Task: {task}\n")
    result = await agent.run_async(task)
    print(f"Result: {result}\n")

    await agent.close()


async def example_selective_tools():
    """Example of MinionCodeAgent with only specific coding tools"""
    print("\n=== Example 5: Selective Coding Tools ===\n")

    # Create agent with only file read and grep tools
    agent = MinionCodeAgent(
        name="readonly_assistant",
        model="gpt-4o",
        coding_tools_to_include=['file_read', 'grep', 'glob'],  # Only include specific tools
    )

    await agent.setup()

    # This agent can only read files, search, and find files (no write/edit)
    task = """
    Find all Python files in the minion/tools directory using glob,
    then search for 'BaseTool' in those files using grep.
    """

    print(f"Task: {task}\n")
    result = await agent.run_async(task)
    print(f"Result: {result}\n")

    await agent.close()


async def main():
    """Run all examples"""
    print("=" * 80)
    print("MinionCodeAgent Examples")
    print("=" * 80)

    try:
        # Run examples
        await example_basic_usage()
        await example_file_analysis()
        await example_search_and_replace()
        await example_with_custom_tools()
        await example_selective_tools()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Note: Make sure you have your API keys configured
    # For OpenAI: export OPENAI_API_KEY="your-key"
    # For other providers, see minion documentation

    asyncio.run(main())
