#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standalone demonstration of tool observation formatting

This example shows the concept without requiring minion package imports.
"""
import tempfile
import os


# Minimal BaseTool implementation for demo
class BaseTool:
    """Base class for tools"""

    def format_for_observation(self, output):
        """Default: just convert to string"""
        return str(output) if output is not None else ""


class FileReadTool(BaseTool):
    """Tool that formats file content with line numbers for observations"""

    def forward(self, file_path: str) -> str:
        """Read and return raw file content"""
        with open(file_path, 'r') as f:
            return f.read()

    def format_for_observation(self, output) -> str:
        """Add line numbers when shown as observation to LLM"""
        if not isinstance(output, str):
            return str(output)

        lines = output.split('\n')
        padding = len(str(len(lines)))
        formatted = []

        for i, line in enumerate(lines, 1):
            formatted.append(f"{str(i).rjust(padding)} | {line}")

        return '\n'.join(formatted)


class SearchTool(BaseTool):
    """Tool that formats search results nicely"""

    def forward(self, query: str) -> list:
        """Return raw search results"""
        return [
            {"title": "Introduction to Python", "score": 0.95, "url": "python.org"},
            {"title": "Python Best Practices", "score": 0.87, "url": "realpython.com"},
            {"title": "Advanced Python", "score": 0.75, "url": "docs.python.org"},
        ]

    def format_for_observation(self, output) -> str:
        """Format results with scores and ranking"""
        if not isinstance(output, list):
            return str(output)

        result = f"🔍 Found {len(output)} results:\n\n"
        for i, item in enumerate(output, 1):
            score = item.get('score', 0)
            title = item.get('title', 'Unknown')
            url = item.get('url', '')
            bar = '█' * int(score * 10)
            result += f"  {i}. {title}\n"
            result += f"     Score: [{bar:<10}] {score:.0%}\n"
            result += f"     URL: {url}\n\n"

        return result


def demo_file_read():
    """Demonstrate FileReadTool"""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DEMO 1: FileReadTool" + " " * 32 + "║")
    print("╚" + "═" * 68 + "╝\n")

    tool = FileReadTool()

    # Create sample Python file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write("def calculate_total(items):\n")
        f.write("    total = sum(items)\n")
        f.write("    return total\n")
        f.write("\n")
        f.write("result = calculate_total([1, 2, 3, 4, 5])\n")
        f.write("print(f'Total: {result}')\n")
        temp_file = f.name

    try:
        # Scenario A: In-code usage
        print("📝 SCENARIO A: Tool Used IN CODE")
        print("─" * 70)
        print("LLM generates code:")
        print("┌" + "─" * 68 + "┐")
        print("│ content = file_read(file_path='calculate.py')              │")
        print("│ lines = content.split('\\n')                                │")
        print("│ function_def = lines[0]                                    │")
        print("│ print(f'Function: {function_def}')                         │")
        print("└" + "─" * 68 + "┘")

        raw_content = tool.forward(temp_file)
        print("\n🔧 What 'content' variable receives (RAW data):")
        print("┌" + "─" * 68 + "┐")
        print(f"│ {repr(raw_content[:50])}...")
        print("└" + "─" * 68 + "┘")
        print("✓ Pure string that can be split, parsed, and processed")

        # Scenario B: As observation
        print("\n\n📊 SCENARIO B: Tool as LAST STATEMENT (becomes observation)")
        print("─" * 70)
        print("LLM generates code:")
        print("┌" + "─" * 68 + "┐")
        print("│ file_read(file_path='calculate.py')                       │")
        print("└" + "─" * 68 + "┘")

        formatted = tool.format_for_observation(raw_content)
        print("\n👁️  Observation shown to LLM (FORMATTED with line numbers):")
        print("┌" + "─" * 68 + "┐")
        for line in formatted.split('\n'):
            print(f"│ {line:<66} │")
        print("└" + "─" * 68 + "┘")
        print("✓ LLM can reference 'line 2' or 'line 5' in its reasoning")

    finally:
        os.unlink(temp_file)


def demo_search():
    """Demonstrate SearchTool"""
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DEMO 2: SearchTool" + " " * 33 + "║")
    print("╚" + "═" * 68 + "╝\n")

    tool = SearchTool()

    # Scenario A: In-code usage
    print("📝 SCENARIO A: Tool Used IN CODE")
    print("─" * 70)
    print("LLM generates code:")
    print("┌" + "─" * 68 + "┐")
    print("│ results = search(query='Python tutorial')                     │")
    print("│ top_result = results[0]                                       │")
    print("│ best_title = top_result['title']                              │")
    print("│ best_score = top_result['score']                              │")
    print("└" + "─" * 68 + "┘")

    raw_results = tool.forward("Python tutorial")
    print("\n🔧 What 'results' variable receives (RAW data):")
    print("┌" + "─" * 68 + "┐")
    print("│ [                                                              │")
    print("│   {'title': 'Introduction to Python', 'score': 0.95, ...},    │")
    print("│   {'title': 'Python Best Practices', 'score': 0.87, ...},     │")
    print("│   ...                                                          │")
    print("│ ]                                                              │")
    print("└" + "─" * 68 + "┘")
    print("✓ Raw list that can be indexed, filtered, sorted")

    # Scenario B: As observation
    print("\n\n📊 SCENARIO B: Tool as LAST STATEMENT (becomes observation)")
    print("─" * 70)
    print("LLM generates code:")
    print("┌" + "─" * 68 + "┐")
    print("│ search(query='Python tutorial')                               │")
    print("└" + "─" * 68 + "┘")

    formatted = tool.format_for_observation(raw_results)
    print("\n👁️  Observation shown to LLM (FORMATTED summary):")
    print("┌" + "─" * 68 + "┐")
    for line in formatted.split('\n'):
        print(f"│ {line:<66} │")
    print("└" + "─" * 68 + "┘")
    print("✓ LLM sees formatted summary with visual score bars")


def demo_workflow():
    """Demonstrate complete workflow"""
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DEMO 3: Complete Workflow" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝\n")

    print("🤖 User Task: 'Find the API key in the config file'\n")

    # Create config file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write('{\n')
        f.write('  "app_name": "MyApp",\n')
        f.write('  "version": "1.0",\n')
        f.write('  "api_key": "sk-abc123def456",\n')
        f.write('  "debug": false\n')
        f.write('}\n')
        temp_file = f.name

    tool = FileReadTool()

    try:
        print("💭 TURN 1: LLM decides to read the config")
        print("─" * 70)
        print("Generated code (observation mode):")
        print("  file_read(file_path='config.json')")

        raw = tool.forward(temp_file)
        formatted = tool.format_for_observation(raw)

        print("\nObservation:")
        print(formatted)

        print("\n🧠 LLM Reasoning: 'I can see the api_key on line 4'")

        print("\n" + "─" * 70)
        print("\n💭 TURN 2: LLM extracts the API key")
        print("─" * 70)
        print("Generated code (processing mode):")
        print("  import json")
        print("  content = file_read(file_path='config.json')")
        print("  config = json.loads(content)")
        print("  api_key = config['api_key']")
        print("  final_answer(api_key)")

        print("\n✅ Result: 'sk-abc123def456'")

        print("\n" + "─" * 70)
        print("🎯 Key Point: Same tool used twice with different purposes!")
        print("   Turn 1: Observation format (with line numbers)")
        print("   Turn 2: Raw format (for JSON parsing)")

    finally:
        os.unlink(temp_file)


def print_summary():
    """Print summary of benefits"""
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "KEY BENEFITS" + " " * 36 + "║")
    print("╚" + "═" * 68 + "╝\n")

    benefits = [
        ("🎯 Context-Aware", "Same tool, different output based on usage context"),
        ("🔧 Code-Friendly", "Returns raw data when used in code for processing"),
        ("👁️  LLM-Friendly", "Returns formatted view when shown as observation"),
        ("📝 Better Reasoning", "Line numbers help LLM reference specific parts"),
        ("♻️  Reusable", "Single tool definition serves both purposes"),
        ("🧹 Clean Design", "Separation of computation and presentation"),
    ]

    for emoji_title, description in benefits:
        print(f"{emoji_title}")
        print(f"  {description}\n")


def main():
    """Run all demonstrations"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "TOOL OBSERVATION FORMATTING - LIVE DEMO" + " " * 19 + "║")
    print("╚" + "═" * 68 + "╝")

    demo_file_read()
    demo_search()
    demo_workflow()
    print_summary()

    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 25 + "END OF DEMO" + " " * 31 + "║")
    print("╚" + "═" * 68 + "╝\n")


if __name__ == '__main__':
    main()
