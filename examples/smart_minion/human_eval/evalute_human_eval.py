import asyncio
import json
import os
import re
import threading
import time
from typing import List, Dict, Tuple, Optional, Any

import aiofiles
import numpy as np
from tqdm.asyncio import tqdm

from minion.configs.config import config
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.main.utils import extract_number_from_string
from minion.providers import create_llm_provider
from minion.providers.cost import CostManager


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
    last_processed_id=0,
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
                pbar.update(6)

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

class TimeoutError(Exception):
    pass

def run_with_timeout(func, args, timeout):
    result = []
    def target():
        try:
            result.append(func(*args))
        except Exception as e:
            result.append(e)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("Function execution timed out")
    if isinstance(result[0], Exception):
        raise result[0]
    return result[0]

def check_solution(solution, test, entry_point):
    print(f"solution: {solution}")

    try:
        # 定义一个包含所有必要模块的全局字典
        global_dict = {
            'math': __import__('math'),
            'hashlib': __import__('hashlib'),
            're': __import__('re'),
            'List': List,
            'Dict': Dict,
            'Tuple': Tuple,
            'Optional': Optional,
            'Any': Any
        }
        if entry_point == "decode_cyclic":
            solution = "\n\ndef encode_cyclic(s: str):\n    \"\"\"\n    returns encoded string by cycling groups of three characters.\n    \"\"\"\n    # split string to groups. Each of length 3.\n    groups = [s[(3 * i):min((3 * i + 3), len(s))] for i in range((len(s) + 2) // 3)]\n    # cycle elements in each group. Unless group has fewer elements than 3.\n    groups = [(group[1:] + group[0]) if len(group) == 3 else group for group in groups]\n    return \"\".join(groups)" + "\n\n" + solution
        elif entry_point == "decode_shift":
            solution = "\n\ndef encode_shift(s: str):\n    \"\"\"\n    returns encoded string by shifting every character by 5 in the alphabet.\n    \"\"\"\n    return \"\".join([chr(((ord(ch) + 5 - ord(\"a\")) % 26) + ord(\"a\")) for ch in s])\n\n\n" + solution
        elif entry_point == "find_zero":
            solution = "\n\ndef poly(xs: list, x: float):\n    return sum(coeff * (x ** i) for i, coeff in enumerate(xs))\n\n" + solution
        # 执行解决方案
        exec(solution, global_dict)

        # 确保入口点函数已定义
        if entry_point not in global_dict:
            raise ValueError(f"函数 {entry_point} 在解决方案中未定义。")

        # 执行测试用例
        exec(test, global_dict)

        # 获取检查函数
        check = global_dict["check"]

        # 运行检查函数，设置超时时间为5秒
        result = run_with_timeout(check, (global_dict[entry_point],), 120)

        if result is None:
            result = (PASS, "解决方案通过了所有测试用例。")

    except TimeoutError:
        result = (FAIL, "执行超时。请检查您的解决方案是否包含无限循环或过于耗时的操作。")
    except Exception as e:
        # 记录详细的错误信息
        error_message = f"错误: {str(e)}.\n 解决方案: {solution}.\n 测试: {test}"
        result = (FAIL, error_message)

        # 将错误信息写入error.log文件
        with open('error.log', 'a', encoding='utf-8') as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_message}\n")

    return result

async def solve_single_question(item, route="cot"):
    question = item["prompt"]
    #ground_truth_raw = item["answer"]
    canonical_solution = item["canonical_solution"]
    entry_point = item["entry_point"]
    test = item["test"]
    item_id = item.get("idx", -1)  # Extract the ID or use a default value

    # Extract the correct answer after '####'

    #correct_answer = extract_answer(ground_truth_raw)

    # Your solver logic
    answer = await solve_question(question)
    ret = check_solution(answer, test, entry_point)
    if ret[0] == PASS:
        return {"result": 1, "item_id": item_id, "question": question, "answer": answer, "idx": item_id}

    else:
        # Append the mismatched item to the JSONL file
        return {
            "result": 0,
            "item_id": item_id,
            "question": question,
            "canonical_solution": canonical_solution,
            "test": test,
            "answer": answer,
            "reason": ret[1],
            "idx": item_id,
        }


# Load ensemble logic from JSON files
def load_execution_config(file_path):
    with open(file_path, "r") as file:
        ensemble_logic = json.load(file)
    return ensemble_logic

async def solve_question(question, route=None):
    # Implement your problem-solving logic here
    # For example, this could be a math solver or text parser
    brain = Brain(stats_storer=None, python_env=RpycPythonEnv(ports=3007), llm=llm)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    ensemble_logic_path = os.path.join(current_dir, "human_eval_config.json")
    obs, score, *_ = await brain.step(query=question, execution_config=load_execution_config(ensemble_logic_path))
    # print(obs)
    return obs


llm = create_llm_provider(config.models.get("default"))
cost_manager = CostManager()
llm.cost_manager = cost_manager
async def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.join(current_dir, "human_eval_test.jsonl")
    data = load_jsonl(file_name)
    # data = await load_data_sample(file_name, samples=1055)

    correct, count, matched_ids, mismatched_ids = await evaluate_dataset(
        data, run_filename="run_human_eval_deepseek.json", continue_process=True, concurrency_count=60
    )

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
