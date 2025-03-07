#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ALFWorld Planner Brain - An advanced brain implementation that can play ALFWorld games with planning.
This brain uses the ALFWorldClient to interact with the ALFWorld environment
and the Brain class from minion to make decisions with planning capabilities.
"""
import asyncio
import os
import random
import json
from typing import Dict, List, Any, Tuple, Optional

from minion import config
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.providers import create_llm_provider

from alfworld_client import ALFWorldClient

class ALFWorldPlannerBrain:
    """
    A brain implementation that can play ALFWorld games with planning capabilities.
    """
    
    def __init__(self, model_name: str = "gpt-4o", port: int = 3007):
        """
        Initialize the ALFWorld Planner Brain.
        
        Args:
            model_name: Name of the language model to use
            port: Port for the Python environment
        """
        self.model_name = model_name
        self.port = port
        self.llm_config = config.models.get(model_name)
        self.llm = create_llm_provider(self.llm_config)
        self.python_env = RpycPythonEnv(port=self.port)
        self.brain = Brain(
            python_env=self.python_env,
            llm=self.llm,
        )
        self.client = ALFWorldClient()
        self.history = []
        self.plan = []
        self.task = ""
        self.current_step = 0
        self.env_type = "AlfredTWEnv"  # Default environment type
        
    async def initialize(self, env_type: Optional[str] = None) -> bool:
        """
        Initialize the ALFWorld environment.
        
        Args:
            env_type: Type of environment to initialize (AlfredTWEnv, AlfredThorEnv, or AlfredHybrid)
            
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        # Set environment type if provided
        if env_type:
            self.env_type = env_type
            
        # Check if server is running
        if not self.client.check_server():
            print("ALFWorld server is not running. Please start the server first.")
            return False
            
        # Initialize environment
        print(f"Initializing ALFWorld environment with type: {self.env_type}...")
        result = self.client.initialize(env_type=self.env_type)
        print(f"Initialization result: {result.get('status', 'unknown')}")
        
        if result.get("status") != "success":
            print("Failed to initialize ALFWorld environment.")
            return False
            
        return True
        
    async def reset(self) -> Dict[str, Any]:
        """
        Reset the environment and extract the task.
        
        Returns:
            Dict: The initial state
        """
        # Reset environment
        print("Resetting environment...")
        reset_result = self.client.reset()
        observation = reset_result.get('observation', 'None')
        admissible_commands = reset_result.get('admissible_commands', [])
        
        # Handle the case where admissible_commands is a list of lists
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]
        
        print(f"Initial observation: {observation}")
        print(f"Admissible commands: {admissible_commands}")
        print()
        
        # Extract the task from the observation
        self.task = ""
        if "Your task is to:" in observation:
            self.task = observation.split("Your task is to:")[1].strip()
            print(f"Extracted task: {self.task}")
        
        # Reset history and plan
        self.history = []
        self.plan = []
        self.current_step = 0
        
        return {
            "observation": observation,
            "admissible_commands": admissible_commands,
            "task": self.task
        }
        
    async def create_plan(self, state: Dict[str, Any]) -> List[str]:
        """
        Create a plan for completing the task.
        
        Args:
            state: The current state of the environment
            
        Returns:
            List[str]: A list of high-level steps to complete the task
        """
        observation = state["observation"]
        task = state["task"] or self.task
        
        # Get admissible commands for context
        admissible_commands = state.get("admissible_commands", [])
        
        # Handle the case where admissible_commands is a list of lists
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]
        
        prompt = f"""
You are an agent in an interactive text environment called ALFWorld. Your goal is to create a plan to complete the task.

Task: {task}

Current observation: {observation}

Available commands: {', '.join(admissible_commands)}

Create a step-by-step plan to complete this task. Each step should be a high-level action.
For example, if the task is "find a mug and put it in the microwave", the plan might be:
1. Look around to identify objects and locations
2. Find the mug
3. Pick up the mug
4. Find the microwave
5. Open the microwave
6. Put the mug in the microwave
7. Close the microwave

Your plan should be specific to the current task and observation. Return ONLY the numbered steps, one per line.
"""
        
        plan_response, score, *_ = await self.brain.step(query=prompt, check=False)
        
        # Extract the plan steps
        plan_steps = []
        for line in plan_response.strip().split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("- ")):
                # Remove the number/bullet and any trailing period
                step = line.split(".", 1)[-1] if "." in line else line
                step = step.split(")", 1)[-1] if ")" in line else step
                step = step.replace("- ", "", 1).strip()
                if step:
                    plan_steps.append(step)
        
        print("Created plan:")
        for i, step in enumerate(plan_steps, 1):
            print(f"{i}. {step}")
        print()
        
        return plan_steps
        
    async def select_action(self, state: Dict[str, Any], plan_step: Optional[str] = None) -> str:
        """
        Select an action based on the current state and plan step.
        
        Args:
            state: The current state of the environment
            plan_step: The current step in the plan
            
        Returns:
            str: The selected action
        """
        observation = state["observation"]
        admissible_commands = state["admissible_commands"]
        task = state["task"] or self.task
        
        # Handle the case where admissible_commands is a list of lists
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]
        
        # Create a history summary for context
        history_summary = "\n".join([
            f"Step {h['step']}: {h['observation']}"
            for h in self.history[-5:]  # Only include the last 5 steps
        ])
        
        # Create a plan summary
        plan_summary = "\n".join([
            f"{i+1}. {step}" + (" (CURRENT STEP)" if i == self.current_step else "")
            for i, step in enumerate(self.plan)
        ])
        
        prompt = f"""
You are an agent in an interactive text environment called ALFWorld. Your goal is to complete the task by taking actions that are available to you.

Task: {task}

Plan:
{plan_summary}

Current plan step: {plan_step or 'No specific step'}

Game History:
{history_summary}

Current observation: {observation}

Available commands:
{', '.join(admissible_commands)}

Think step by step about what action to take next:
1. What objects are mentioned in the observation?
2. What is the current state of the environment?
3. What progress have you made toward the task?
4. How does the current plan step guide your action?
5. Which of the available commands will help you make progress?

Based on your analysis, choose ONE of the available commands that will help accomplish the goal.
Respond with ONLY the exact command you want to execute.
"""
        
        # Ask the brain for the next action
        brain_response, score, *_ = await self.brain.step(query=prompt, check=False)
        
        # Clean up the brain's response to extract just the command
        cleaned_response = brain_response.strip()
        
        # Extract the action from the brain's response
        action = None
        
        # First try to find an exact match
        for cmd in admissible_commands:
            if cmd == cleaned_response:
                action = cmd
                break
        
        # If no exact match, look for the command within the response
        if not action:
            for cmd in admissible_commands:
                if cmd in cleaned_response:
                    action = cmd
                    break
        
        # If still no valid action was found, take a random action
        if not action:
            print("No valid action found in brain response, taking a random action.")
            action = random.choice(admissible_commands)
        
        print(f"Brain's reasoning: {brain_response}")
        print(f"Selected action: {action}")
        
        return action
        
    async def update_plan_progress(self, state: Dict[str, Any]) -> int:
        """
        Update the progress in the plan based on the current state.
        
        Args:
            state: The current state of the environment
            
        Returns:
            int: The index of the next plan step
        """
        if not self.plan:
            return 0
            
        observation = state["observation"]
        task = state["task"] or self.task
        
        # Get admissible commands for context
        admissible_commands = state.get("admissible_commands", [])
        
        # Handle the case where admissible_commands is a list of lists
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]
        
        # Create a history summary
        history_summary = "\n".join([
            f"Step {h['step']}: {h['observation']}" + (f" (Action: {h['action']})" if 'action' in h else "")
            for h in self.history[-10:]  # Include more history for better context
        ])
        
        # Create a plan summary
        plan_summary = "\n".join([
            f"{i+1}. {step}"
            for i, step in enumerate(self.plan)
        ])
        
        prompt = f"""
You are tracking progress through a plan in an ALFWorld environment.

Task: {task}

Plan:
{plan_summary}

Current plan step: {self.current_step + 1}. {self.plan[self.current_step] if self.current_step < len(self.plan) else "N/A"}

Recent game history:
{history_summary}

Current observation: {observation}

Available commands: {', '.join(admissible_commands)}

Based on the current observation and history, has the current plan step been completed? If yes, we should move to the next step.
Answer with ONLY "NEXT" if we should move to the next step, or "STAY" if we should remain at the current step.
"""
        
        progress_response, score, *_ = await self.brain.step(query=prompt, check=False)
        
        # Check if we should move to the next step
        if "NEXT" in progress_response.upper():
            self.current_step = min(self.current_step + 1, len(self.plan) - 1)
            print(f"Moving to plan step {self.current_step + 1}: {self.plan[self.current_step]}")
        else:
            print(f"Staying at plan step {self.current_step + 1}: {self.plan[self.current_step]}")
            
        return self.current_step
        
    async def run(self, custom_task: Optional[str] = None, max_steps: int = 50) -> Dict[str, Any]:
        """
        Run the ALFWorld game with planning.
        
        Args:
            custom_task: A custom task to use instead of the one from the environment
            max_steps: Maximum number of steps to take
            
        Returns:
            Dict: A summary of the game
        """
        # Reset the environment
        initial_state = await self.reset()
        
        # Set custom task if provided
        if custom_task:
            self.task = custom_task
            initial_state["task"] = custom_task
            print(f"Custom task: {custom_task}")
        
        # Create a plan
        self.plan = await self.create_plan(initial_state)
        
        # Game loop
        observation = initial_state["observation"]
        admissible_commands = initial_state["admissible_commands"]
        
        # Handle the case where admissible_commands is a list of lists
        if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
            admissible_commands = admissible_commands[0]
            
        done = False
        total_reward = 0
        step_count = 0
        
        while not done and step_count < max_steps:
            step_count += 1
            print(f"Step {step_count}:")
            
            # Add the current observation to history
            self.history.append({
                "step": step_count,
                "observation": observation,
                "admissible_commands": admissible_commands
            })
            
            # Get the current state
            current_state = {
                "observation": observation,
                "admissible_commands": admissible_commands,
                "task": self.task
            }
            
            # Get the current plan step
            current_plan_step = self.plan[self.current_step] if self.plan and self.current_step < len(self.plan) else None
            
            # Select an action
            action = await self.select_action(current_state, current_plan_step)
            
            # Add the action to history
            self.history[-1]["action"] = action
            
            # Take the action
            response = self.client.step(action)
            
            # Update the state
            observation = response.get('observation', 'None')
            admissible_commands = response.get('admissible_commands', [])
            
            # Handle the case where admissible_commands is a list of lists
            if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
                admissible_commands = admissible_commands[0]
                
            reward = response.get('reward', 0)
            done = response.get('done', False)
            
            total_reward += reward
            
            print(f"Observation: {observation}")
            print(f"Reward: {reward}")
            print(f"Total Reward: {total_reward}")
            print(f"Done: {done}")
            print(f"Admissible commands: {admissible_commands}")
            print()
            
            # Update plan progress if not done
            if not done:
                await self.update_plan_progress({
                    "observation": observation,
                    "admissible_commands": admissible_commands,
                    "task": self.task
                })
            
            # If the task is completed, break out of the loop
            if done:
                print("Task completed!")
                break
        
        print(f"Game finished after {step_count} steps.")
        print(f"Total reward: {total_reward}")
        
        if not done and step_count >= max_steps:
            print("Maximum steps reached without completing the task.")
        
        # Print a summary of the game
        print("\nGame Summary:")
        for h in self.history:
            print(f"Step {h['step']}:")
            print(f"  Observation: {h['observation']}")
            if 'action' in h:
                print(f"  Action: {h['action']}")
            print()
            
        # Return a summary
        return {
            "status": "success" if done else "incomplete",
            "steps": step_count,
            "total_reward": total_reward,
            "task": self.task,
            "plan": self.plan,
            "history": self.history
        }
        
    async def save_results(self, results: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save the results of a game to a file.
        
        Args:
            results: The results to save
            filename: The filename to save to (default: alfworld_results_{timestamp}.json)
            
        Returns:
            str: The path to the saved file
        """
        if filename is None:
            import time
            timestamp = int(time.time())
            filename = f"alfworld_results_{timestamp}.json"
            
        # Create a serializable version of the results
        serializable_results = {
            "status": results.get("status"),
            "steps": results.get("steps"),
            "total_reward": results.get("total_reward"),
            "task": results.get("task"),
            "plan": results.get("plan"),
            "history": [
                {
                    "step": h.get("step"),
                    "observation": h.get("observation"),
                    "action": h.get("action") if "action" in h else None
                }
                for h in results.get("history", [])
            ]
        }
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2)
            
        print(f"Results saved to {filename}")
        return filename

async def run_planner_brain(custom_task: Optional[str] = None, max_steps: int = 50, save_results: bool = True, env_type: str = "AlfredTWEnv"):
    """
    Run the ALFWorld Planner Brain.
    
    Args:
        custom_task: A custom task to use instead of the one from the environment
        max_steps: Maximum number of steps to take
        save_results: Whether to save the results to a file
        env_type: Type of environment to initialize (AlfredTWEnv, AlfredThorEnv, or AlfredHybrid)
    """
    planner_brain = ALFWorldPlannerBrain()
    await planner_brain.initialize(env_type=env_type)
    results = await planner_brain.run(custom_task, max_steps)
    
    if save_results:
        await planner_brain.save_results(results)
        
    return results

if __name__ == "__main__":
    # Example usage:
    custom_task = "find two soapbottle and put them in cabinet"
    asyncio.run(run_planner_brain(custom_task)) 