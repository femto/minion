# copy from https://github.com/princeton-nlp/intercode which this file doesn't contains in package,weird.
# but we'll need to modify this anyway.

import ast
import logging
import re
import traceback
from typing import Dict, Tuple

import rpyc
from intercode.utils import IntercodeDataLoader
from rich.logging import RichHandler

from .ic_env import ACTION_EXEC, AGENT_OBS, EVAL_OBS, REWARD, IntercodeEnv
from minion.utils.utils import extract_id_and_command

TIMEOUT_DURATION = 10
START_UP_DELAY = 3

# Set up logger
handler = RichHandler(show_time=False)
handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

HOST_PORT = 3006
RESET_KEYWORD = "RESET_CONTAINER_SPECIAL_KEYWORD"


class RpycPythonEnv(IntercodeEnv):
    """LocalPythonEnv for python shell"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.logger = logger

        if "verbose" not in self.kwargs or self.kwargs["verbose"] != True:
            self.logger.disabled = True

        # Load dataset
        self.tool_mode = True
        if "data_path" in self.kwargs:
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

        self.conn = rpyc.connect(kwargs.get("host", "localhost"), kwargs.get("port", kwargs.get("ports", HOST_PORT)))
        self.is_agent = kwargs.get("is_agent", True)
        self.info = {}
        self.trajectory = []

    def exec_action(self, action: str) -> None:
        """
        Executes given action in environment (called by `step` method)
        """
        raise NotImplementedError

    def step(self, action: str) -> None:
        full_id, code = extract_id_and_command(action)
        try:
            if code.strip().startswith("def "):
                if not self.is_agent:  # interactive input multiline
                    function_definition = self.input_multiline_function()
                    code = code + "\n" + function_definition
            else:
                code = self.wrap_with_print(code)
            self.logger.info(f"Command run: {action}")
            self.observation = self.conn.root.execute(f"<id>{full_id}</id>{code}")
            self.info[ACTION_EXEC] = "error" in self.observation and len(self.observation["error"]) > 0
        except Exception as e:
            stack_trace = traceback.format_exc()
            # Return the stack trace in the error response
            self.observation = {"error": f"Error: {str(e)}\nStack trace:\n{stack_trace}"}
            self.info[ACTION_EXEC] = False
        return self.observation, 0.0, False, False, self.info

    def get_reward(self) -> Tuple[float, Dict]:
        MAP_DATASET_TO_REWARD = {
            "ic_apps": self.get_reward_apps,
            "ic_mbpp": self.get_reward_mbpp,
        }
        dataset = self.data_path.split("/")[-1].split(".")[0]
        return MAP_DATASET_TO_REWARD[dataset]()

    def close(self):
        pass

    ############################
    ### MARK: Helper methods ###
    ############################
    def input_multiline_function(self):
        lines = []
        while True:
            line = input(". ")
            if len(line) == 0:
                break
            lines.append(line)
        return "\n".join(lines)

    def wrap_with_print(self, command):
        # Parse the command as an AST (Abstract Syntax Tree)
        parsed_command = ast.parse(command.strip())

        # Check if the command contains an assignment node, print node, or import
        has_assignment = any(isinstance(node, ast.Assign) for node in ast.walk(parsed_command))
        has_print = any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
            for node in ast.walk(parsed_command)
        )
        has_import = any(isinstance(node, ast.Import) for node in ast.walk(parsed_command))
        is_assert = command.strip().startswith("assert")

        # Wrap the command with "print" if it's not an assignment and does not have a "print" statement
        if not any([has_assignment, has_print, has_import, is_assert]):
            return f"print({command})"
        else:
            return command

    ##############################
    ### MARK: Reward functions ###
    ##############################
    def get_reward_apps(self):
        self.info = {}
        return 0.0, self.info

    def get_reward_mbpp(self):
        self.info = {}

        # Get function from `submit` action
        last_action = self.trajectory[-1][0]
        func_name = last_action.split(" ")[1]

        # Get gold function name, assign to submitted function
        func_name_ref = re.search(r"def (\w+)\(", self.gold).group(1)
        self.conn.root.execute(f"{func_name_ref} = {func_name}")

        # Run tests against submitted function
        results_pred = {}
        self.conn.root.execute(self.record["test_setup_code"])
        for test in self.record["tests"]:
            results_pred[test] = self.conn.root.execute(test)

        # Load gold + run tests
        results_gold = {}
        self.conn.root.execute(RESET_KEYWORD)
        self.conn.root.execute(self.record["test_setup_code"])
        self.conn.root.execute(self.gold)
        for test in self.record["tests"]:
            results_gold[test] = self.conn.root.execute(test)

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
