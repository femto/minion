#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ALFWorld Brain - A brain implementation that can play ALFWorld games.
This brain uses the ALFWorldClient to interact with the ALFWorld environment
and the Brain class from minion to make decisions.
"""
import asyncio
import os
import random
from typing import Dict, List, Any, Tuple

from minion import config
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.providers import create_llm_provider

from alfworld_client import ALFWorldClient

async def alfworld_brain(env_type="AlfredTWEnv"):
    """
    Create a brain that can play ALFWorld games.
    This function initializes the ALFWorld client, connects to the server,
    and uses the Brain class to make decisions.
    
    Args:
        env_type: Type of environment to initialize (AlfredTWEnv, AlfredThorEnv, or AlfredHybrid)
    """
    # Initialize the LLM model
    model = "gpt-4o"  # You can change this to any model you have configured
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)

    # Initialize the Python environment
    python_env_config = {"port": 3007}
    python_env = RpycPythonEnv(port=python_env_config.get("port", 3007))

    # Create the brain
    brain = Brain(
        python_env=python_env,
        llm=llm,
    )

    # Initialize the ALFWorld client
    client = ALFWorldClient()

    # Check if server is running
    if not client.check_server():
        print("ALFWorld server is not running. Please start the server first.")
        return

    # Initialize environment
    print(f"Initializing ALFWorld environment with type: {env_type}...")
    result = client.initialize(env_type=env_type)
    print(f"Initialization result: {result.get('status', 'unknown')}")

    # Reset environment
    print("Resetting environment...")
    reset_result = client.reset()
    observation = reset_result.get('observation', 'None')
    admissible_commands = reset_result.get('admissible_commands', [])
    
    # Handle the case where admissible_commands is a list of lists
    if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
        admissible_commands = admissible_commands[0]
    
    print(f"Initial observation: {observation}")
    print(f"Admissible commands: {admissible_commands}")
    print()

    # Extract the task from the observation
    task = ""
    if "Your task is to:" in observation:
        task = observation.split("Your task is to:")[1].strip()
    
    # Game loop
    done = False
    total_reward = 0
    step_count = 0
    history = []  # Keep track of the game history
    
    while not done and step_count < 50:  # Limit to 50 steps to avoid infinite loops
        step_count += 1
        print(f"Step {step_count}:")
        
        # Add the current observation to history
        history.append({
            "step": step_count,
            "observation": observation,
            "admissible_commands": admissible_commands
        })
        
        # Create a history summary for context
        history_summary = "\n".join([
            f"Step {h['step']}: {h['observation']}"
            for h in history[-5:]  # Only include the last 5 steps to avoid context overflow
        ])
        
        # Use the brain to decide what action to take
        prompt = f"""
You are an agent in an interactive text environment called ALFWorld. Your goal is to complete the task by taking actions that are available to you.

Task: {task}

Game History:
{history_summary}

Current observation: {observation}

Available commands:
{', '.join(admissible_commands)}

Think step by step about what action to take next:
1. What objects are mentioned in the observation?
2. What is the current state of the environment?
3. What progress have you made toward the task?
4. What is the next logical step to complete the task?
5. Which of the available commands will help you make progress?

Based on your analysis, choose ONE of the available commands that will help accomplish the goal.
Respond with ONLY the exact command you want to execute.
"""
        
        # Ask the brain for the next action
        brain_response, score, *_ = await brain.step(query=prompt, check=False)
        
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
        
        # Add the action to history
        history[-1]["action"] = action
        
        # Take the action
        response = client.step(action)
        
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
        
        # If the task is completed, break out of the loop
        if done:
            print("Task completed!")
            break
    
    print(f"Game finished after {step_count} steps.")
    print(f"Total reward: {total_reward}")
    
    if not done and step_count >= 50:
        print("Maximum steps reached without completing the task.")
    
    # Print a summary of the game
    print("\nGame Summary:")
    for h in history:
        print(f"Step {h['step']}:")
        print(f"  Observation: {h['observation']}")
        if 'action' in h:
            print(f"  Action: {h['action']}")
        print()

async def run_alfworld_with_custom_task(task_description, env_type="AlfredTWEnv"):
    """
    Run the ALFWorld brain with a custom task description.
    
    Args:
        task_description: A string describing the task to complete
        env_type: Type of environment to initialize (AlfredTWEnv, AlfredThorEnv, or AlfredHybrid)
    """
    # Initialize the LLM model
    model = "gpt-4o"  # You can change this to any model you have configured
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)

    # Initialize the Python environment
    python_env_config = {"port": 3007}
    python_env = RpycPythonEnv(port=python_env_config.get("port", 3007))

    # Create the brain
    brain = Brain(
        python_env=python_env,
        llm=llm,
    )

    # Initialize the ALFWorld client
    client = ALFWorldClient()

    # Check if server is running
    if not client.check_server():
        print("ALFWorld server is not running. Please start the server first.")
        return

    # Initialize environment
    print(f"Initializing ALFWorld environment with type: {env_type}...")
    result = client.initialize(env_type=env_type)
    print(f"Initialization result: {result.get('status', 'unknown')}")

    # Reset environment
    print("Resetting environment...")
    reset_result = client.reset()
    observation = reset_result.get('observation', 'None')
    admissible_commands = reset_result.get('admissible_commands', [])
    
    # Handle the case where admissible_commands is a list of lists
    if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
        admissible_commands = admissible_commands[0]
    
    print(f"Initial observation: {observation}")
    print(f"Admissible commands: {admissible_commands}")
    print()

    # Use the provided task description
    task = task_description
    print(f"Custom task: {task}")
    
    # Game loop
    done = False
    total_reward = 0
    step_count = 0
    history = []  # Keep track of the game history
    
    while not done and step_count < 50:  # Limit to 50 steps to avoid infinite loops
        step_count += 1
        print(f"Step {step_count}:")
        
        # Add the current observation to history
        history.append({
            "step": step_count,
            "observation": observation,
            "admissible_commands": admissible_commands
        })
        
        # Create a history summary for context
        history_summary = "\n".join([
            f"Step {h['step']}: {h['observation']}"
            for h in history[-5:]  # Only include the last 5 steps to avoid context overflow
        ])
        
        # Use the brain to decide what action to take
        prompt = f"""
You are an agent in an interactive text environment called ALFWorld. Your goal is to complete the task by taking actions that are available to you.

Task: {task}

Game History:
{history_summary}

Current observation: {observation}

Available commands:
{', '.join(admissible_commands)}

Think step by step about what action to take next:
1. What objects are mentioned in the observation?
2. What is the current state of the environment?
3. What progress have you made toward the task?
4. What is the next logical step to complete the task?
5. Which of the available commands will help you make progress?

Based on your analysis, choose ONE of the available commands that will help accomplish the goal.
Respond with ONLY the exact command you want to execute.
"""
        
        # Ask the brain for the next action
        brain_response, score, *_ = await brain.step(query=prompt, check=False)
        
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
        
        # Add the action to history
        history[-1]["action"] = action
        
        # Take the action
        response = client.step(action)
        
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
        
        # If the task is completed, break out of the loop
        if done:
            print("Task completed!")
            break
    
    print(f"Game finished after {step_count} steps.")
    print(f"Total reward: {total_reward}")
    
    if not done and step_count >= 50:
        print("Maximum steps reached without completing the task.")
    
    # Print a summary of the game
    print("\nGame Summary:")
    for h in history:
        print(f"Step {h['step']}:")
        print(f"  Observation: {h['observation']}")
        if 'action' in h:
            print(f"  Action: {h['action']}")
        print()

if __name__ == "__main__":
    # Example usage:
    # 1. Run with the default task from the environment
    # asyncio.run(alfworld_brain())
    
    # 2. Run with a custom task
    custom_task = "find two soapbottle and put them in cabinet"
    asyncio.run(run_alfworld_with_custom_task(custom_task)) 