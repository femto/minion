import asyncio
import json
import os
import re

import aiofiles
from datasets import load_dataset
from pydantic import BaseModel
from tqdm.asyncio import tqdm

from metagpt.minion.brain import Brain
from metagpt.minion.minion import extract_number_from_string
from metagpt.minion.stats_storer import (
    JsonStatsStorer,
    MultipleStatsStorer,
    SqlStatsStorer,
)
from metagpt.minion.utils import compare_number_result


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


async def evaluate_aime(
    data,
    last_processed_id=0,
    to_processed_id=None,
    route="cot",
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

    with tqdm(total=total_count, desc="Evaluating") as pbar:
        for item in data:
            item_id = Item(id=item.get("ID", -1))

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


# Note: The solve_single_question function is not defined here.
# Make sure it's implemented elsewhere in your code.


async def solve_single_question(
    item,
    route="cot",
    stats_storer=None,
):
    question = item["Question"]
    correct_answer_str = item["Answer"]
    item_id = item.get("ID", -1)  # Extract the ID or use a default value

    # Extract the correct answer after '####'

    correct_answer = extract_answer(correct_answer_str)

    # Your solver logic
    user_answer_str = await solve_question(
        question,
        route=route,
        correct_answer=correct_answer,
        raw_correct_answer=correct_answer_str,
        item_id=item_id,
        stats_storer=stats_storer,
    )
    user_answer = extract_number_from_string(user_answer_str)

    if compare_number_result(extract_number_from_string(user_answer), extract_number_from_string(correct_answer)):
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
def load_ensemble_logic(file_path):
    with open(file_path, "r") as file:
        ensemble_logic = json.load(file)
    return ensemble_logic


# Sample solver function (you'll replace this with your actual logic)
async def solve_question(question, route=None, stats_storer=None, **kwargs):
    # Implement your problem-solving logic here
    # For example, this could be a math solver or text parser
    brain = Brain(
        stats_storer=stats_storer,
    )

    obs, score, *_ = await brain.step(
        query=question,
        route=route,
        ensemble_logic=load_ensemble_logic("aime_ensemble.json"),
        **kwargs
        # stats={},
        # stats_output="aime/stat_output.json"
    )
    # print(obs)
    return obs


async def main():
    # file_name = "aime.json"
    # data = load_json(file_name)

    data = load_dataset("qq8933/AIME_1983_2024", split="train")

    #
    json_storer = JsonStatsStorer("logs/stats_output.json")

    # tracker = AsyncStatsTracker(stats_db_url)
    # In your main function or wherever you set up your application

    sql_storer = SqlStatsStorer("postgresql+asyncpg://femtozheng@localhost:5432/aime1")
    await sql_storer.init_db()

    stats_storer = MultipleStatsStorer([json_storer, sql_storer])

    correct, count, matched_ids, mismatched_ids = await evaluate_aime(
        data,
        last_processed_id="1981-0",
        to_processed_id=None,
        concurrency_count=1,
        stats_storer=stats_storer,
        start_id=None,
        continue_process=True,
        run_filename="run_aime.json",
    )

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
