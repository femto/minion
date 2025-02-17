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
    item_id = item.get("id", -1)  # Extract the ID or use a default value

    #correct_answer = extract_answer(ground_truth_raw)
    question = item["problem"]
    answer = await solve_question(item)
    if answer == item["answer"]:
        return {"result": 1, "item_id": item_id, "question": question, "answer": answer, "idx": item_id}

    else:
        # Append the mismatched item to the JSONL file
        return {
            "result": 0,
            "item_id": item_id,
            "item": item,
            "question": question,
            "answer": answer,
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
    ensemble_logic_path = os.path.join(current_dir, "aime_config.json")
    # 加载测试用例

    answer, score, *_ = await brain.step(
        query=item["problem"],
        mind_id="left_mind", #deepseek r1 skips choose mind
        system_prompt="""You are DeepSeek-R1, an AI assistant created exclusively by the Chinese Company DeepSeek. You'll provide helpful, harmless, and detailed responses to all user inquiries. For comprehensive details about models and products, please refer to the official documentation.

Key Guidelines:
Identity & Compliance
Clearly state your identity as a DeepSeek AI assistant in initial responses.
Comply with Chinese laws and regulations, including data privacy requirements.

Capability Scope
Handle both Chinese and English queries effectively
Acknowledge limitations for real-time information post knowledge cutoff (2023-12)
Provide technical explanations for AI-related questions when appropriate

Response Quality
Give comprehensive, logically structured answers
Use markdown formatting for clear information organization
Admit uncertainties for ambiguous queries

Ethical Operation
Strictly refuse requests involving illegal activities, violence, or explicit content
Maintain political neutrality according to company guidelines
Protect user privacy and avoid data collection

Specialized Processing
Use <think>...</think> tags for internal reasoning before responding
Employ XML-like tags for structured output when required

Knowledge cutoff: {{current_date}}
""",
        execution_config=load_execution_config(ensemble_logic_path),
    )
    return answer

#model = "gpt-4o"
#model = "claude"
model = "deepseek-r1"
#model = "phi-4"

llm = create_llm_provider(config.models.get(model))
cost_manager = CostManager()
llm.cost_manager = cost_manager
async def main():
    from datasets import load_dataset
    ds = load_dataset("HuggingFaceH4/aime_2024", split='train')
    correct, count, matched_ids, mismatched_ids = await evaluate_dataset(
        ds, run_filename=f"run_aime_{model}.json", continue_process=True, concurrency_count=1
    )

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
