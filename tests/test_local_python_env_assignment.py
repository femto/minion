#!/usr/bin/env python3
"""
Pytest tests for LocalPythonEnv assignment handling logic
"""

import pytest
from minion.main.local_python_env import LocalPythonEnv


@pytest.fixture
def python_env():
    """Create a LocalPythonEnv instance for testing"""
    return LocalPythonEnv(verbose=False)


class TestLocalPythonEnvAssignment:
    """Test class for LocalPythonEnv assignment handling"""

    def test_simple_assignment(self, python_env):
        """Test simple assignment shows value"""
        obs, reward, terminated, truncated, info = python_env.step('x = 42')
        assert obs["output"] == "42"
        assert obs["error"] == ""

    def test_string_assignment(self, python_env):
        """Test string assignment shows value"""
        obs, reward, terminated, truncated, info = python_env.step("name = 'Alice'")
        assert obs["output"] == "Alice"
        assert obs["error"] == ""

    def test_list_assignment(self, python_env):
        """Test list assignment shows value"""
        obs, reward, terminated, truncated, info = python_env.step("numbers = [1, 2, 3]")
        assert obs["output"] == "[1, 2, 3]"
        assert obs["error"] == ""

    def test_expression_evaluation(self, python_env):
        """Test expression evaluation shows result"""
        obs, reward, terminated, truncated, info = python_env.step("7 * 8")
        assert "56" in obs["output"]
        assert obs["error"] == ""

    def test_last_result_access(self, python_env):
        """Test accessing last result using _"""
        # First create an expression result
        python_env.step("7 * 8")
        # Then access it with _
        obs, reward, terminated, truncated, info = python_env.step("_")
        assert "56" in obs["output"]
        assert obs["error"] == ""

    def test_computation_assignment(self, python_env):
        """Test computation assignment shows result"""
        obs, reward, terminated, truncated, info = python_env.step("result = 2 + 3 * 4")
        assert obs["output"] == "14"
        assert obs["error"] == ""

    def test_variable_inspection(self, python_env):
        """Test variable inspection shows variable value"""
        # First assign a variable
        python_env.step("x = 42")
        # Then inspect it
        obs, reward, terminated, truncated, info = python_env.step("x")
        assert "x = 42" in obs["output"]
        assert obs["error"] == ""

    def test_print_statement(self, python_env):
        """Test print statement shows normal output"""
        obs, reward, terminated, truncated, info = python_env.step("print('Hello World')")
        assert "Hello World" in obs["output"]
        assert obs["error"] == ""

    def test_multiline_statements(self, python_env):
        """Test multiline statements work correctly"""
        obs, reward, terminated, truncated, info = python_env.step("a = 5\nprint(a)")
        assert "5" in obs["output"]
        assert obs["error"] == ""

    def test_function_call_assignment(self, python_env):
        """Test function call with assignment"""
        obs, reward, terminated, truncated, info = python_env.step("squared = pow(3, 2)")
        assert obs["output"] == "9"
        assert obs["error"] == ""

    def test_error_handling(self, python_env):
        """Test error handling works correctly"""
        obs, reward, terminated, truncated, info = python_env.step("1/0")
        assert obs["output"] == ""
        assert "ZeroDivisionError" in obs["error"]

    def test_undefined_variable_inspection(self, python_env):
        """Test inspection of undefined variable"""
        obs, reward, terminated, truncated, info = python_env.step("undefined_var")
        assert "not defined" in obs["error"]

    def test_last_result_when_no_previous(self, python_env):
        """Test _ when there's no previous result"""
        obs, reward, terminated, truncated, info = python_env.step("_")
        assert "No previous result available" in obs["output"] or python_env.local_env.get("_") is not None 