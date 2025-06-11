#!/usr/bin/env python3
"""
Novel Writing Demo with TuringMachineAgent

This demo shows how the TuringMachineAgent can handle large-scale creative writing tasks
using the TextGenerationTool to break down and execute complex storytelling projects.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import minion
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.agents.turing_machine_agent import create_turing_machine_agent
from minion.tools.text_generation_tool import TextGenerationTool
from minion.tools.default_tools import DuckDuckGoSearchTool, PythonInterpreterTool
from minion.tools.base_tool import BaseTool


class CalculatorTool(BaseTool):
    """Simple calculator tool for word count and planning calculations"""
    name = "calculator"
    description = "Perform mathematical calculations for planning and analysis"
    inputs = {
        "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
    }
    output_type = "string"
    
    def forward(self, expression: str) -> str:
        try:
            # Safe evaluation of mathematical expressions
            import ast
            import operator
            
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }
            
            def eval_expr(node):
                if isinstance(node, ast.Num):
                    return node.n
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                elif isinstance(node, ast.UnaryOp):
                    return operators[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(f"Unsupported type {type(node)}")
            
            tree = ast.parse(expression, mode='eval')
            result = eval_expr(tree.body)
            return f"Result: {result}"
            
        except Exception as e:
            return f"Error calculating '{expression}': {str(e)}"


async def demo_short_story():
    """Demo writing a short story to test the text generation capabilities"""
    print("=" * 70)
    print("📚 Short Story Writing Demo")
    print("=" * 70)
    
    # Create agent with text generation capabilities
    agent = create_turing_machine_agent(name="short_story_agent")
    agent.add_tool(TextGenerationTool())
    agent.add_tool(CalculatorTool())
    
    print(f"🛠️  Available tools: {[tool.name for tool in agent.tools]}")
    
    # Short story task
    task = "Write a compelling short story (about 1000 words) about a time traveler who accidentally changes history by saving a butterfly. Be creative and include dialogue, character development, and a surprising twist."
    
    print(f"\n📖 Task: {task}")
    print("-" * 70)
    
    step_count = 0
    final_response = None
    
    async for result in agent.run(task, max_steps=15, streaming=True, debug=False):
        step_count += 1
        response, score, terminated, truncated, info = result
        
        print(f"\n📝 Step {step_count}: {info.get('state', 'unknown').upper()}")
        if len(str(response)) > 200:
            print(f"   Response: {str(response)[:200]}...")
        else:
            print(f"   Response: {response}")
        
        final_response = response
        if terminated:
            print("✅ Short story completed!")
            break
    
    print(f"\n📊 Summary: Completed in {step_count} steps")
    return final_response


async def demo_novel_writing():
    """Demo writing a full novel using TuringMachineAgent"""
    print("=" * 70)
    print("📖 Novel Writing Demo - 'Reborn in Skyrim'")
    print("=" * 70)
    
    # Create agent with comprehensive tools for novel writing
    agent = create_turing_machine_agent(name="novel_writer_agent")
    agent.add_tool(TextGenerationTool())
    agent.add_tool(CalculatorTool())
    agent.add_tool(DuckDuckGoSearchTool())  # For research if needed
    agent.add_tool(PythonInterpreterTool())  # For text analysis/processing
    
    print(f"🛠️  Available tools: {[tool.name for tool in agent.tools]}")
    
    # Large-scale novel writing task
    task = """Write a 500,000 characters novel named 'Reborn in Skyrim'. 

The story should follow a modern person who dies and is reborn in the world of Skyrim (The Elder Scrolls). 
Fill the story with creative details, character development, world-building, and adventure. 

Key requirements:
- Target: 500,000 characters (approximately 80,000-100,000 words)
- Genre: Fantasy/Isekai adventure
- Include dialogue, action scenes, character growth
- Divide into chapters for better organization
- Be creative with your own ideas and interpretations!

Since this novel is very long, break it into manageable subtasks and work systematically."""
    
    print(f"\n📚 Task: Writing 'Reborn in Skyrim' Novel")
    print(f"🎯 Target: 500,000 characters (~80,000-100,000 words)")
    print(f"📝 Genre: Fantasy/Isekai Adventure")
    print("-" * 70)
    
    # Track progress
    step_count = 0
    max_steps = 100  # Allow many steps for large project
    final_response = None
    word_count_estimates = []
    
    print("🚀 Starting novel writing process...")
    print("📊 Progress will be shown for each major step")
    
    try:
        async for result in agent.run(task, max_steps=max_steps, streaming=True, debug=True):
            step_count += 1
            response, score, terminated, truncated, info = result
            
            # Show condensed progress for large outputs
            if step_count % 5 == 1 or terminated:  # Show every 5th step or final
                print(f"\n🔄 Step {step_count}: {info.get('state', 'unknown').upper()}")
                
                # Estimate content length
                if response and len(str(response)) > 100:
                    char_count = len(str(response))
                    word_estimate = char_count // 5  # Rough estimate: 5 chars per word
                    word_count_estimates.append(word_estimate)
                    
                    print(f"   📏 Content length: ~{char_count:,} characters (~{word_estimate:,} words)")
                    print(f"   📄 Preview: {str(response)[:150]}...")
                else:
                    print(f"   📝 Planning/Setup: {response}")
                
                print(f"   🎯 Confidence: {score:.2f}")
                
            final_response = response
            if terminated:
                print("\n🎉 Novel writing completed!")
                break
                
            if step_count >= max_steps:
                print(f"\n⏰ Reached maximum steps ({max_steps}). Consider continuing with a new session.")
                break
                
    except KeyboardInterrupt:
        print("\n⏸️  Novel writing interrupted by user.")
    except Exception as e:
        print(f"\n❌ Error during novel writing: {e}")
        import traceback
        traceback.print_exc()
    
    # Final summary
    total_estimated_words = sum(word_count_estimates)
    target_words = 80000  # Conservative estimate for 500k characters
    completion_percentage = min(100, (total_estimated_words / target_words) * 100)
    
    print("\n" + "=" * 70)
    print("📊 NOVEL WRITING SUMMARY")
    print("=" * 70)
    print(f"📖 Novel: 'Reborn in Skyrim'")
    print(f"🔢 Total steps: {step_count}")
    print(f"📏 Estimated words generated: ~{total_estimated_words:,}")
    print(f"🎯 Target completion: {completion_percentage:.1f}%")
    print(f"✅ Status: {'Completed' if terminated else 'Partial/In Progress'}")
    
    if completion_percentage < 100:
        print(f"\n💡 To continue: Run the agent again or increase max_steps")
        print(f"📈 Progress: Generated ~{completion_percentage:.1f}% of target content")
    
    return final_response


async def demo_interactive_novel_planning():
    """Demo novel planning and outlining"""
    print("=" * 70)
    print("📋 Interactive Novel Planning Demo")
    print("=" * 70)
    
    agent = create_turing_machine_agent(name="novel_planner_agent")
    agent.add_tool(TextGenerationTool())
    agent.add_tool(CalculatorTool())
    
    # Planning task
    task = """Create a detailed outline and planning document for the novel 'Reborn in Skyrim'.

Include:
1. Main character background and development arc
2. Chapter-by-chapter outline (at least 20 chapters)
3. Key plot points and story beats
4. Character relationships and supporting cast
5. World-building elements specific to Skyrim
6. Major conflicts and resolutions
7. Estimated word count distribution per chapter

Make this a comprehensive planning document that could guide the actual writing process."""
    
    print(f"📋 Task: Novel Planning & Outlining")
    print("-" * 70)
    
    step_count = 0
    async for result in agent.run(task, max_steps=20, streaming=True, debug=False):
        step_count += 1
        response, score, terminated, truncated, info = result
        
        print(f"\n📝 Planning Step {step_count}:")
        if len(str(response)) > 300:
            print(f"   Generated: {str(response)[:300]}...")
        else:
            print(f"   Output: {response}")
            
        if terminated:
            print("✅ Novel planning completed!")
            break
    
    print(f"\n📊 Planning completed in {step_count} steps")


async def main():
    """Run novel writing demonstrations"""
    print("🎭 TuringMachineAgent Novel Writing Demonstrations")
    print("=" * 80)
    
    demos = [
        ("Short Story Demo", demo_short_story),
        ("Novel Planning Demo", demo_interactive_novel_planning),
        ("Full Novel Writing Demo", demo_novel_writing),
    ]
    
    print("\nAvailable demos:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    
    # For automated demo, run the planning first, then short story
    print(f"\n🚀 Running automated demo sequence...")
    
    try:
        # Start with short story to test the system
        print(f"\n{'='*20} Running Short Story Demo {'='*20}")
        await demo_short_story()
        
        # Then do novel planning
        print(f"\n{'='*20} Running Novel Planning Demo {'='*20}")
        await demo_interactive_novel_planning()
        
        # Ask user if they want to run the full novel demo
        print(f"\n{'='*20} Full Novel Demo Available {'='*20}")
        print("📚 The full novel writing demo is available but may take a long time.")
        print("💡 To run it manually, call: await demo_novel_writing()")
        print("⚠️  It may generate many steps and substantial content.")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎭 Novel writing demos completed!")
    print("💡 You can now use these patterns for your own creative writing projects!")


if __name__ == "__main__":
    asyncio.run(main()) 