#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Programmatic Tool Calling (PTC) Example

This example demonstrates the PTC pattern from Anthropic's "Advanced Tool Use" article:
https://www.anthropic.com/engineering/advanced-tool-use

PTC allows Claude to orchestrate tools through code rather than through individual API
round-trips. Instead of Claude requesting tools one at a time with each result being
returned to its context, Claude writes code that calls multiple tools, processes their
outputs, and controls what information actually enters its context window.

Key benefits of PTC:
1. Token savings: Intermediate results stay out of Claude's context
2. Reduced latency: Multiple tool calls in a single code block eliminate inference passes
3. Improved accuracy: Explicit orchestration logic in code is more reliable than
   natural language tool invocations

In minion, CodeAgent implements the PTC pattern by:
- Using Python code for reasoning and tool calling
- Executing code in a sandboxed environment
- Only returning final results to the model's context
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion import config
from minion.agents import CodeAgent
from minion.main.brain import Brain
from minion.providers import create_llm_provider
from minion.tools.base_tool import BaseTool


# =============================================================================
# Custom Tools for PTC Demo
# =============================================================================

class GetTeamMembersTool(BaseTool):
    """Tool to get team members of a department."""

    name: str = "get_team_members"
    description: str = """Get all members of a department.

    Args:
        department: The department name (e.g., "engineering", "sales", "marketing")

    Returns:
        List of team member objects with id, name, and level fields.
    """

    def forward(self, department: str) -> list:
        """Simulate fetching team members from a database."""
        # Simulated data - in production this would call an actual API/database
        teams = {
            "engineering": [
                {"id": "EMP-001", "name": "Alice Chen", "level": "senior"},
                {"id": "EMP-002", "name": "Bob Smith", "level": "junior"},
                {"id": "EMP-003", "name": "Carol White", "level": "senior"},
                {"id": "EMP-004", "name": "David Brown", "level": "lead"},
                {"id": "EMP-005", "name": "Eve Johnson", "level": "junior"},
            ],
            "sales": [
                {"id": "EMP-101", "name": "Frank Lee", "level": "senior"},
                {"id": "EMP-102", "name": "Grace Kim", "level": "junior"},
                {"id": "EMP-103", "name": "Henry Wang", "level": "lead"},
            ],
            "marketing": [
                {"id": "EMP-201", "name": "Ivy Zhang", "level": "senior"},
                {"id": "EMP-202", "name": "Jack Liu", "level": "junior"},
            ],
        }
        return teams.get(department.lower(), [])


class GetExpensesTool(BaseTool):
    """Tool to get expenses for a user in a specific quarter."""

    name: str = "get_expenses"
    description: str = """Get expense records for a user in a specific quarter.

    Args:
        user_id: The employee ID (e.g., "EMP-001")
        quarter: The quarter (e.g., "Q1", "Q2", "Q3", "Q4")

    Returns:
        List of expense objects with category, amount, and description fields.
    """

    def forward(self, user_id: str, quarter: str) -> list:
        """Simulate fetching expenses from a database."""
        import random
        random.seed(hash(user_id + quarter))  # Consistent results for same input

        categories = ["travel", "equipment", "meals", "software", "training"]
        expenses = []

        # Generate 5-15 expense items per person
        num_expenses = random.randint(5, 15)
        for _ in range(num_expenses):
            category = random.choice(categories)
            # Travel tends to be more expensive
            if category == "travel":
                amount = random.randint(500, 3000)
            elif category == "equipment":
                amount = random.randint(100, 1500)
            else:
                amount = random.randint(20, 300)

            expenses.append({
                "category": category,
                "amount": amount,
                "description": f"{category.title()} expense"
            })

        return expenses


class GetBudgetByLevelTool(BaseTool):
    """Tool to get budget limits for an employee level."""

    name: str = "get_budget_by_level"
    description: str = """Get budget limits for a specific employee level.

    Args:
        level: The employee level (e.g., "junior", "senior", "lead")

    Returns:
        Budget object with travel_limit, equipment_limit, and total_limit fields.
    """

    def forward(self, level: str) -> dict:
        """Return budget limits based on employee level."""
        budgets = {
            "junior": {
                "travel_limit": 2000,
                "equipment_limit": 1000,
                "total_limit": 5000
            },
            "senior": {
                "travel_limit": 5000,
                "equipment_limit": 2500,
                "total_limit": 10000
            },
            "lead": {
                "travel_limit": 8000,
                "equipment_limit": 4000,
                "total_limit": 15000
            },
        }
        return budgets.get(level.lower(), budgets["junior"])


class SearchProductsTool(BaseTool):
    """Tool to search for products in a catalog."""

    name: str = "search_products"
    description: str = """Search for products in the catalog.

    Args:
        query: Search query string
        category: Optional category filter
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of product objects with id, name, price, category, and stock fields.
    """

    def forward(self, query: str, category: str = None, max_results: int = 10) -> list:
        """Simulate product search."""
        # Simulated product catalog
        all_products = [
            {"id": "P001", "name": "Laptop Pro 15", "price": 1299.99, "category": "electronics", "stock": 50},
            {"id": "P002", "name": "Wireless Mouse", "price": 29.99, "category": "electronics", "stock": 200},
            {"id": "P003", "name": "USB-C Hub", "price": 49.99, "category": "electronics", "stock": 150},
            {"id": "P004", "name": "Standing Desk", "price": 599.99, "category": "furniture", "stock": 30},
            {"id": "P005", "name": "Ergonomic Chair", "price": 449.99, "category": "furniture", "stock": 45},
            {"id": "P006", "name": "Monitor 27inch", "price": 399.99, "category": "electronics", "stock": 75},
            {"id": "P007", "name": "Keyboard Mechanical", "price": 149.99, "category": "electronics", "stock": 100},
            {"id": "P008", "name": "Desk Lamp LED", "price": 79.99, "category": "furniture", "stock": 120},
            {"id": "P009", "name": "Webcam HD", "price": 89.99, "category": "electronics", "stock": 80},
            {"id": "P010", "name": "Headphones Noise Cancel", "price": 299.99, "category": "electronics", "stock": 60},
        ]

        # Filter by query
        results = []
        query_lower = query.lower()
        for product in all_products:
            if query_lower in product["name"].lower() or query_lower in product["category"].lower():
                if category is None or product["category"] == category.lower():
                    results.append(product)

        return results[:max_results]


class GetInventoryStatusTool(BaseTool):
    """Tool to get detailed inventory status for a product."""

    name: str = "get_inventory_status"
    description: str = """Get detailed inventory status for a product.

    Args:
        product_id: The product ID (e.g., "P001")

    Returns:
        Inventory object with stock, reserved, available, and warehouse_location fields.
    """

    def forward(self, product_id: str) -> dict:
        """Simulate inventory lookup."""
        import random
        random.seed(hash(product_id))

        stock = random.randint(20, 200)
        reserved = random.randint(0, stock // 3)

        return {
            "product_id": product_id,
            "stock": stock,
            "reserved": reserved,
            "available": stock - reserved,
            "warehouse_location": f"WH-{random.randint(1, 5)}-{random.choice(['A', 'B', 'C'])}{random.randint(1, 20)}"
        }


# =============================================================================
# PTC Example Functions
# =============================================================================

async def budget_compliance_example():
    """
    Example 1: Budget Compliance Check (from Anthropic's article)

    This demonstrates the PTC pattern where Claude writes code to:
    1. Fetch team members
    2. Get expenses for each member in parallel
    3. Get budget limits by level
    4. Compare and find who exceeded budget

    Without PTC: 20+ tool calls, each returning to Claude's context (50KB+ data)
    With PTC: Claude writes code, processes data internally, returns only summary (~1KB)
    """
    print("\n" + "=" * 60)
    print("Example 1: Budget Compliance Check (PTC Pattern)")
    print("=" * 60)

    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create CodeAgent with budget-related tools using .create() method
    agent = await CodeAgent.create(
        brain=brain,
        tools=[GetTeamMembersTool(), GetExpensesTool(), GetBudgetByLevelTool()]
    )

    # The task - this is what triggers PTC pattern
    task = """
    Find which engineering team members exceeded their Q3 travel budget.

    Steps to follow:
    1. Get all engineering team members using get_team_members("engineering")
    2. For each team member, get their Q3 expenses using get_expenses(user_id, "Q3")
    3. Get the budget limits for each employee level using get_budget_by_level(level)
    4. Calculate total travel expenses for each person
    5. Compare against their travel budget limit
    6. Return a list of people who exceeded their budget with their name, spent amount, and limit

    Use Python code to orchestrate these tool calls efficiently.
    """

    print(f"\nTask: {task}")
    print("\nExecuting with PTC (Code-based tool orchestration)...")

    try:
        result = await agent.run_async(task)
        print(f"\nResult (only summary returned to context):\n{result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def inventory_analysis_example():
    """
    Example 2: Inventory Analysis

    Demonstrates PTC for processing large datasets:
    - Search products across categories
    - Get inventory status for each product
    - Aggregate and analyze data in code
    - Return only actionable insights
    """
    print("\n" + "=" * 60)
    print("Example 2: Inventory Analysis (PTC Pattern)")
    print("=" * 60)

    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create CodeAgent with inventory tools using .create() method
    agent = await CodeAgent.create(
        brain=brain,
        tools=[SearchProductsTool(), GetInventoryStatusTool()]
    )

    task = """
    Analyze the electronics inventory and identify products that need restocking.

    Steps:
    1. Search for all electronics products using search_products("electronics")
    2. For each product, get detailed inventory status using get_inventory_status(product_id)
    3. Identify products where available stock is less than 50 units
    4. Calculate the total value of low-stock items (price * available)
    5. Return a summary with:
       - List of products needing restock (name, available, price)
       - Total count of low-stock items
       - Total value at risk

    Use code to process this efficiently without flooding the context with raw data.
    """

    print(f"\nTask: {task}")
    print("\nExecuting with PTC...")

    try:
        result = await agent.run_async(task)
        print(f"\nResult:\n{result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def data_aggregation_example():
    """
    Example 3: Multi-Department Budget Summary

    Shows PTC handling complex aggregation across multiple data sources:
    - Fetch data from multiple departments
    - Aggregate by category
    - Compute statistics
    - Return condensed report
    """
    print("\n" + "=" * 60)
    print("Example 3: Multi-Department Budget Summary (PTC Pattern)")
    print("=" * 60)

    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create CodeAgent using .create() method
    agent = await CodeAgent.create(
        brain=brain,
        tools=[GetTeamMembersTool(), GetExpensesTool(), GetBudgetByLevelTool()]
    )

    task = """
    Create a Q3 expense summary across all departments (engineering, sales, marketing).

    For each department:
    1. Get all team members
    2. Get Q3 expenses for each member
    3. Aggregate expenses by category (travel, equipment, meals, software, training)

    Final report should include:
    - Total expenses per department
    - Top spending category per department
    - Overall company total
    - Department with highest spending

    Write Python code to efficiently gather and process this data.
    The code should minimize what gets returned to context - only the final summary.
    """

    print(f"\nTask: {task}")
    print("\nExecuting with PTC...")

    try:
        result = await agent.run_async(task)
        print(f"\nResult:\n{result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def simple_ptc_demo():
    """
    Example 4: Simple PTC Demo

    A simpler example showing basic PTC workflow with math calculation tools.
    """
    print("\n" + "=" * 60)
    print("Example 4: Simple PTC Demo - Fibonacci with Code")
    print("=" * 60)

    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)

    # Create CodeAgent using .create() method (no extra tools - using Python's built-in capabilities)
    agent = await CodeAgent.create(brain=brain)

    task = """
    Calculate the first 20 Fibonacci numbers and find:
    1. The sum of all 20 numbers
    2. The ratio between consecutive numbers (showing Golden Ratio convergence)
    3. Which Fibonacci numbers are also prime

    Write efficient Python code to compute this.
    """

    print(f"\nTask: {task}")
    print("\nExecuting with PTC...")

    try:
        result = await agent.run_async(task)
        print(f"\nResult:\n{result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all PTC examples."""
    print("=" * 60)
    print("Programmatic Tool Calling (PTC) Examples")
    print("Based on: https://www.anthropic.com/engineering/advanced-tool-use")
    print("=" * 60)
    print("""
PTC Pattern Benefits:
- Token savings: 37% reduction on complex research tasks
- Reduced latency: Eliminate multiple inference passes
- Improved accuracy: Explicit logic in code vs natural language

minion's CodeAgent implements PTC by letting Claude write Python code
that orchestrates tool calls and processes data before returning results.
    """)

    # Run examples - simple_ptc_demo demonstrates pure Python code execution
    #await simple_ptc_demo()

    # Uncomment to run tool-based examples (require more time):
    await budget_compliance_example()
    #await inventory_analysis_example()
    # await data_aggregation_example()


if __name__ == "__main__":
    asyncio.run(main())
