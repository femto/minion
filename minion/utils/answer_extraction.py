#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import json
import multiprocessing
import re
from math import isclose
from typing import Union, Optional

import regex
from sympy import N, simplify
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import parse_expr

from minion.utils.custom_decoder import CustomDecoder
from minion.utils.sanitize import sanitize


def extract_final_answer(text):
    # Match for <final_answer> tag
    match_tag = re.search(r"<final_answer>\s*(.*?)\s*</final_answer>", text, re.DOTALL)
    if match_tag:
        return match_tag.group(1).strip()

    return text

def extract_python(code: str, entrypoint: Optional[str] = None):
    return sanitize(code, entrypoint)
    # Regex pattern to extract code inside ```python ``` blocks
    # pattern = r"```python(.*?)```"
    # match = re.search(pattern, text, re.DOTALL)
    # if match:
    #     # Return the extracted code, strip to remove leading/trailing newlines
    #     return match.group(1).strip()
    # return text
def extract_longest_json_from_string(text):
    # Regular expression pattern to match all content between ```json and ```
    pattern = r"```json\s*([\s\S]*?)\s*```"

    # Find all matches in the input text
    matches = re.findall(pattern, text)

    if matches:
        # Heuristic: Select the longest JSON block, assuming it's the most comprehensive
        longest_match = max(matches, key=len)

        try:
            # Decode the longest JSON block
            return CustomDecoder(strict=False).decode(longest_match)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON content in the selected block.") from e
    else:
        raise ValueError("No JSON content found.")


def extract_answer(text):
    # Match for <final_answer> tag
    match_tag = re.search(r"<answer>\s*(.*?)\s*</answer>", text, re.DOTALL)
    if match_tag:
        return match_tag.group(1).strip()

    return text

def extract_gsm8k_answer(answer_str):
    # Regular expression to find the answer after '####'
    match = re.search(r"####\s*(.*)", answer_str)
    if match:
        return match.group(1).strip()  # Extract and remove any surrounding whitespace
    else:
        return answer_str  # Return None if no match is found


def extract_math_answer(answer_str):
    # Custom function to extract the content inside \boxed{...}, handling nested braces
    def extract_boxed_content(s):
        stack = []
        start_idx = None
        for i, char in enumerate(s):
            if char == "{":
                if start_idx is None:
                    start_idx = i
                stack.append("{")
            elif char == "}":
                stack.pop()
                if not stack:  # We found the matching closing brace
                    return s[start_idx + 1 : i]  # Return the content inside the braces
        return None

    # Look for the answer within \boxed{...}
    boxed_match = re.search(r"\\boxed{", answer_str)
    if boxed_match:
        # Start searching from the position of \boxed{
        return extract_boxed_content(answer_str[boxed_match.end() - 1 :])

    # If no \boxed{...}, return the last sentence
    sentences = answer_str.split(".")
    return sentences[-1].strip() if sentences else ""


def parse_digits(num):
    # format: 234.23 || 23%
    num = regex.sub(",", "", str(num))
    try:
        return float(num)
    except:
        if num.endswith("%"):
            num = num[:-1]
            if num.endswith("\\"):
                num = num[:-1]
            try:
                return float(num) / 100
            except:
                pass
    return None


def is_digit(num):
    # paired with parse_digits
    return parse_digits(num) is not None


def symbolic_equal(a, b):
    def _parse(s):
        for f in [parse_latex, parse_expr]:
            try:
                return f(s)
            except:
                pass
        return s

    a = _parse(a)
    b = _parse(b)

    try:
        if simplify(a - b) == 0:
            return True
    except:
        pass

    try:
        if isclose(N(a), N(b), abs_tol=1e-3):
            return True
    except:
        pass
    return False


def call_with_timeout(func, *args, timeout=5, **kwargs):
    output_queue = multiprocessing.Queue()
    process_args = args + (output_queue,)
    process = multiprocessing.Process(target=func, args=process_args, kwargs=kwargs)
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        return False

    return output_queue.get()


def strip_outer_brackets(expression):
    """
    Remove outer parentheses or square brackets from the given expression, if present.
    """
    # Match and strip outer brackets if they exist
    expression = expression.strip()
    if re.match(r"(\(|\[).+(\)|\])", expression, re.DOTALL):
        return expression[1:-1].strip()
    if re.match(r"(\\\[).+(\\\])", expression, re.DOTALL):
        return expression[2:-2].strip()
    if re.match(r"(\\\().+(\\\))", expression, re.DOTALL):
        return expression[2:-2].strip()
    return expression


def math_equal(
    prediction: Union[bool, float, str],
    reference: Union[float, str],
    include_percentage: bool = True,
    is_close: bool = True,
    timeout: bool = False,
) -> bool:
    """
    Exact match of math if and only if:
    1. numerical equal: both can convert to float and are equal
    2. symbolic equal: both can convert to sympy expression and are equal
    """
    if str(prediction) == str(reference):
        return True

    try:  # 1. numerical equal
        if is_digit(prediction) and is_digit(reference):
            prediction = parse_digits(prediction)
            reference = parse_digits(reference)
            # number questions
            if include_percentage:
                gt_result = [reference / 100, reference, reference * 100]
            else:
                gt_result = [reference]
            for item in gt_result:
                try:
                    if is_close:
                        if isclose(item, prediction, abs_tol=1e-3):
                            return True
                    else:
                        if item == prediction:
                            return True
                except Exception:
                    continue
            return False
    except:
        pass

    if not prediction and prediction not in [0, False]:
        return False

    # 2. symbolic equal
    reference = str(reference).strip()
    prediction = str(prediction).strip()

    if (
        regex.match(r"(\(|\[).+(\)|\])", prediction, re.DOTALL) is not None
        or regex.match(r"(\(|\[).+(\)|\])", reference, re.DOTALL) is not None
        or regex.match(r"(\\\[).+(\\\])", prediction, re.DOTALL) is not None
        or regex.match(r"(\\\[).+(\\\])", reference, re.DOTALL) is not None
    ):
        pred_parts = strip_outer_brackets(prediction)
        ref_parts = strip_outer_brackets(reference)

        pred_parts = pred_parts.split(",")
        ref_parts = ref_parts.split(",")
        if len(pred_parts) == len(ref_parts):
            if all(
                [math_equal(pred_parts[i], ref_parts[i], include_percentage, is_close) for i in range(len(pred_parts))]
            ):
                return True

    if (
        regex.match(r"(\(|\[).+(\)|\])", prediction) is not None
        and regex.match(r"(\(|\[).+(\)|\])", reference) is not None
    ):
        pred_parts = prediction[1:-1].split(",")
        ref_parts = reference[1:-1].split(",")
        if len(pred_parts) == len(ref_parts):
            if all(
                [math_equal(pred_parts[i], ref_parts[i], include_percentage, is_close) for i in range(len(pred_parts))]
            ):
                return True

    if (
        (prediction.startswith("\\begin{pmatrix}") or prediction.startswith("\\begin{bmatrix}"))
        and (prediction.endswith("\\end{pmatrix}") or prediction.endswith("\\end{bmatrix}"))
        and (reference.startswith("\\begin{pmatrix}") or reference.startswith("\\begin{bmatrix}"))
        and (reference.endswith("\\end{pmatrix}") or reference.endswith("\\end{bmatrix}"))
    ):
        pred_lines = [
            line.strip()
            for line in prediction[len("\\begin{pmatrix}") : -len("\\end{pmatrix}")].split("\\\\")
            if line.strip()
        ]
        ref_lines = [
            line.strip()
            for line in reference[len("\\begin{pmatrix}") : -len("\\end{pmatrix}")].split("\\\\")
            if line.strip()
        ]
        matched = True
        if len(pred_lines) == len(ref_lines):
            for pred_line, ref_line in zip(pred_lines, ref_lines):
                pred_parts = pred_line.split("&")
                ref_parts = ref_line.split("&")
                if len(pred_parts) == len(ref_parts):
                    if not all(
                        [
                            math_equal(pred_parts[i], ref_parts[i], include_percentage, is_close)
                            for i in range(len(pred_parts))
                        ]
                    ):
                        matched = False
                        break
                else:
                    matched = False
                if not matched:
                    break
        else:
            matched = False
        if matched:
            return True

    if prediction.count("=") == 1 and reference.count("=") == 1:
        pred = prediction.split("=")
        pred = f"{pred[0].strip()} - ({pred[1].strip()})"
        ref = reference.split("=")
        ref = f"{ref[0].strip()} - ({ref[1].strip()})"
        if symbolic_equal(pred, ref) or symbolic_equal(f"-({pred})", ref):
            return True
    elif prediction.count("=") == 1 and len(prediction.split("=")[0].strip()) <= 2 and "=" not in reference:
        if math_equal(prediction.split("=")[1], reference, include_percentage, is_close):
            return True
    elif reference.count("=") == 1 and len(reference.split("=")[0].strip()) <= 2 and "=" not in prediction:
        if math_equal(prediction, reference.split("=")[1], include_percentage, is_close):
            return True

    # symbolic equal with sympy
    if timeout:
        if call_with_timeout(symbolic_equal, prediction, reference):
            return True
    else:
        if symbolic_equal(prediction, reference):
            return True

    return False


def calculate_score(expected_output: str, prediction: str) -> int:
    expected_answer = extract_answer(expected_output)
    predicted_answer = extract_answer(prediction)

    return 1 if math_equal(predicted_answer, expected_answer) else 0
# 测试代码
# test_code = '''
# A=100
# def helper_function():
#     return 42
#
# def main_function():
#     result = helper_function()
#     return result * 2
#
# def another_function():
#     print("Hello")
# '''
#
# # 让我们测试一下 extract_python 和 sanitize 函数
# from minion.utils.answer_extraction import extract_python
# from minion.utils.sanitize import sanitize
#
# # 测试 1: entrypoint 为空
# print("Test 1 - Empty entrypoint:")
# result1 = extract_python(test_code, entrypoint='')
# print(result1)
# print("\n" + "="*50 + "\n")
#
# # 测试 2: 指定 entrypoint
# print("Test 2 - With entrypoint 'main_function':")
# result2 = extract_python(test_code, entrypoint='main_function')
# print(result2)