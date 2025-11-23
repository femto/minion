#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Manual test for tool observation formatting mechanism
"""
import tempfile
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.tools.file_tools import FileReadTool


def test_file_read_tool():
    """Test FileReadTool with observation formatting"""
    print("=" * 60)
    print("Testing FileReadTool observation formatting")
    print("=" * 60)

    tool = FileReadTool()

    # Create a temporary file with test content
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_content = """def hello_world():
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()"""
        f.write(test_content)
        temp_file = f.name

    try:
        # Test 1: forward() returns raw content
        print("\n1. Testing forward() - should return RAW content:")
        print("-" * 60)
        raw_output = tool.forward(temp_file)
        print(raw_output)
        print("-" * 60)
        assert "1 |" not in raw_output, "Raw output should NOT have line numbers"
        print("✓ PASS: forward() returns raw content without line numbers\n")

        # Test 2: format_for_observation() adds line numbers
        print("2. Testing format_for_observation() - should add LINE NUMBERS:")
        print("-" * 60)
        formatted = tool.format_for_observation(raw_output)
        print(formatted)
        print("-" * 60)
        assert "1 | def hello_world():" in formatted, "Should have line numbers"
        assert "2 |     print(\"Hello, World!\")" in formatted, "Should have line numbers"
        print("✓ PASS: format_for_observation() adds line numbers\n")

        # Test 3: Error messages are not modified
        print("3. Testing error handling:")
        print("-" * 60)
        error_output = tool.forward("/nonexistent/file.txt")
        print(f"Error output: {error_output}")
        formatted_error = tool.format_for_observation(error_output)
        print(f"Formatted error: {formatted_error}")
        assert error_output == formatted_error, "Error messages should not be modified"
        print("✓ PASS: Error messages are not modified\n")

        # Test 4: Line number padding
        print("4. Testing line number padding:")
        print("-" * 60)
        many_lines = "\n".join([f"line {i}" for i in range(1, 12)])
        formatted_many = tool.format_for_observation(many_lines)
        print(formatted_many)
        print("-" * 60)
        assert " 1 | line 1" in formatted_many, "Single digit should be padded"
        assert "10 | line 10" in formatted_many, "Double digit should not be padded extra"
        print("✓ PASS: Line numbers are properly padded\n")

    finally:
        os.unlink(temp_file)

    print("=" * 60)
    print("All tests PASSED! ✓")
    print("=" * 60)


def demo_use_case():
    """Demonstrate the use case difference"""
    print("\n\n")
    print("=" * 60)
    print("DEMONSTRATION: Use Case Comparison")
    print("=" * 60)

    tool = FileReadTool()

    # Create a sample file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write("import sys\n")
        f.write("def main():\n")
        f.write("    print('Hello')\n")
        temp_file = f.name

    try:
        raw = tool.forward(temp_file)
        formatted = tool.format_for_observation(raw)

        print("\n📁 USE CASE 1: Tool call in middle of code")
        print("   (Returns raw content for further processing)")
        print("-" * 60)
        print("Code:")
        print("  content = file_read(file_path='script.py')")
        print("  lines = content.split('\\n')")
        print("  first_line = lines[0]")
        print("\nOutput value that gets assigned to 'content':")
        print(raw)
        print("-" * 60)

        print("\n📝 USE CASE 2: Tool call as LAST item in code")
        print("   (Becomes observation with line numbers for LLM)")
        print("-" * 60)
        print("Code:")
        print("  file_read(file_path='script.py')")
        print("\nObservation shown to LLM:")
        print(formatted)
        print("-" * 60)

        print("\n💡 KEY INSIGHT:")
        print("   - Same tool, different contexts!")
        print("   - Middle of code: Returns raw data for processing")
        print("   - Last in code: Formatted view for LLM understanding")
        print("   - LLM can now say: 'Look at line 3 where print is called'")

    finally:
        os.unlink(temp_file)


if __name__ == '__main__':
    test_file_read_tool()
    demo_use_case()
