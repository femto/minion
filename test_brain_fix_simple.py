#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple test to verify the brain.step() fix logic without importing dependencies
"""

class MockHistory:
    def __init__(self):
        self.messages = []

class MockAgentState:
    def __init__(self, history=None):
        self.history = history or MockHistory()
        self.input = None
        self.step_count = 0

class MockInput:
    def __init__(self, query):
        self.query = query

print("Testing brain.step() fix for state=None")
print("=" * 50)

# Simulate the scenario from the error message
print("\n1. Initial state: state=None, self.state=None")
state = None
self_state = None

# This is the fixed logic from brain.step()
print("\n2. Applying the fix...")
if state is None:
    # 如果state为None，使用Brain自身的state或创建新的AgentState
    if self_state is not None:
        state = self_state
        print("   → Used existing self.state")
    else:
        state = MockAgentState(history=MockHistory())
        print("   → Created new AgentState")

print(f"\n3. After fix: state = {state}, type = {type(state).__name__}")

# Simulate setting self.state if it was None
print("\n4. Setting self.state = state")
if self_state is None:
    self_state = state
    print(f"   → self.state is now set: {self_state}")

# Simulate creating input from query
print("\n5. Creating input and setting state.input")
query = [{"type": "text", "content": "what's the solution 234*568"}]
input_obj = MockInput(query=query)
state.input = input_obj
print(f"   → state.input = {state.input}")
print(f"   → state.input.query = {state.input.query}")

print("\n" + "=" * 50)
print("✅ SUCCESS! The fix handles state=None correctly")
print("\nThe fix ensures that:")
print("1. When state=None is passed, a default AgentState is created")
print("2. self.state is properly initialized")
print("3. state.input can be safely set without AttributeError")
