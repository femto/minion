#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/9/1$ 13:38$
@Author  : femto Zheng
@File    : extract_answer.py$
"""
import asyncio
import re


def extract_gsm8k_answer(text: str) -> str:
    """
    Extracts the answer for GSM8K-style questions where the answer is preceded by '#### '.
    """
    match = re.search(r"####\s*(.+)", text)
    if match:
        return match.group(1).strip()
    return None


def extract_math_answer(text: str) -> str:
    """
    Extracts the answer for math problems where the answer is enclosed in \boxed{},
    ensuring that the braces are balanced.
    """
    # Find the starting point of \boxed{ using regex
    match = re.search(r"\\boxed\{", text)
    if not match:
        return None

    # Initialize a stack to keep track of braces
    stack = []
    start_index = match.end() - 1  # Start right after \boxed{

    # Traverse the text from the starting index to extract the balanced content
    for i in range(start_index, len(text)):
        char = text[i]
        if char == "{":
            stack.append(char)
        elif char == "}":
            stack.pop()
            if not stack:
                # When stack is empty, we've found the matching closing brace
                return text[start_index + 1 : i].strip()

    return None


def extract_correct_answer(text: str, query_type: str) -> str:
    """
    Determines which extraction method to use based on the query type.
    """
    if query_type == "gsm8k":
        return extract_gsm8k_answer(text)
    elif query_type == "math":
        return extract_math_answer(text)
    else:
        raise ValueError("Unknown query type for answer extraction")


# Example usage with a model:
async def main():
    # extracted_answer = extract_correct_answer(model_instance.answer_raw, model_instance.query_type)
    # print(f"Extracted Answer: {extracted_answer}")
    # Example usage:
    gsm8k_text = "She earned 0.2 x 50 = $<<0.2*50=10>>10.\n#### 10"
    math_text = "For any angle $x$, we have $\sin (180^\circ - x)=\sin x$, so $\sin RPS = \sin(180^\circ - \angle RPS) = \sin \angle RPQ = \\boxed{\\frac{7}{25}}$."

    gsm8k_answer = extract_gsm8k_answer(gsm8k_text)
    math_answer = extract_math_answer(math_text)

    print(f"GSM8K Answer: {gsm8k_answer}")  # Output: "10"
    print(f"Math Answer: {math_answer}")  # Output: "\frac{7}{25}"


if __name__ == "__main__":
    asyncio.run(main())
