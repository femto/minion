#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standalone test for observation formatting (no package imports)
"""
import tempfile
import os


# Inline BaseTool for testing
class BaseTool:
    def format_for_observation(self, output):
        """Default implementation"""
        return str(output) if output is not None else ""


# Inline FileReadTool for testing
class FileReadTool(BaseTool):
    """Tool for reading file contents with observation formatting"""

    def forward(self, file_path: str) -> str:
        """Read and return file contents"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            return f"Error: File not found: {file_path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def format_for_observation(self, output) -> str:
        """Format file content with line numbers for LLM observation"""
        if not isinstance(output, str):
            return str(output)

        # Check if this is an error message
        if output.startswith("Error:"):
            return output

        # Add line numbers to each line
        lines = output.split('\n')
        formatted_lines = []

        # Calculate padding for line numbers
        max_line_num = len(lines)
        padding = len(str(max_line_num))

        for i, line in enumerate(lines, start=1):
            line_num = str(i).rjust(padding)
            formatted_lines.append(f"{line_num} | {line}")

        return '\n'.join(formatted_lines)


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("Testing Tool Observation Formatting Mechanism")
    print("=" * 70)

    tool = FileReadTool()

    # Create a test file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        test_code = """def calculate_sum(a, b):
    result = a + b
    return result

total = calculate_sum(10, 20)
print(f"Total: {total}")"""
        f.write(test_code)
        temp_file = f.name

    try:
        # Test 1: Raw output (for use in code)
        print("\n✓ TEST 1: forward() returns RAW content")
        print("-" * 70)
        raw = tool.forward(temp_file)
        print("Raw output (as would be used in code):")
        print(raw)
        assert "1 |" not in raw
        print("\n✓ PASS: No line numbers in raw output")

        # Test 2: Formatted for observation (for LLM)
        print("\n✓ TEST 2: format_for_observation() adds line numbers")
        print("-" * 70)
        formatted = tool.format_for_observation(raw)
        print("Formatted for LLM observation:")
        print(formatted)
        assert "1 | def calculate_sum(a, b):" in formatted
        assert "2 |     result = a + b" in formatted
        print("\n✓ PASS: Line numbers added correctly")

        # Test 3: Padding
        print("\n✓ TEST 3: Line number padding works correctly")
        print("-" * 70)
        many_lines = "\n".join([f"line {i}" for i in range(1, 15)])
        formatted_many = tool.format_for_observation(many_lines)
        print("First few lines:")
        print('\n'.join(formatted_many.split('\n')[:5]))
        print("...")
        print("Last few lines:")
        print('\n'.join(formatted_many.split('\n')[-3:]))
        assert " 1 | line 1" in formatted_many  # Space padding for single digit
        assert "14 | line 14" in formatted_many  # No extra space for double digit
        print("\n✓ PASS: Padding is correct")

        # Test 4: Error handling
        print("\n✓ TEST 4: Error messages are not modified")
        print("-" * 70)
        error = tool.forward("/nonexistent/file.txt")
        formatted_error = tool.format_for_observation(error)
        print(f"Error: {error}")
        print(f"Formatted: {formatted_error}")
        assert error == formatted_error
        print("\n✓ PASS: Errors unchanged")

    finally:
        os.unlink(temp_file)

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓✓✓")
    print("=" * 70)


def demo_use_case():
    """Show the practical use case"""
    print("\n\n")
    print("=" * 70)
    print("PRACTICAL DEMONSTRATION")
    print("=" * 70)

    tool = FileReadTool()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write("import math\n\ndef area(r):\n    return math.pi * r ** 2\n")
        temp_file = f.name

    try:
        raw = tool.forward(temp_file)
        formatted = tool.format_for_observation(raw)

        print("\n🎯 SCENARIO: Agent needs to understand a Python file")
        print("-" * 70)

        print("\n📝 Case A: Tool used IN CODE (for processing)")
        print("Code: content = file_read(file_path='area.py')")
        print("      first_line = content.split('\\n')[0]")
        print("\nTool returns RAW content:")
        print(f'"{raw}"')
        print("\n→ Raw string can be split, processed, passed to other functions")

        print("\n" + "-" * 70)
        print("\n📊 Case B: Tool is LAST STATEMENT (becomes observation)")
        print("Code: file_read(file_path='area.py')")
        print("\nObservation shown to LLM:")
        print(formatted)
        print("\n→ LLM can now reference 'line 3' or 'line 4' precisely!")
        print("→ Better for understanding and discussing code structure")

        print("\n" + "=" * 70)
        print("💡 KEY BENEFIT:")
        print("   Same tool, context-aware output formatting!")
        print("   - Code needs raw data → returns raw string")
        print("   - LLM needs to understand → returns formatted with line numbers")
        print("=" * 70)

    finally:
        os.unlink(temp_file)


if __name__ == '__main__':
    run_tests()
    demo_use_case()
