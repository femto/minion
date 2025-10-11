#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the unified tool decorator that automatically
converts sync functions to BaseTool and async functions to AsyncBaseTool
"""

import asyncio
from minion.tools import tool


@tool
def calculate_area(length: float, width: float) -> float:
    """
    Calculate the area of a rectangle.
    
    Args:
        length: The length of the rectangle
        width: The width of the rectangle
    """
    return length * width


@tool
async def fetch_weather(city: str) -> str:
    """
    Fetch weather information for a city (simulated).
    
    Args:
        city: The name of the city to get weather for
    """
    # Simulate async API call
    await asyncio.sleep(0.1)
    return f"The weather in {city} is sunny with 25°C"


async def main():
    """Demonstrate both sync and async tools"""
    print("=== Tool Decorator Example ===\n")
    
    # Test sync tool
    print("1. Sync Tool (BaseTool):")
    print(f"   Type: {type(calculate_area)}")
    print(f"   Name: {calculate_area.name}")
    print(f"   Description: {calculate_area.description}")
    print(f"   Inputs: {calculate_area.inputs}")
    print(f"   Output type: {calculate_area.output_type}")
    
    result = calculate_area(10.0, 5.0)
    print(f"   Result: calculate_area(10.0, 5.0) = {result}")
    
    print("\n" + "="*50 + "\n")
    
    # Test async tool
    print("2. Async Tool (AsyncBaseTool):")
    print(f"   Type: {type(fetch_weather)}")
    print(f"   Name: {fetch_weather.name}")
    print(f"   Description: {fetch_weather.description}")
    print(f"   Inputs: {fetch_weather.inputs}")
    print(f"   Output type: {fetch_weather.output_type}")
    
    result = await fetch_weather("Tokyo")
    print(f"   Result: await fetch_weather('Tokyo') = {result}")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())