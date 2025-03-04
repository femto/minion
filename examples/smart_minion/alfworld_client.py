"""
ALFWorld Client - Provides a Python interface to interact with the ALFWorld server.
This client can be used in your Python 3.11 project to communicate with the ALFWorld server
running in a Python 3.9 environment.
"""

import requests
import json
import time
import random
from typing import Dict, List, Tuple, Any, Optional, Union


class ALFWorldClient:
    """Client for interacting with the ALFWorld server."""

    def __init__(self, server_url: str = "http://localhost:5000"):
        """
        Initialize the ALFWorld client.

        Args:
            server_url: URL of the ALFWorld server
        """
        self.server_url = server_url
        self.initialized = False
        self.available_env_types = ["AlfredTWEnv", "AlfredThorEnv", "AlfredHybrid"]
        self.check_server()

    def check_server(self) -> bool:
        """
        Check if the server is running.

        Returns:
            bool: True if the server is running, False otherwise
        """
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            data = response.json()

            if data.get("status") == "success":
                self.initialized = data.get("environment_initialized", False)
                # Update available environment types if provided
                if "available_env_types" in data:
                    self.available_env_types = data.get("available_env_types")
                return True
            return False
        except requests.RequestException:
            return False

    def initialize(self, config_path: str = "configs/base_config.yaml", env_type: str = "AlfredTWEnv") -> Dict[
        str, Any]:
        """
        Initialize the ALFWorld environment.

        Args:
            config_path: Path to the configuration file
            env_type: Type of environment to initialize

        Returns:
            Dict: Response from the server
        """
        # Validate environment type
        if env_type not in self.available_env_types:
            print(f"Warning: Invalid environment type: {env_type}. Using default: {self.available_env_types[0]}")
            env_type = self.available_env_types[0]

        payload = {
            "config_path": config_path,
            "env_type": env_type
        }

        response = requests.post(f"{self.server_url}/initialize", json=payload)
        data = response.json()

        if data.get("status") == "success":
            self.initialized = True

        return data

    def reset(self) -> Dict[str, Any]:
        """
        Reset the environment.

        Returns:
            Dict: Response from the server containing observation, admissible commands, and info
        """
        if not self.initialized:
            raise RuntimeError("Environment not initialized. Call initialize() first.")

        response = requests.post(f"{self.server_url}/reset")
        return response.json()

    def step(self, action: str) -> Dict[str, Any]:
        """
        Take a step in the environment.

        Args:
            action: Action to take

        Returns:
            Dict: Response from the server containing observation, reward, done flag,
                  admissible commands, and info
        """
        if not self.initialized:
            raise RuntimeError("Environment not initialized. Call initialize() first.")

        payload = {"action": action}
        response = requests.post(f"{self.server_url}/step", json=payload)
        return response.json()

    def get_admissible_commands(self) -> List[str]:
        """
        Get the list of admissible commands in the current state.

        Returns:
            List[str]: List of admissible commands
        """
        if not self.initialized:
            raise RuntimeError("Environment not initialized. Call initialize() first.")

        response = requests.get(f"{self.server_url}/get_admissible_commands")
        data = response.json()

        if data.get("status") == "success":
            commands = data.get("admissible_commands", [])
            # Handle nested list format if present
            if commands and isinstance(commands, list) and isinstance(commands[0], list):
                return commands[0]  # Return the first list of commands
            return commands
        return []

    def random_action(self) -> Tuple[str, Dict[str, Any]]:
        """
        Take a random action from the list of admissible commands.

        Returns:
            Tuple[str, Dict]: The action taken and the response from the server
        """
        admissible_commands = self.get_admissible_commands()

        if not admissible_commands:
            raise RuntimeError("No admissible commands available.")

        # If admissible_commands is a list of lists, flatten it
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]

        action = random.choice(admissible_commands)
        response = self.step(action)

        return action, response


def example_usage():
    """Example usage of the ALFWorldClient."""
    client = ALFWorldClient()

    # Check if server is running
    if not client.check_server():
        print("Server is not running. Please start the server first.")
        return

    # Initialize environment
    print("Initializing environment...")
    result = client.initialize()
    print(f"Initialization result: {result.get('status', 'unknown')}")

    # Reset environment
    print("Resetting environment...")
    reset_result = client.reset()
    print(f"Initial observation: {reset_result.get('observation', 'None')}")
    print(f"Admissible commands: {reset_result.get('admissible_commands', [])}")
    print()

    # Take a few random steps
    for i in range(1, 6):
        print(f"Step {i}:")
        action, response = client.random_action()
        print(f"Action: {action}")
        print(f"Observation: {response.get('observation', 'None')}")
        print(f"Reward: {response.get('reward', 'None')}")
        print(f"Done: {response.get('done', 'None')}")
        print(f"Admissible commands: {response.get('admissible_commands', [])}")
        print()


if __name__ == "__main__":
    example_usage()