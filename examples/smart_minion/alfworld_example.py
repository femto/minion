#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ALFWorld Example - Example usage of the ALFWorld brain.
This script demonstrates how to use the ALFWorld brain to play ALFWorld games.
"""
import asyncio
import argparse
from alfworld_brain import alfworld_brain, run_alfworld_with_custom_task
from alfworld_planner_brain import run_planner_brain

async def main():
    """
    Main function that parses command line arguments and runs the appropriate function.
    """
    parser = argparse.ArgumentParser(description='Run the ALFWorld brain with various options.')
    parser.add_argument('--task', type=str, help='Custom task to run. If not provided, the default task from the environment will be used.')
    parser.add_argument('--examples', action='store_true', help='Show example tasks and exit.')
    parser.add_argument('--planner', action='store_true', help='Use the planner brain instead of the basic brain.')
    parser.add_argument('--max-steps', type=int, default=50, help='Maximum number of steps to take.')
    parser.add_argument('--save-results', action='store_true', help='Save the results to a file.')
    parser.add_argument('--env-type', type=str, default='AlfredTWEnv', 
                        choices=['AlfredTWEnv', 'AlfredThorEnv', 'AlfredHybrid'],
                        help='Type of environment to use: AlfredTWEnv, AlfredThorEnv, or AlfredHybrid.')
    
    args = parser.parse_args()
    
    if args.examples:
        print("Example tasks:")
        print("  - find two soapbottle and put them in cabinet")
        print("  - put a mug in the microwave")
        print("  - find a knife and put it in the drawer")
        print("  - find an apple and place it in the fridge")
        print("  - clean the toilet with a cloth")
        print("  - heat a pot on the stove")
        return
    
    if args.planner:
        print("Using the planner brain")
        await run_planner_brain(
            custom_task=args.task,
            max_steps=args.max_steps,
            save_results=args.save_results,
            env_type=args.env_type
        )
    else:
        if args.task:
            print(f"Running with custom task: {args.task}")
            await run_alfworld_with_custom_task(args.task, env_type=args.env_type)
        else:
            print("Running with default task from the environment")
            await alfworld_brain(env_type=args.env_type)

if __name__ == "__main__":
    asyncio.run(main()) 