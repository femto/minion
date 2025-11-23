#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test tool observation formatting mechanism
"""
import pytest
import tempfile
import os
from minion.tools.file_tools import FileReadTool


class TestToolObservationFormatting:
    """Test the format_for_observation mechanism in tools"""

    def test_file_read_tool_forward_returns_raw_content(self):
        """Test that forward() returns raw file content without line numbers"""
        tool = FileReadTool()

        # Create a temporary file with test content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            test_content = "line 1\nline 2\nline 3"
            f.write(test_content)
            temp_file = f.name

        try:
            # Call forward() - should return raw content
            result = tool.forward(temp_file)
            assert result == test_content
            assert "1 |" not in result  # No line numbers in raw output
        finally:
            os.unlink(temp_file)

    def test_file_read_tool_observation_has_line_numbers(self):
        """Test that format_for_observation() adds line numbers"""
        tool = FileReadTool()

        # Create a temporary file with test content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            test_content = "first line\nsecond line\nthird line"
            f.write(test_content)
            temp_file = f.name

        try:
            # Get raw content
            raw_output = tool.forward(temp_file)

            # Format for observation
            formatted = tool.format_for_observation(raw_output)

            # Check that line numbers are present
            assert "1 | first line" in formatted
            assert "2 | second line" in formatted
            assert "3 | third line" in formatted

            # Verify format
            lines = formatted.split('\n')
            assert len(lines) == 3
            assert lines[0].startswith("1 |")
            assert lines[1].startswith("2 |")
            assert lines[2].startswith("3 |")
        finally:
            os.unlink(temp_file)

    def test_file_read_tool_observation_padding(self):
        """Test that line numbers are properly padded for alignment"""
        tool = FileReadTool()

        # Create content with many lines to test padding
        lines = [f"line {i}" for i in range(1, 12)]  # 11 lines, needs 2-digit padding
        test_content = '\n'.join(lines)

        formatted = tool.format_for_observation(test_content)

        # Check padding for single-digit line numbers
        assert " 1 | line 1" in formatted
        assert " 9 | line 9" in formatted

        # Check no extra padding for double-digit line numbers
        assert "10 | line 10" in formatted
        assert "11 | line 11" in formatted

    def test_file_read_tool_error_messages_unchanged(self):
        """Test that error messages are not modified by format_for_observation"""
        tool = FileReadTool()

        # Test with non-existent file
        error_output = tool.forward("/nonexistent/file.txt")
        assert error_output.startswith("Error:")

        # Format for observation should not add line numbers to errors
        formatted = tool.format_for_observation(error_output)
        assert formatted == error_output
        assert "1 |" not in formatted

    def test_base_tool_default_format_for_observation(self):
        """Test that BaseTool's default format_for_observation just converts to string"""
        from minion.tools.base_tool import BaseTool

        class SimpleTestTool(BaseTool):
            name = "test_tool"
            description = "A simple test tool"
            inputs = {}
            output_type = "string"

            def forward(self):
                return {"result": "test"}

        tool = SimpleTestTool()

        # Test default implementation
        output = {"result": "test"}
        formatted = tool.format_for_observation(output)
        assert formatted == str(output)

    def test_format_for_observation_with_none(self):
        """Test that format_for_observation handles None output gracefully"""
        tool = FileReadTool()

        formatted = tool.format_for_observation(None)
        assert formatted == "None"  # Default behavior from str(None)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
