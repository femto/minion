import asyncio
import json
import os
import re
from collections import Counter

import aiofiles
import pandas as pd
from minion.llm import LLM
from minion.utils.cost_manager import CostManager
from pydantic import BaseModel
from tqdm.asyncio import tqdm

from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.main.stats_storer import (
    JsonStatsStorer,
    MultipleStatsStorer,
    SqlStatsStorer,
)


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
    return answer_str
    # Regular expression to find the answer after '####'
    match = re.search(r"####\s*(.*)", answer_str)
    if match:
        return match.group(1).strip()  # Extract and remove any surrounding whitespace
    else:
        return None  # Return None if no match is found


def roman_to_int(roman):
    roman_values = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
        "V": 5,
        "VI": 6,
        "VII": 7,
        "VIII": 8,
        "IX": 9,
        "X": 10,
        "XI": 11,
        "XII": 12,
    }
    return roman_values.get(roman.upper(), 0)


class Item(BaseModel):
    id: str
    arr: list[int] = None

    def __init__(self, **data):
        data["id"] = str(data["id"])
        super().__init__(**data)
        # Split the id into parts
        parts = self.id.split("-")

        # Convert the parts to integers, handling Roman numerals as needed
        self.arr = []
        for part in parts:
            try:
                self.arr.append(int(part))
            except ValueError:
                self.arr.append(roman_to_int(part))

    def __lt__(self, other):
        return self.arr < other.arr

    def __le__(self, other):
        return self.arr <= other.arr


cost_manager = CostManager()
llm = LLM()
llm.cost_manager = cost_manager


async def evaluate_dataset(
    data,
    last_processed_id=0,
    to_processed_id=None,
    route="python",
    concurrency_count=1,
    start_id=None,
    continue_process=False,
    run_filename=None,
    stats_storer=None,
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
        for index, item in data.iterrows():
            item_id = Item(id=index)

            if last_processed_id and item_id <= Item(id=last_processed_id):
                continue
            if start_id and item_id < Item(id=start_id):
                continue
            if to_processed_id and item_id > Item(id=to_processed_id):
                break

            count += 1
            tasks.append(solve_single_question(item, route=route, stats_storer=stats_storer))

            if len(tasks) == concurrency_count:
                correct, last_processed_item = await process_batch(tasks, correct)
                last_processed_id = last_processed_item["item_id"]
                tasks = []  # Reset tasks after processing
                pbar.set_postfix({"Correct": correct, "count": count, "Last ID": last_processed_id})
                pbar.update(concurrency_count)

                # Save running information after each batch
                await save_run_info(filename=run_filename, last_processed_id=last_processed_id)

        # Process remaining tasks
        if tasks:
            correct, last_processed_item = await process_batch(tasks, correct)
            last_processed_id = last_processed_item["item_id"]
            pbar.set_postfix({"Correct": correct, "count": count, "Last ID": last_processed_id})
            pbar.update(len(tasks))

            # Save running information after the final batch
            await save_run_info(filename=run_filename, last_processed_id=last_processed_id)

    return correct, count, matched_ids, mismatch


def find_expression_end(s):
    paren_count = 0
    num_count = 0
    op_count = 0
    start = -1

    for i, char in enumerate(s):
        if start == -1:
            if char.isdigit() or char == "(":
                start = i
            elif char not in " \n":  # Skip leading spaces and newlines
                paren_count = 0
                num_count = 0
                op_count = 0
                start = -1

        if start != -1:
            if char == "(":
                paren_count += 1
            elif char == ")":
                paren_count -= 1
            elif char.isdigit() and (i == len(s) - 1 or not s[i + 1].isdigit()):
                num_count += 1
            elif char in "+-*/":
                op_count += 1
            elif char not in " ()+-*/0123456789":
                paren_count = 0
                num_count = 0
                op_count = 0
                start = -1

            if paren_count == 0 and num_count == 4 and op_count == 3:
                return start, i + 1

    return None, None


def extract_solution(solution_str):
    start, end = find_expression_end(solution_str)
    if start is None or end is None:
        return None

    expr = solution_str[start:end].strip()

    # Ensure we have 4 numbers and 3 operators
    numbers = re.findall(r"\d+", expr)
    operators = re.findall(r"[\+\-\*\/]", expr)
    if len(numbers) != 4 or len(operators) != 3:
        return None

    return expr


def evaluate_expression(expr, numbers):
    # Convert all numbers to integers
    numbers = [int(num) for num in numbers]

    # Remove all whitespace and parentheses for number checking
    expr_clean = re.sub(r"[\s\(\)]", "", expr)

    # Extract all numbers from the expression
    expr_numbers = [int(num) for num in re.findall(r"\d+", expr_clean)]

    # Check if the numbers in the expression match the given numbers
    if Counter(expr_numbers) != Counter(numbers):
        return False

    # Evaluate the expression
    try:
        result = eval(expr)
        return abs(result - 24) < 1e-6  # Allow for small floating-point errors
    except:
        return False


def verify_game24_solution(question, user_answer):
    # Extract numbers from the question
    numbers = re.findall(r"\d+", question)

    # Ensure we have exactly 4 numbers
    if len(numbers) != 4:
        return False

    # Extract the solution from the user_answer
    solution = extract_solution(user_answer)
    if not solution:
        return False

    # Verify the solution
    return evaluate_expression(solution, numbers)


async def solve_single_question(
    item,
    route="cot",
    stats_storer=None,
):
    question = item["Puzzles"]
    correct_answer_str = None  # item["Answer"]
    item_id = item.name  # the item_id for update_stats

    # Extract the correct answer after '####'

    correct_answer = None  # extract_answer(correct_answer_str)

    # Your solver logic
    user_answer_str = await solve_question(
        f"what's the solution for  game of 24 for {question}",
        route=route,
        correct_answer=correct_answer,
        raw_correct_answer=correct_answer_str,
        item_id=item_id,
        stats_storer=stats_storer,
    )
    user_answer = user_answer_str

    if verify_game24_solution(
        question,
        user_answer,
    ):
        return {"result": 1, "item_id": item_id, "question": question, "user_answer": user_answer, "idx": item_id}

    else:
        # Append the mismatched item to the JSONL file
        return {
            "result": 0,
            "item_id": item_id,
            "question": question,
            "correct_answer": correct_answer_str,
            "user_answer": user_answer,
            "idx": item_id,
        }


# Load ensemble logic from JSON files
def load_execution_config(file_path):
    with open(file_path, "r") as file:
        ensemble_logic = json.load(file)
    return ensemble_logic


# Sample solver function (you'll replace this with your actual logic)
async def solve_question(question, route=None, stats_storer=None, **kwargs):
    # Implement your problem-solving logic here
    # For example, this could be a math solver or text parser
    brain = Brain(stats_storer=stats_storer, python_env=RpycPythonEnv(ports=3007), llm=llm)

    obs, score, *_ = await brain.step(
        query=question,
        route=route,
        execution_config=load_execution_config("game_24_ensemble.json"),
        **kwargs
        # stats={},
        # stats_output="aime/stat_output.json"
    )
    # print(obs)
    return obs


async def main():
    file_name = "game_24.csv"
    # data = load_json(file_name)
    data = pd.read_csv(file_name)
    data = data.sort_index(ascending=False).reset_index(drop=True)
    #
    json_storer = JsonStatsStorer("logs/game24_stats_output.json")

    # tracker = AsyncStatsTracker(stats_db_url)
    # In your main function or wherever you set up your application

    sql_storer = SqlStatsStorer("postgresql+asyncpg://femtozheng@localhost:5432/game24")
    await sql_storer.init_db()

    stats_storer = MultipleStatsStorer([json_storer, sql_storer])

    correct, count, matched_ids, mismatched_ids = await evaluate_dataset(
        data,
        concurrency_count=1,
        stats_storer=stats_storer,
        continue_process=True,
        run_filename="run_game24_reverse.json",
    )

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
