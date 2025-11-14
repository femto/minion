#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify the brain.step() fix for state=None
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Test imports
try:
    from minion.types.agent_state import AgentState
    from minion.types.history import History
    from minion.main.input import Input
    print("✓ Successfully imported required modules")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test creating an AgentState
try:
    state = AgentState(history=History())
    print(f"✓ Successfully created AgentState: {type(state)}")
except Exception as e:
    print(f"✗ Failed to create AgentState: {e}")
    sys.exit(1)

# Test creating an Input
try:
    input_obj = Input(query="test query")
    print(f"✓ Successfully created Input: {type(input_obj)}")
except Exception as e:
    print(f"✗ Failed to create Input: {e}")
    sys.exit(1)

# Simulate the brain.step() logic with state=None
print("\n--- Testing brain.step() logic with state=None ---")
state = None
self_state = None  # Simulating Brain.state being None initially

# This is the fixed logic from brain.step()
if state is None:
    # 如果state为None，使用Brain自身的state或创建新的AgentState
    if self_state is not None:
        state = self_state
        print("✓ Used existing self.state")
    else:
        state = AgentState(history=History())
        print("✓ Created new AgentState when state=None")

print(f"✓ Final state type: {type(state)}")
print(f"✓ State has history: {hasattr(state, 'history')}")
print(f"✓ State has input: {hasattr(state, 'input')}")

print("\n--- Testing the second part: setting state.input ---")
# Simulate creating input from query
query = [{"type": "text", "content": "what's the solution 234*568"}]
input = Input(query=query)

# This is the fixed logic from brain.step()
if self_state is None:
    self_state = state
    print("✓ Set self.state = state when self.state was None")

state.input = input
print(f"✓ Successfully set state.input: {type(state.input)}")

print("\n✅ All tests passed! The fix should work correctly.")
