import ast
import logging
import re
import traceback
import subprocess
import sys
import os
from typing import Dict, Tuple, Any, Optional
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from rich.logging import RichHandler

from .ic_env import ACTION_EXEC, AGENT_OBS, EVAL_OBS, REWARD, IntercodeEnv
from minion.utils.utils import extract_id_and_command

# Set up logger
handler = RichHandler(show_time=False)
handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)


class LocalPythonEnv(IntercodeEnv):
    """LocalPythonEnv for executing Python code locally without Docker or rpyc"""

    name = "local_python"

    def __init__(self, **kwargs):
        """
        Initialize the local Python environment.

        Args:
            **kwargs: Additional keyword arguments
                - data_path (str): Path to dataset
                - preprocess (function): Function to apply to environment before each episode
                - traj_dir (str): Directory to save trajectory files to
                - verbose (bool): Whether to print debug messages
                - is_agent (bool): Whether the environment is being used by an agent
        """
        self.kwargs = kwargs
        self.logger = logger

        if "verbose" not in self.kwargs or self.kwargs["verbose"] != True:
            self.logger.disabled = True

        # Load dataset
        self.tool_mode = True
        if "data_path" in self.kwargs:
            from intercode.utils import IntercodeDataLoader
            self.data_path = self.kwargs["data_path"]
            self.data_loader = IntercodeDataLoader(self.data_path)
            self.logger.info(f"Loaded dataset from {self.data_path}")
            self.tool_mode = False
        else:
            self.logger.info("No dataset provided, running in interactive mode")

        # Verify that preprocess function matches specifications
        self.preprocess = None
        if "preprocess" in self.kwargs:
            self.logger.info("Verifying preprocess function...")
            preprocess = self.kwargs["preprocess"]
            assert isinstance(preprocess, type(lambda x: x))
            assert preprocess.__annotations__["return"] == str
            assert "record" in preprocess.__annotations__
            assert preprocess.__annotations__["record"] == Dict
            self.preprocess = preprocess

        # Record logging directory if provided as a keyword argument
        self.traj_dir = None
        if "traj_dir" in self.kwargs and self.kwargs["traj_dir"]:
            self.traj_dir = self.kwargs["traj_dir"]

        self.is_agent = kwargs.get("is_agent", True)
        self.info = {}
        self.trajectory = []
        
        # Initialize the local execution environment
        self.local_env = {}
        self.reset_local_env()
        
        self.logger.info("LocalPythonEnv Initialized")

    def reset_local_env(self) -> None:
        """Reset the local execution environment"""
        self.local_env = {}
        # Add any necessary built-in modules or functions to the environment
        self.local_env.update({
            'print': print,
            '__builtins__': __builtins__,
        })
        # Initialize the last result variable
        self.last_result = None

    def exec_action(self, action: str) -> None:
        """
        Executes given action in environment (called by `step` method)
        """
        try:
            full_id, code = extract_id_and_command(action)
            if code.strip().startswith("def "):
                if not self.is_agent:  # interactive input multiline
                    function_definition = self.input_multiline_function()
                    code = code + "\n" + function_definition
            else:
                code = self.wrap_with_print(code)
                
            self.logger.info(f"Command run: {action}")
            self.observation = self.execute_code(code)
            self.info[ACTION_EXEC] = "error" in self.observation and len(self.observation["error"]) > 0
        except Exception as e:
            stack_trace = traceback.format_exc()
            # Return the stack trace in the error response
            self.observation = {"error": f"Error: {str(e)}\nStack trace:\n{stack_trace}"}
            self.info[ACTION_EXEC] = False

    def step(self, action: str) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """
        Execute the given action in the local Python environment.
        
        Args:
            action (str): The Python code to execute
            
        Returns:
            observation (Dict): The output of the execution
            reward (float): The reward value (always 0.0 in interactive mode)
            terminated (bool): Whether the episode is terminated
            truncated (bool): Whether the episode is truncated
            info (Dict): Additional information
        """
        full_id, code = extract_id_and_command(action)
        try:
            if code.strip().startswith("def "):
                if not self.is_agent:  # interactive input multiline
                    function_definition = self.input_multiline_function()
                    code = code + "\n" + function_definition
            else:
                # Check if this is a variable inspection request
                var_name = self._is_variable_inspection(code)
                if var_name:
                    # This is a request to inspect a variable
                    if var_name in self.local_env:
                        self.observation = {"output": f"{var_name} = {self.local_env[var_name]}\n", "error": ""}
                    else:
                        self.observation = {"output": "", "error": f"Variable '{var_name}' is not defined\n"}
                    self.info[ACTION_EXEC] = False
                    self.trajectory.append((action, self.observation))
                    return self.observation, 0.0, False, False, self.info
                
                code = self.wrap_with_print(code)
                
            self.logger.info(f"Command run: {action}")
            self.observation = self.execute_code(code)
            self.info[ACTION_EXEC] = "error" in self.observation and len(self.observation["error"]) > 0
            
            # Add to trajectory
            self.trajectory.append((action, self.observation))
            
        except Exception as e:
            stack_trace = traceback.format_exc()
            # Return the stack trace in the error response
            self.observation = {"error": f"Error: {str(e)}\nStack trace:\n{stack_trace}"}
            self.info[ACTION_EXEC] = False
            
        return self.observation, 0.0, False, False, self.info

    def execute_code(self, code: str) -> Dict[str, str]:
        """
        Execute Python code in the local environment.
        
        Args:
            code (str): The Python code to execute
            
        Returns:
            Dict[str, str]: A dictionary containing the output and/or error
        """
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        result = {"output": "", "error": "", "result": ""}
        
        try:
            # Check if this is a request for the last result
            if code.strip() == "_":
                if self.last_result is not None:
                    result["output"] = f"{self.last_result}\n"
                else:
                    result["output"] = "No previous result available\n"
                return result
                
            # Try to extract the last assigned variable name before execution
            last_assigned_var = self._extract_last_assigned_var(code)
            
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Try to parse the code to see if it's a single expression that we can evaluate
                try:
                    # Check if the code is a single expression
                    parsed = ast.parse(code.strip())
                    if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Expr):
                        # It's a single expression, we can use eval to get its value
                        expr_value = eval(code, self.local_env)
                        if expr_value is not None:
                            result["result"] = str(expr_value)
                            self.last_result = expr_value
                            # Store the last result in the _ variable
                            self.local_env["_"] = expr_value
                    else:
                        # It's not a single expression, execute it normally
                        exec(code, self.local_env)
                        
                        # Check if it's an assignment that we should capture the value of
                        if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Assign):
                            # Get the variable name being assigned
                            var_name = parsed.body[0].targets[0].id
                            if var_name in self.local_env:
                                result["result"] = str(self.local_env[var_name])
                                self.last_result = self.local_env[var_name]
                                # Store the last result in the _ variable
                                self.local_env["_"] = self.local_env[var_name]
                except SyntaxError:
                    # If parsing fails, just execute the code normally
                    exec(code, self.local_env)
                
            result["output"] = stdout_capture.getvalue()
            result["error"] = stderr_capture.getvalue()
            
            # If there was no output but we have a result, add it to the output
            if not result["output"].strip() and result["result"]:
                result["output"] = result["result"] + "\n"
            
            # If we identified a variable assignment and there's no output, show the variable value
            if last_assigned_var and not result["output"].strip() and last_assigned_var in self.local_env:
                result["output"] = f"{last_assigned_var} = {self.local_env[last_assigned_var]}\n"
                
        except Exception as e:
            result["error"] = f"{str(e)}\n{traceback.format_exc()}"
            
        return result

    def get_reward(self) -> Tuple[float, Dict]:
        """
        Get reward value at current step of environment
        
        Returns:
            reward (float): The reward value
            info (Dict): Additional information
        """
        MAP_DATASET_TO_REWARD = {
            "ic_apps": self.get_reward_apps,
            "ic_mbpp": self.get_reward_mbpp,
        }
        dataset = self.data_path.split("/")[-1].split(".")[0]
        return MAP_DATASET_TO_REWARD[dataset]()

    def close(self):
        """Clean up resources"""
        pass

    ############################
    ### MARK: Helper methods ###
    ############################
    def input_multiline_function(self):
        """
        Handle multiline function input for interactive mode
        
        Returns:
            str: The multiline function definition
        """
        lines = []
        while True:
            line = input(". ")
            if len(line) == 0:
                break
            lines.append(line)
        return "\n".join(lines)

    def wrap_with_print(self, command):
        """
        Wrap expressions with print() if they don't already have side effects
        
        Args:
            command (str): The command to potentially wrap with print()
            
        Returns:
            str: The command, possibly wrapped with print()
        """
        try:
            # Parse the command as an AST (Abstract Syntax Tree)
            parsed_command = ast.parse(command.strip())

            # Check if the command contains an assignment node, print node, or import
            has_assignment = any(isinstance(node, ast.Assign) for node in ast.walk(parsed_command))
            has_print = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
                for node in ast.walk(parsed_command)
            )
            has_import = any(isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom) for node in ast.walk(parsed_command))
            is_assert = command.strip().startswith("assert")

            # Wrap the command with "print" if it's not an assignment and does not have a "print" statement
            if not any([has_assignment, has_print, has_import, is_assert]):
                return f"print({command})"
            else:
                return command
        except SyntaxError:
            # If there's a syntax error, don't modify the command
            return command

    def _is_variable_inspection(self, code: str) -> Optional[str]:
        """
        Check if the code is a request to inspect a variable.
        
        Args:
            code (str): The code to check
            
        Returns:
            Optional[str]: The variable name if this is a variable inspection request, None otherwise
        """
        # Check if the code is just a variable name
        code = code.strip()
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', code):
            return code
        return None

    def _extract_last_assigned_var(self, code: str) -> Optional[str]:
        """
        Extract the name of the last variable being assigned in the code.
        
        Args:
            code (str): The code to analyze
            
        Returns:
            Optional[str]: The name of the last assigned variable, or None if no assignment is found
        """
        try:
            parsed = ast.parse(code.strip())
            # Find the last assignment statement
            last_assign = None
            for node in parsed.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    # Simple assignment like 'x = 5'
                    if isinstance(node.targets[0], ast.Name):
                        last_assign = node.targets[0].id
            return last_assign
        except SyntaxError:
            return None

    ##############################
    ### MARK: Reward functions ###
    ##############################
    def get_reward_apps(self):
        """
        Get reward for apps dataset
        
        Returns:
            float: The reward value
            Dict: Additional information
        """
        self.info = {}
        return 0.0, self.info

    def get_reward_mbpp(self):
        """
        Get reward for MBPP dataset
        
        Returns:
            float: The reward value
            Dict: Additional information
        """
        self.info = {}

        # Get function from `submit` action
        last_action = self.trajectory[-1][0]
        func_name = last_action.split(" ")[1]

        # Get gold function name, assign to submitted function
        func_name_ref = re.search(r"def (\w+)\(", self.gold).group(1)
        self.execute_code(f"{func_name_ref} = {func_name}")

        # Run tests against submitted function
        results_pred = {}
        self.execute_code(self.record["test_setup_code"])
        for test in self.record["tests"]:
            results_pred[test] = self.execute_code(test)

        # Load gold + run tests
        results_gold = {}
        self.reset_local_env()
        self.execute_code(self.record["test_setup_code"])
        self.execute_code(self.gold)
        for test in self.record["tests"]:
            results_gold[test] = self.execute_code(test)

        self.info["submitted_function"] = func_name
        self.info[AGENT_OBS] = results_pred
        self.info[EVAL_OBS] = results_gold

        # Compute reward
        correct = 0
        for test, output in results_pred.items():
            output_gold = results_gold[test]
            if output == output_gold:
                correct += 1
        self.info[REWARD] = float(correct) / len(results_pred)
        self.reward = self.info[REWARD]

        self.logger.info(f"Info: {self.info}")
        self.logger.info(f"Reward: {self.reward}")
        return self.reward, self.info 