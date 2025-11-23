#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating tool observation formatting

This example shows how tools can have different output formats
depending on whether they're used in code or as observations.
"""
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_example_tools():
    """Create example tools with observation formatting"""
    from minion.tools.base_tool import BaseTool

    class FileReadTool(BaseTool):
        """Tool that adds line numbers when output becomes observation"""
        name = "file_read"
        description = "Read file contents"
        inputs = {"file_path": {"type": "string", "description": "Path to file"}}
        output_type = "string"

        def forward(self, file_path: str) -> str:
            with open(file_path, 'r') as f:
                return f.read()

        def format_for_observation(self, output) -> str:
            if not isinstance(output, str):
                return str(output)

            lines = output.split('\n')
            padding = len(str(len(lines)))
            formatted = []

            for i, line in enumerate(lines, 1):
                formatted.append(f"{str(i).rjust(padding)} | {line}")

            return '\n'.join(formatted)

    class SearchTool(BaseTool):
        """Tool that formats search results nicely for observations"""
        name = "search"
        description = "Search for patterns"
        inputs = {"query": {"type": "string", "description": "Search query"}}
        output_type = "list"

        def forward(self, query: str) -> list:
            # Simulate search results
            return [
                {"title": "Result 1", "score": 0.95},
                {"title": "Result 2", "score": 0.87},
                {"title": "Result 3", "score": 0.75},
            ]

        def format_for_observation(self, output) -> str:
            if not isinstance(output, list):
                return str(output)

            result = f"Found {len(output)} results:\n"
            for i, item in enumerate(output, 1):
                score = item.get('score', 0)
                title = item.get('title', 'Unknown')
                result += f"  {i}. [{score:.0%}] {title}\n"

            return result

    return FileReadTool(), SearchTool()


def demonstrate_file_read():
    """Demonstrate file_read tool with different contexts"""
    print("=" * 70)
    print("EXAMPLE 1: FileReadTool - Context-Aware Formatting")
    print("=" * 70)

    file_read_tool, _ = create_example_tools()
    tool = file_read_tool

    # Create a sample file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write("def factorial(n):\n")
        f.write("    if n <= 1:\n")
        f.write("        return 1\n")
        f.write("    return n * factorial(n - 1)\n")
        temp_file = f.name

    try:
        print("\n📝 Scenario A: Tool used IN CODE (for processing)")
        print("-" * 70)
        print("Generated code:")
        print("  content = file_read(file_path='factorial.py')")
        print("  lines = content.split('\\n')")
        print("  def_line = lines[0]")

        raw_content = tool.forward(temp_file)
        print("\nValue assigned to 'content' variable:")
        print(f"  {repr(raw_content[:50])}...")
        print("\n✓ Returns RAW string that can be split, parsed, processed")

        print("\n" + "-" * 70)
        print("\n📊 Scenario B: Tool as LAST STATEMENT (becomes observation)")
        print("-" * 70)
        print("Generated code:")
        print("  file_read(file_path='factorial.py')")

        formatted = tool.format_for_observation(raw_content)
        print("\nObservation shown to LLM:")
        print(formatted)
        print("\n✓ Returns FORMATTED content with line numbers")
        print("✓ LLM can now say: 'On line 2, we check if n <= 1'")

    finally:
        os.unlink(temp_file)


def demonstrate_search():
    """Demonstrate search tool formatting"""
    print("\n\n")
    print("=" * 70)
    print("EXAMPLE 2: SearchTool - Formatted Results")
    print("=" * 70)

    file_read, search = create_example_tools()

    print("\n📝 Scenario A: Search used IN CODE")
    print("-" * 70)
    print("Generated code:")
    print("  results = search(query='machine learning')")
    print("  top_result = results[0]")
    print("  title = top_result['title']")

    raw_results = search.forward("machine learning")
    print("\nValue assigned to 'results' variable:")
    print(f"  {raw_results}")
    print("\n✓ Returns raw list that can be indexed, filtered, processed")

    print("\n" + "-" * 70)
    print("\n📊 Scenario B: Search as LAST STATEMENT")
    print("-" * 70)
    print("Generated code:")
    print("  search(query='machine learning')")

    formatted = search.format_for_observation(raw_results)
    print("\nObservation shown to LLM:")
    print(formatted)
    print("✓ Returns formatted summary with scores and rankings")


def demonstrate_workflow():
    """Demonstrate a complete workflow"""
    print("\n\n")
    print("=" * 70)
    print("EXAMPLE 3: Complete Workflow")
    print("=" * 70)

    print("\n🤖 LLM Task: 'Read the config file and check the first setting'")
    print("-" * 70)

    # Create a sample config file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write('{\n')
        f.write('  "debug": true,\n')
        f.write('  "port": 8080,\n')
        f.write('  "host": "localhost"\n')
        f.write('}\n')
        temp_file = f.name

    file_read_tool, _ = create_example_tools()
    tool = file_read_tool

    try:
        print("\n💭 Step 1: LLM generates code to read and process")
        print("Generated code:")
        code1 = """import json
config_text = file_read(file_path='config.json')
config = json.loads(config_text)
first_key = list(config.keys())[0]
first_value = config[first_key]
print(f"First setting: {first_key} = {first_value}")"""
        print(code1)
        print("\n→ file_read returns RAW text (can be parsed by json.loads)")
        print("→ Code completes successfully")

        print("\n" + "-" * 70)
        print("\n💭 Step 2: LLM wants to SEE the config file")
        print("Generated code:")
        code2 = "file_read(file_path='config.json')"
        print(code2)

        raw = tool.forward(temp_file)
        formatted = tool.format_for_observation(raw)

        print("\nObservation to LLM:")
        print(formatted)
        print("\n→ LLM sees line-numbered content")
        print("→ LLM can reference 'line 2' or 'line 3' in response")
        print("\n🎯 LLM Response: 'I can see on line 2 that debug is set to true'")

    finally:
        os.unlink(temp_file)


def main():
    """Run all demonstrations"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "TOOL OBSERVATION FORMATTING DEMO" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")

    demonstrate_file_read()
    demonstrate_search()
    demonstrate_workflow()

    print("\n\n")
    print("=" * 70)
    print("🎓 KEY TAKEAWAYS")
    print("=" * 70)
    print("""
1. Tools return RAW data when used in code (for processing)
2. Tools return FORMATTED data when used as observations (for LLM understanding)
3. Same tool, different contexts = context-aware output
4. Benefits:
   - Single tool definition serves both purposes
   - LLM gets better formatted information for understanding
   - Code gets raw data for computation
   - Cleaner tool design with separation of concerns

5. Implementation:
   - Override format_for_observation() in your tool
   - CodeMinion automatically detects context and formats appropriately
   - No changes needed to tool usage code
""")
    print("=" * 70)


if __name__ == '__main__':
    main()
