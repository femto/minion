import asyncio
import json
import os
import re
import sys
import threading
import time
from typing import List, Dict, Tuple, Optional, Any
from contextlib import redirect_stdout
from io import StringIO

import aiofiles
import numpy as np
from tqdm.asyncio import tqdm

from minion.configs.config import config
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.utils.syncheck import run_with_timeout
from minion.utils.utils import extract_number_from_string
from minion.providers import create_llm_provider
from minion.providers.cost import CostManager
from minion.utils.process import run_code_in_separate_process

# Load JSONL file
def load_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


# Load JSONL file
def load_jsonl(file_path):
    data = []
    with open(file_path, "r") as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data


def extract_answer(answer_str):
    # Regular expression to find the answer after '####'
    match = re.search(r"####\s*(.*)", answer_str)
    if match:
        return match.group(1).strip()  # Extract and remove any surrounding whitespace
    else:
        return answer_str  # Return None if no match is found

async def evaluate_dataset(
    data,
    last_processed_id=None,
    start_id=None,
    to_processed_id=None,
    route="cot",
    run_filename=None,
    continue_process=False,
    concurrency_count=1,
):
    correct = 0
    count = 0
    total_count = len(data)
    matched_ids = []
    mismatch = []
    tasks = []

    async def process_batch(tasks, correct):
        results = await asyncio.gather(*tasks)
        for result in results:
            correct += result["result"]
            if result["result"] == 1:
                matched_ids.append(result["item_id"])
            else:
                mismatch.append(result)
        last_processed_item = results[-1]  # Get the last processed item
        return correct, last_processed_item

    async def read_json_file(filename):
        async with aiofiles.open(filename, "r") as f:
            contents = await f.read()
            data = json.loads(contents)
        return data

    async def save_run_info(filename, last_processed_id):
        run_info = {
            "last_processed_id": last_processed_id,
            "matched_ids": matched_ids,
            "mismatched_ids": mismatch,
            "correct": correct,
            "count": count,
            "correct_percentage": correct / count if count > 0 else 0,
            "total_prompt_tokens": cost_manager.total_prompt_tokens,
            "total_completion_tokens": cost_manager.total_completion_tokens,
            "total_cost": cost_manager.total_cost,
        }
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(run_info, indent=4))

    if continue_process and os.path.exists(run_filename):
        async with aiofiles.open(run_filename, "r") as f:
            run_info = json.loads(await f.read())
        last_processed_id = run_info["last_processed_id"]
        matched_ids = run_info["matched_ids"]
        mismatch = run_info["mismatched_ids"]
        correct = run_info["correct"]
        count = run_info["count"]
        cost_manager.total_prompt_tokens = run_info.get("total_prompt_tokens", 0)
        cost_manager.total_completion_tokens = run_info.get("total_completion_tokens", 0)
        cost_manager.total_cost = run_info.get("total_cost", 0)

    with tqdm(total=total_count, desc="Evaluating") as pbar:
        for i, item in enumerate(data):
            item_id = i
            item["idx"] = i
            if last_processed_id is not None and item_id <= last_processed_id:
                continue
            if start_id and item_id < start_id:
                continue
            if to_processed_id and item_id > to_processed_id:
                break

            count += 1
            tasks.append(solve_single_question(item, route=route))

            if len(tasks) == concurrency_count:
                correct, last_processed_item = await process_batch(tasks, correct)
                last_processed_id = last_processed_item["item_id"]
                tasks = []  # Reset tasks after processing
                pbar.set_postfix({"Correct": correct, "count": count})
                pbar.update(concurrency_count)

                # Save running information after each batch
                await save_run_info(filename=run_filename, last_processed_id=last_processed_id)

        # Process remaining tasks
        if tasks:
            correct, last_processed_item = await process_batch(tasks, correct)
            last_processed_id = last_processed_item["item_id"]
            pbar.set_postfix({"Correct": correct})
            pbar.update(len(tasks))

            # Save running information after each batch
            await save_run_info(filename=run_filename, last_processed_id=last_processed_id)

    return correct, count, matched_ids, mismatch

PASS = "PASS"
FAIL = "FAIL"

def check_solution(solution, test):
    print(f"solution: {solution}")

    try:
        # Get test cases from the dictionary
        inputs = test.get('input', [])
        outputs = test.get('output', [])

        # Run each test case
        for input_data, expected_output in zip(inputs, outputs):
            try:
                # Run the code in a separate process
                result = run_code_in_separate_process(solution, input_data)
                
                if result.stderr:
                    print(f"Test produced stderr: {result.stderr}")
                
                # Compare outputs (strip both to handle trailing newlines)
                if result.stdout.strip() != expected_output.strip():
                    return (FAIL, f"Test failed:\nInput: {input_data}\nExpected: {expected_output}\nGot: {result.stdout}\nStderr: {result.stderr if result.stderr else 'None'}")
            except Exception as e:
                return (FAIL, f"Test execution failed: {str(e)}")

        return (PASS, "Solution passed all test cases.")

    except TimeoutError:
        return (FAIL, "Execution timeout. Please check if your solution contains infinite loops or time-consuming operations.")
    except Exception as e:
        # Record detailed error information
        error_message = f"Error: {str(e)}.\n Solution: {solution}.\n Test: {test}"
        
        # Write error information to error.log file
        with open('error.log', 'a', encoding='utf-8') as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_message}\n")
            
        return (FAIL, error_message)

async def solve_single_question(item, route="cot"):
    question = item['description']
    #ground_truth_raw = item["answer"]
    solutions = item["solutions"]
    public_tests = item['public_tests']
    private_tests = item['private_tests']
    item_id = item.get("idx", -1)  # Extract the ID or use a default value

    # Extract the correct answer after '####'

    #correct_answer = extract_answer(ground_truth_raw)

    answer = await solve_question(item)
    ret = check_solution(answer, private_tests)
    if ret[0] == PASS:
        return {"result": 1, "item_id": item_id, "question": question, "answer": answer, "idx": item_id}

    else:
        # Append the mismatched item to the JSONL file
        return {
            "result": 0,
            "item_id": item_id,
            "item": item,
            "question": question,
            "answer": answer,
            "reason": ret[1],
            "idx": item_id,
        }


# Load ensemble logic from JSON files
def load_execution_config(file_path):
    with open(file_path, "r") as file:
        ensemble_logic = json.load(file)
    return ensemble_logic

async def solve_question(item):
    brain = Brain(stats_storer=None, python_env=RpycPythonEnv(ports=3007), llm=llm)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ensemble_logic_path = os.path.join(current_dir, "code_contests_config.json")
    # 加载测试用例
    public_tests = item['public_tests']
    metadata = {"test_cases": public_tests}
    answer, score, *_ = await brain.step(
        query="""Please provide a complete function implementation including:
- Full function definition
- All necessary logic
- Proper return statement
- Handle all edge cases
Here is the function to implement:
""" + item['description'],
    #entry_point="main", #used in extract_python
        pre_processing="problem_reflect",
        dataset="code_contests",
        execution_config=load_execution_config(ensemble_logic_path),
        metadata=metadata
    )
    return answer

#model = "gpt-4o-mini"
model = "default"

llm = create_llm_provider(config.models.get(model))
cost_manager = CostManager()
llm.cost_manager = cost_manager
async def main():
    from datasets import load_dataset
    validation_data = load_dataset("deepmind/code_contests", split='valid')
    test_data = load_dataset("deepmind/code_contests", split='test')

    correct, count, matched_ids, mismatched_ids = await evaluate_dataset(
        validation_data, run_filename=f"run_code_contests_{model}.json", continue_process=True, concurrency_count=1
    )

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
