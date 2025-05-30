#!/usr/bin/env python3
"""
Pytest tests for python_server assignment handling logic
"""

import sys
import os
import pytest

# Add the docker/utils directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docker', 'utils'))

from python_server import MyService


@pytest.fixture
def python_service():
    """Create a MyService instance for testing"""
    return MyService()


class TestPythonServerAssignment:
    """Test class for python_server assignment handling"""

    def test_simple_assignment(self, python_service):
        """Test simple assignment shows value"""
        result = python_service.exposed_execute("x = 42")
        assert result["output"] == "42"
        assert result["error"] == ""

    def test_string_assignment(self, python_service):
        """Test string assignment shows value"""
        result = python_service.exposed_execute("name = 'Alice'")
        assert result["output"] == "Alice"
        assert result["error"] == ""

    def test_list_assignment(self, python_service):
        """Test list assignment shows value"""
        result = python_service.exposed_execute("numbers = [1, 2, 3]")
        assert result["output"] == "[1, 2, 3]"
        assert result["error"] == ""

    def test_computation_assignment(self, python_service):
        """Test computation assignment shows result"""
        result = python_service.exposed_execute("result = 2 + 3 * 4")
        assert result["output"] == "14"
        assert result["error"] == ""

    def test_print_statement(self, python_service):
        """Test print statement shows normal output"""
        result = python_service.exposed_execute("print('Hello')")
        assert "Hello" in result["output"]
        assert result["error"] == ""

    def test_multiline_statements(self, python_service):
        """Test multiline statements work correctly"""
        result = python_service.exposed_execute("a = 5\nprint(a)")
        assert "5" in result["output"]
        assert result["error"] == ""

    def test_function_call_assignment(self, python_service):
        """Test function call with assignment"""
        result = python_service.exposed_execute("squared = pow(3, 2)")
        assert result["output"] == "9"
        assert result["error"] == ""

    def test_error_handling(self, python_service):
        """Test error handling works correctly"""
        result = python_service.exposed_execute("1/0")
        assert "ZeroDivisionError" in result["error"]

    def test_reset_container(self, python_service):
        """Test container reset functionality"""
        # First set a variable
        python_service.exposed_execute("test_var = 123")
        # Reset the container
        result = python_service.exposed_execute("RESET_CONTAINER_SPECIAL_KEYWORD")
        assert result["output"] == ""
        assert result["error"] == ""

    def test_namespace_isolation_with_id(self, python_service):
        """Test namespace isolation with different IDs"""
        # Set variable in namespace 1
        result1 = python_service.exposed_execute("<id>ns1</id>x = 100")
        assert result1["output"] == "100"
        
        # Set variable in namespace 2
        result2 = python_service.exposed_execute("<id>ns2</id>x = 200")
        assert result2["output"] == "200"
        
        # Verify namespace 1 still has its value
        result3 = python_service.exposed_execute("<id>ns1</id>print(x)")
        assert "100" in result3["output"]

    def test_multiple_assignments_in_one_command(self, python_service):
        """Test multiple assignments in one command"""
        result = python_service.exposed_execute("a = 1\nb = 2\nc = a + b")
        # Should show the last assignment value
        assert result["output"] == "3"
        assert result["error"] == ""

    def test_assignment_with_expression(self, python_service):
        """Test assignment with complex expression"""
        result = python_service.exposed_execute("result = sum([1, 2, 3, 4, 5])")
        assert result["output"] == "15"
        assert result["error"] == ""

    def test_no_assignment_no_output_change(self, python_service):
        """Test that commands without assignment work normally"""
        # Test import statement
        result = python_service.exposed_execute("import math")
        assert result["output"] == ""
        assert result["error"] == ""
        
        # Test function definition
        result = python_service.exposed_execute("def test_func(): return 42")
        assert result["output"] == ""
        assert result["error"] == "" 