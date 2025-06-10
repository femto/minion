"""
Turing Machine Agent Demo Script

This script demonstrates various ways to use the TuringMachineAgent
including basic usage, step-by-step execution, and integration with BaseAgent.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import minion
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.agents.turing_machine_agent import (
    AgentTuringMachine, 
    AgentInput, 
    Memory, 
    Plan, 
    AgentState,
    create_turing_machine_agent
)
from minion.agents.base_agent import Input


async def demo_basic_usage():
    """Demo basic usage of TuringMachineAgent"""
    print("=" * 60)
    print("Basic TuringMachineAgent Demo")
    print("=" * 60)
    
    # Create agent using default LLM configuration
    agent = create_turing_machine_agent(name="demo_agent")
    
    # Simple task using BaseAgent interface
    task = "Help me plan a weekend trip to San Francisco. I'm interested in technology museums and good food."
    
    print(f"Task: {task}")
    print("-" * 60)
    
    # Run the task
    result = await agent.run(task, max_steps=5, streaming=False)
    
    print(f"Result: {result}")
    print("-" * 60)


async def demo_step_by_step():
    """Demo step-by-step execution with detailed monitoring"""
    print("=" * 60) 
    print("Step-by-Step Turing Machine Demo")
    print("=" * 60)
    
    # Create agent with specific model (if available in config)
    try:
        agent = create_turing_machine_agent(
            model_name="gpt-4o-mini",  # or any model name from your config
            name="step_agent"
        )
    except:
        # Fallback to default if model not found
        agent = create_turing_machine_agent(name="step_agent")
    
    # Create detailed task setup
    goal = "Create a simple Python function that calculates the Fibonacci sequence"
    
    # Initialize memory with some context
    memory = Memory()
    memory.update_working("task_type", "programming")
    memory.update_working("language", "python") 
    memory.update_semantic("user_expertise", "intermediate")
    
    # Create detailed plan
    plan = Plan(goal=goal)
    plan.add_step("analyze_requirements", {"language": "python", "algorithm": "fibonacci"})
    plan.add_step("design_function", {"approach": "iterative_or_recursive"})
    plan.add_step("implement_code", {"include_docstring": True})
    plan.add_step("add_error_handling", {})
    plan.add_step("test_function", {"test_cases": [0, 1, 5, 10]})
    plan.add_step("finalize_result", {})
    
    # Create agent input
    agent_input = AgentInput(
        goal=goal,
        plan=plan,
        memory=memory,
        prompt="Please create a well-documented Python function for calculating Fibonacci numbers with proper error handling.",
        context={"programming_language": "python", "style": "clean_code"}
    )
    
    print(f"Goal: {goal}")
    print(f"Initial Plan Steps: {len(plan.steps)}")
    print("-" * 60)
    
    # Execute steps one by one
    outputs = []
    max_steps = 8
    
    for i in range(max_steps):
        if agent.turing_machine.current_state == AgentState.HALTED:
            print("Agent reached HALTED state")
            break
            
        print(f"\n--- Step {i+1} ---")
        print(f"Current State: {agent.turing_machine.current_state.value}")
        print(f"Current Plan Step: {agent_input.plan.current_step + 1}/{len(agent_input.plan.steps)}")
        
        current_step = agent_input.plan.get_current_step()
        if current_step:
            print(f"Current Action: {current_step['action']}")
        
        # Execute one step
        output = await agent.turing_machine.step(agent_input, debug=False)
        outputs.append(output)
        
        print(f"Next Instruction: {output.next_instruction}")
        print(f"Result: {output.current_result}")
        print(f"Confidence: {output.confidence:.2f}")
        print(f"Next State: {output.next_state.value}")
        print(f"Reasoning: {output.reasoning}")
        
        if output.halt_condition:
            print("Halt condition reached")
            break
    
    print("\n" + "=" * 60)
    print("Execution Summary")
    print("=" * 60)
    print(f"Total steps executed: {len(outputs)}")
    print(f"Final state: {agent.turing_machine.current_state.value}")
    print(f"Working memory: {agent_input.memory.working_memory}")
    print(f"Episodes count: {len(agent_input.memory.episodic_memory)}")


async def demo_integrated_with_base_agent():
    """Demo using TuringMachineAgent through BaseAgent interface"""
    print("=" * 60)
    print("BaseAgent Interface Demo")
    print("=" * 60)
    
    agent = create_turing_machine_agent(name="base_interface_agent")
    
    # Use the BaseAgent interface for simpler interaction
    task_input = Input(query="Explain the concept of machine learning in simple terms and provide a basic example")
    
    print(f"Task: {task_input.query}")
    print("-" * 60)
    
    # Execute single step
    response, score, terminated, truncated, info = await agent.step(task_input, debug=True)
    
    print(f"Response: {response}")
    print(f"Score: {score}")
    print(f"Terminated: {terminated}")
    print(f"Info: {info}")
    
    # If not terminated, you could continue with more steps
    if not terminated:
        print("\nContinuing with additional steps...")
        response2, score2, terminated2, truncated2, info2 = await agent.step(task_input, debug=True)
        print(f"Second Response: {response2}")
        print(f"Second Score: {score2}")
        print(f"Second Terminated: {terminated2}")


async def demo_custom_llm_config():
    """Demo using different LLM configurations"""
    print("=" * 60)
    print("Custom LLM Configuration Demo")
    print("=" * 60)
    
    # This would use different models if they're configured in your config.yaml
    model_names = ["default", "gpt-4o-mini"]  # Adjust based on your actual config
    
    for model_name in model_names:
        try:
            print(f"\nTesting with model: {model_name}")
            print("-" * 40)
            
            if model_name == "default":
                agent = create_turing_machine_agent()
            else:
                agent = create_turing_machine_agent(model_name=model_name)
            
            task = "What are the three most important principles of good software design?"
            result = await agent.run(task, max_steps=3)
            
            print(f"Model: {model_name}")
            print(f"Result: {result}")
            
        except Exception as e:
            print(f"Error with model {model_name}: {e}")


async def main():
    """Run all demos"""
    print("Turing Machine Agent Demonstrations")
    print("=" * 80)
    
    demos = [
        ("Basic Usage", demo_basic_usage),
        ("Step-by-Step Execution", demo_step_by_step),
        ("BaseAgent Interface", demo_integrated_with_base_agent),
        ("Custom LLM Config", demo_custom_llm_config),
    ]
    
    for demo_name, demo_func in demos:
        try:
            print(f"\n\n{'='*20} {demo_name} {'='*20}")
            await demo_func()
            print(f"{'='*20} {demo_name} Complete {'='*20}")
        except Exception as e:
            print(f"Error in {demo_name}: {e}")
            import traceback
            traceback.print_exc()
        
        # Pause between demos
        print("\n" + "."*60)
        await asyncio.sleep(1)
    
    print("\n\nAll demos completed!")


if __name__ == "__main__":
    asyncio.run(main()) 