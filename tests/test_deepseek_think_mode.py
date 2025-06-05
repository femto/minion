import pytest
from minion.main.prompt import extract_think_and_answer, format_deepseek_response, COT_PROBLEM_INSTRUCTION


class TestDeepSeekThinkMode:
    """Test cases for DeepSeek think mode functionality"""

    def test_extract_think_and_answer_with_think_tags(self):
        """Test extracting think content and answer from response with think tags"""
        response = """<think>
Let me think about this step by step.
First, I need to understand the problem.
Then I need to solve it systematically.
</think>

Based on my analysis, the answer is 42.
This is the final result with high confidence.
"""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        expected_think = """Let me think about this step by step.
First, I need to understand the problem.
Then I need to solve it systematically."""
        
        expected_answer = """Based on my analysis, the answer is 42.
This is the final result with high confidence."""
        
        assert think_content.strip() == expected_think.strip()
        assert answer_content.strip() == expected_answer.strip()

    def test_extract_think_and_answer_multiple_think_blocks(self):
        """Test extracting multiple think blocks"""
        response = """<think>
First thought process here.
</think>

Some intermediate text.

<think>
Second thought process here.
More detailed analysis.
</think>

Final answer: The solution is X."""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        expected_think = """First thought process here.


Second thought process here.
More detailed analysis."""
        
        expected_answer = """Some intermediate text.



Final answer: The solution is X."""
        
        assert think_content.strip() == expected_think.strip()
        assert answer_content.strip() == expected_answer.strip()

    def test_extract_think_and_answer_no_think_tags(self):
        """Test extracting from response without think tags"""
        response = """This is just a regular answer without any think tags.
The solution is straightforward and doesn't require thinking tags."""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        assert think_content == ""
        assert answer_content.strip() == response.strip()

    def test_extract_think_and_answer_empty_think_tags(self):
        """Test extracting from response with empty think tags"""
        response = """<think></think>

The answer is provided without any thinking process."""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        assert think_content == ""
        assert answer_content.strip() == "The answer is provided without any thinking process."

    def test_extract_think_and_answer_nested_tags_in_content(self):
        """Test handling content that contains tag-like strings"""
        response = """<think>
I need to consider the <problem> and its <solution>.
This involves analyzing <data> structures.
</think>

The final answer involves working with <xml> tags and <html> elements."""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        expected_think = """I need to consider the <problem> and its <solution>.
This involves analyzing <data> structures."""
        
        expected_answer = "The final answer involves working with <xml> tags and <html> elements."
        
        assert think_content.strip() == expected_think.strip()
        assert answer_content.strip() == expected_answer.strip()

    def test_format_deepseek_response_with_both_contents(self):
        """Test formatting response with both think and answer content"""
        think_content = """Let me analyze this problem.
Step 1: Understand the requirements.
Step 2: Devise a solution."""
        
        answer_content = """The solution is to implement algorithm X.
This will solve the problem efficiently."""
        
        result = format_deepseek_response(think_content, answer_content)
        
        expected = """<think>
Let me analyze this problem.
Step 1: Understand the requirements.
Step 2: Devise a solution.
</think>

The solution is to implement algorithm X.
This will solve the problem efficiently."""
        
        assert result == expected

    def test_format_deepseek_response_no_think_content(self):
        """Test formatting response with only answer content"""
        think_content = ""
        answer_content = "This is just a direct answer without thinking."
        
        result = format_deepseek_response(think_content, answer_content)
        
        assert result == answer_content

    def test_format_deepseek_response_empty_answer(self):
        """Test formatting response with think content but empty answer"""
        think_content = "I'm thinking about this problem..."
        answer_content = ""
        
        result = format_deepseek_response(think_content, answer_content)
        
        expected = """<think>
I'm thinking about this problem...
</think>

"""
        
        assert result == expected

    def test_roundtrip_extraction_and_formatting(self):
        """Test that extracting and then formatting preserves the original structure"""
        original_response = """<think>
This is my thinking process.
I need to solve this step by step.
</think>

This is my final answer.
It's based on the analysis above."""
        
        # Extract
        think_content, answer_content = extract_think_and_answer(original_response)
        
        # Format back
        reconstructed = format_deepseek_response(think_content, answer_content)
        
        # Should be equivalent (allowing for whitespace differences)
        original_think, original_answer = extract_think_and_answer(original_response)
        reconstructed_think, reconstructed_answer = extract_think_and_answer(reconstructed)
        
        assert original_think.strip() == reconstructed_think.strip()
        assert original_answer.strip() == reconstructed_answer.strip()

    def test_extract_with_multiline_think_content(self):
        """Test extracting think content that spans multiple lines with various formatting"""
        response = """<think>
Problem Analysis:
- Input: A complex mathematical equation
- Output: Numerical solution
- Constraints: Must be solved analytically

Solution Approach:
1. Simplify the equation
2. Apply algebraic rules
3. Solve for x

Mathematical Steps:
x^2 + 5x + 6 = 0
(x + 2)(x + 3) = 0
x = -2 or x = -3
</think>

The solutions to the equation x^2 + 5x + 6 = 0 are x = -2 and x = -3.

Verification:
- For x = -2: (-2)^2 + 5(-2) + 6 = 4 - 10 + 6 = 0 ✓
- For x = -3: (-3)^2 + 5(-3) + 6 = 9 - 15 + 6 = 0 ✓"""
        
        think_content, answer_content = extract_think_and_answer(response)
        
        assert "Problem Analysis:" in think_content
        assert "Solution Approach:" in think_content
        assert "Mathematical Steps:" in think_content
        assert "x = -2 or x = -3" in think_content
        
        assert "The solutions to the equation" in answer_content
        assert "Verification:" in answer_content
        assert "✓" in answer_content
        
        # Ensure think content doesn't appear in answer content
        assert "<think>" not in answer_content
        assert "</think>" not in answer_content

    def test_cot_problem_instruction_format(self):
        """Test that COT_PROBLEM_INSTRUCTION follows DeepSeek think mode format"""
        assert "<think>" in COT_PROBLEM_INSTRUCTION
        assert "</think>" in COT_PROBLEM_INSTRUCTION
        
        # Should not contain the old <final_answer> tags
        assert "<final_answer>" not in COT_PROBLEM_INSTRUCTION
        assert "</final_answer>" not in COT_PROBLEM_INSTRUCTION
        
        # Should have instruction outside think tags
        lines = COT_PROBLEM_INSTRUCTION.strip().split('\n')
        think_end_index = -1
        for i, line in enumerate(lines):
            if "</think>" in line:
                think_end_index = i
                break
        
        # There should be content after </think> tag
        assert think_end_index != -1
        assert think_end_index < len(lines) - 1
        
        # The content after </think> should not be empty
        remaining_content = '\n'.join(lines[think_end_index + 1:]).strip()
        assert len(remaining_content) > 0

    def test_integration_with_typical_cot_response(self):
        """Test integration with a typical COT response in DeepSeek format"""
        # Simulate a typical response from CotMinion using the new instruction format
        simulated_response = """<think>
Let me approach this problem systematically.

First, I need to understand what we're looking for:
- We have a mathematical problem to solve
- We need to find the value of x

Now, let me solve step by step:
1. Start with the equation: 2x + 5 = 15
2. Subtract 5 from both sides: 2x = 10
3. Divide by 2: x = 5

Let me verify: 2(5) + 5 = 10 + 5 = 15 ✓
</think>

The value of x is 5.

To solve the equation 2x + 5 = 15:
- Subtract 5 from both sides: 2x = 10
- Divide by 2: x = 5

Confidence: 95% / High"""
        
        think_content, answer_content = extract_think_and_answer(simulated_response)
        
        # Verify think content contains the reasoning
        assert "approach this problem systematically" in think_content
        assert "solve step by step" in think_content
        assert "2x + 5 = 15" in think_content
        assert "x = 5" in think_content
        assert "Let me verify" in think_content
        
        # Verify answer content contains the final answer
        assert "The value of x is 5" in answer_content
        assert "Confidence: 95% / High" in answer_content
        
        # Verify clean separation
        assert "<think>" not in answer_content
        assert "</think>" not in answer_content


class TestMinionIntegration:
    """Test minion integration with DeepSeek think mode"""

    def test_raw_minion_answer_extraction(self):
        """Test RawMinion extracts answers correctly from think mode responses"""
        # Simulate a RawMinion response processing
        from minion.main.worker import RawMinion
        from minion.main.prompt import extract_think_and_answer
        
        # Simulate what RawMinion.execute() would do
        response = """<think>
Let me analyze this query step by step.
The user is asking for a simple calculation.
2 + 2 = 4
</think>

The answer to 2 + 2 is 4."""
        
        # This is what happens inside RawMinion.execute()
        think_content, answer_content = extract_think_and_answer(response)
        final_answer = answer_content if answer_content else response
        
        assert think_content.strip() == "Let me analyze this query step by step.\nThe user is asking for a simple calculation.\n2 + 2 = 4"
        assert final_answer.strip() == "The answer to 2 + 2 is 4."

    def test_native_minion_answer_extraction(self):
        """Test NativeMinion extracts answers correctly from think mode responses"""
        # Simulate a NativeMinion response processing
        from minion.main.worker import NativeMinion
        from minion.main.prompt import extract_think_and_answer
        
        # Simulate what NativeMinion.execute() would do
        response = """<think>
I need to provide a comprehensive answer to this question.
Let me break down the components:
1. Understanding the query
2. Providing accurate information
3. Ensuring clarity
</think>

Based on the analysis, here is the comprehensive answer to your question.
The key points are clearly explained and well-structured."""
        
        # This is what happens inside NativeMinion.execute()
        think_content, answer_content = extract_think_and_answer(response)
        final_answer = answer_content if answer_content else response
        
        expected_think = """I need to provide a comprehensive answer to this question.
Let me break down the components:
1. Understanding the query
2. Providing accurate information
3. Ensuring clarity"""
        
        expected_answer = """Based on the analysis, here is the comprehensive answer to your question.
The key points are clearly explained and well-structured."""
        
        assert think_content.strip() == expected_think.strip()
        assert final_answer.strip() == expected_answer.strip()

    def test_minion_fallback_behavior(self):
        """Test minion behavior when there are no think tags (fallback to original response)"""
        from minion.main.prompt import extract_think_and_answer
        
        # Response without think tags
        response = """This is a direct answer without any thinking process.
No additional processing needed."""
        
        # This is what happens in all minions now
        think_content, answer_content = extract_think_and_answer(response)
        final_answer = answer_content if answer_content else response
        
        assert think_content == ""
        assert final_answer == response

    def test_minion_empty_answer_handling(self):
        """Test minion behavior when think tags exist but answer content is empty"""
        from minion.main.prompt import extract_think_and_answer
        
        # Response with only think content
        response = """<think>
I'm thinking about this problem but haven't reached a conclusion yet.
Still processing the information.
</think>"""
        
        # This is what happens in all minions now
        think_content, answer_content = extract_think_and_answer(response)
        final_answer = answer_content if answer_content else response
        
        assert "thinking about this problem" in think_content
        assert answer_content.strip() == ""
        assert final_answer == response  # Falls back to original response


if __name__ == "__main__":
    pytest.main([__file__]) 