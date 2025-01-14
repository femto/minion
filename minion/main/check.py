import doctest
import inspect
import re
import sys
import xml.etree.ElementTree as ET
from io import StringIO
from contextlib import redirect_stdout

from jinja2 import Template

from minion.logs import logger
from minion.main.check_route import register_check_minion
from minion.main.minion import Minion
from minion.main.prompt import CHECK_PROMPT
from minion.actions.lmp_action_node import LmpActionNode
from minion.models.schemas import CheckResult
from minion.utils.syncheck import run_with_timeout
from minion.utils.process import run_code_in_separate_process

def extract_root_content(text):
    pattern = r"(<root>.*?</root>)"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def extract_feedback_parts(xml_string):
    try:
        # Create a file-like object from the string
        xml_string = extract_root_content(xml_string)
        xml_file = StringIO(xml_string)

        # Parse the XML
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Extract feedback content
        feedback_content = root.find("feedback").text.strip()

        # Extract correctness and convert to boolean
        correct_text = root.find("correct").text.lower()
        correct = correct_text.lower() == "true"

        # Extract score and convert to float
        score = float(root.find("score").text)

        return {"feedback_content": feedback_content, "correct": correct, "score": score}
    except Exception as e:
        logger.error(e)
        return None

@register_check_minion
class CheckMinion(Minion):
    """Check Minion"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to verify this answer"

    async def execute(self):
        prompt = Template(CHECK_PROMPT)
        prompt = prompt.render(input=self.input)

        node = LmpActionNode(self.brain.llm)
        result = await node.execute(prompt, response_format=CheckResult, format="xml_simple")

        self.answer_node = result
        self.answer = self.input.feedback = {
            "feedback": result.feedback,
            "correct": result.correct,
            "score": result.score
        }

        if result:
            return self.answer

@register_check_minion
class TestMinion(CheckMinion):
    """Test Minion for verifying code solutions with test cases"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.test_cases = []

    def _process_test_cases(self, test_cases, entry_point):
        """Replace 'candidate' with actual function name in test cases"""
        processed_tests = []
        for test in test_cases:
            # 将 candidate 替换为实际的函数名
            processed_test = test.replace('candidate', entry_point)
            processed_tests.append(processed_test)
        return processed_tests

    async def execute(self):
        if not self.input.metadata.get('test_cases'):
            return await super().execute()
            
        # metadata 直接包含测试用例数组
        raw_test_cases = self.input.metadata['test_cases']
        self.entry_point = self.input.entry_point # 默认使用 sort_array
        
        # 处理测试用例,替换函数名
        #humaneval format, using candidate in test case
        self.test_cases = self._process_test_cases(raw_test_cases, self.entry_point)
        
        return await self._execute_test()

    async def _execute_test(self):
        """Execute test logic"""
        feedback = []
        passed_count = 0
        total_tests = len(self.test_cases)
        test_results = []
        
        # 获取要测试的代码
        solution = self.input.answer
        
        # 创建本地环境执行测试
        local_env = {}
        timeout = 120 #todo: specify some default timeout?
        try:
            # 执行代码定义函数
            run_with_timeout(exec,[solution, local_env],timeout=timeout)
            
            # 执行每个测试用例
            for i, test_case in enumerate(self.test_cases, 1):
                try:
                    run_with_timeout(exec, [test_case, local_env], timeout=timeout)
                    passed_count += 1
                    test_results.append({
                        "test": test_case,
                        "passed": True
                    })
                    logger.info(f"Test {i}/{total_tests} PASSED: {test_case}")
                except AssertionError as e:
                    error_msg = f"Test failed: {test_case}\nAssertion Error: {str(e)}"
                    feedback.append(error_msg)
                    test_results.append({
                        "test": test_case,
                        "passed": False,
                        "error": error_msg
                    })
                    logger.error(f"Test {i}/{total_tests} FAILED: {error_msg}")
                except Exception as e:
                    error_msg = f"Test failed: {test_case}\nError: {str(e)}"
                    feedback.append(error_msg)
                    test_results.append({
                        "test": test_case,
                        "passed": False,
                        "error": error_msg
                    })
                    logger.error(f"Test {i}/{total_tests} ERROR: {error_msg}")
                    
        except Exception as e:
            error_msg = f"Failed to execute solution: {str(e)}"
            feedback.append(error_msg)
            test_results.append({
                "test": "code execution",
                "passed": False,
                "error": error_msg
            })
            logger.error(f"Code execution failed: {error_msg}")
            passed_count = 0  # 如果代码执行失败,分数为0

        # 计算得分(通过率)
        score = passed_count / total_tests if total_tests > 0 else 0.0

        # 记录最终结果
        if score == 1.0:
            logger.info(f"All {total_tests} tests PASSED!")
        else:
            logger.warning(f"Tests completed: {passed_count}/{total_tests} passed (score: {score:.2f})")

        # 直接构造feedback字典
        self.answer = self.input.feedback = {
            "feedback": "\n".join(feedback) if feedback else "All tests passed!",
            "correct": (score == 1.0),
            "score": score,
            "test_results": test_results
        }

        return self.answer

@register_check_minion
class DoctestMinion(CheckMinion):
    """Test Minion for verifying code solutions with doctest examples"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.test_cases = self.extract_doctest(self.input.answer)

    def extract_doctest(self, query):
        """Extract test cases from docstring"""
        parser = doctest.DocTestParser()
        doctests = []
        tests = parser.get_examples(query)
        doctests.extend(tests)
        return doctests

    async def execute(self):
        if not self.test_cases:
            return await super().execute()
            
        prompt = Template(CHECK_PROMPT)
        context = {
            'input': self.input,
            'test_cases': self.test_cases,
            'test_type': 'doctest'
        }
        prompt = prompt.render(**context)
        
        return await self._execute_test(prompt)

    async def _execute_test(self, prompt):
        """Execute test logic"""
        node = LmpActionNode(self.brain.llm)
        result = await node.execute(prompt, response_format=CheckResult)
        
        self.answer_node = result
        self.answer = self.input.feedback = {
            "feedback": result.feedback,
            "correct": result.correct,
            "score": result.score,
            "test_results": result.test_results if hasattr(result, 'test_results') else None
        }
        
        return self.answer

@register_check_minion
class CodiumCheckMinion(TestMinion):
    """Test Minion for verifying code solutions with stdin/stdout test cases"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def _process_test_cases(self, test_cases, entry_point):
        """Process test cases from metadata format to internal format"""
        if not test_cases or not isinstance(test_cases, dict):
            return []
            
        inputs = test_cases.get('input', [])
        outputs = test_cases.get('output', [])
        
        # Ensure we have matching input/output pairs
        return list(zip(inputs, outputs))
        
    async def _execute_test(self):
        """Execute test logic for input/output based problems"""
        feedback = []
        passed_count = 0
        total_tests = len(self.test_cases)
        test_results = []
        
        # Get the solution code
        solution = self.input.answer
        
        try:
            # Execute each test case
            for i, (input_data, expected_output) in enumerate(self.test_cases, 1):
                try:
                    # Run the code in a separate process
                    result = run_code_in_separate_process(solution, input_data)
                    
                    if result.stderr:
                        logger.warning(f"Test {i} produced stderr: {result.stderr}")
                    
                    # Compare outputs (strip both to handle trailing newlines)
                    if result.stdout.strip() == expected_output.strip():
                        passed_count += 1
                        test_results.append({
                            "test": f"Test {i}",
                            "input": input_data,
                            "expected": expected_output,
                            "actual": result.stdout,
                            "stderr": result.stderr,
                            "passed": True
                        })
                        logger.info(f"Test {i}/{total_tests} PASSED")
                    else:
                        error_msg = f"Test failed:\nInput: {input_data}\nExpected: {expected_output}\nGot: {result.stdout}"
                        if result.stderr:
                            error_msg += f"\nStderr: {result.stderr}"
                        feedback.append(error_msg)
                        test_results.append({
                            "test": f"Test {i}",
                            "input": input_data,
                            "expected": expected_output,
                            "actual": result.stdout,
                            "stderr": result.stderr,
                            "passed": False,
                            "error": error_msg
                        })
                        logger.error(f"Test {i}/{total_tests} FAILED: {error_msg}")
                
                except Exception as e:
                    error_msg = f"Test execution failed: {str(e)}"
                    feedback.append(error_msg)
                    test_results.append({
                        "test": f"Test {i}",
                        "passed": False,
                        "error": error_msg
                    })
                    logger.error(f"Test {i}/{total_tests} ERROR: {error_msg}")
                    
        except Exception as e:
            error_msg = f"Failed to execute solution: {str(e)}"
            feedback.append(error_msg)
            test_results.append({
                "test": "code execution",
                "passed": False,
                "error": error_msg
            })
            logger.error(f"Code execution failed: {error_msg}")
            passed_count = 0
        
        # Calculate score
        score = passed_count / total_tests if total_tests > 0 else 0.0
        
        # Log final results
        if score == 1.0:
            logger.info(f"All {total_tests} tests PASSED!")
        else:
            logger.warning(f"Tests completed: {passed_count}/{total_tests} passed (score: {score:.2f})")
        
        # Construct feedback dictionary
        self.answer = self.input.feedback = {
            "feedback": "\n".join(feedback) if feedback else "All tests passed!",
            "correct": (score == 1.0),
            "score": score,
            "test_results": test_results
        }
        
        return self.answer

