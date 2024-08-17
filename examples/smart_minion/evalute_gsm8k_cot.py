import asyncio
import json
import re

import aiofiles
from tqdm.asyncio import tqdm

from metagpt.minion.brain import Brain
from metagpt.minion.ensemble_logic import GSM8K_ENSEMBLE_LOGIC
from metagpt.minion.minion import extract_number_from_string


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
        return None  # Return None if no match is found


# Evaluate GSM8K task
async def evaluate_gsm8k(data):
    correct = 0
    count = 0
    total_count = len(data)
    matched_ids = []
    mismatch = []
    tasks = []

    last_processed_id = 394
    skip = True if last_processed_id else False

    async def process_batch(tasks, correct):
        results = await asyncio.gather(*tasks)
        for result in results:
            correct += result["result"]
            if result["result"] == 1:
                matched_ids.append(result["item_id"])
            else:
                mismatch.append(result)
        return correct

    async def save_run_info():
        run_info = {
            "last_processed_id": last_processed_id,
            "matched_ids": matched_ids,
            "mismatched_ids": mismatch,
            "correct": correct,
            "count": count,
            "correct_percentage": correct / count if count > 0 else 0,
        }
        async with aiofiles.open("run.json", "w") as f:
            await f.write(json.dumps(run_info, indent=4))

    with tqdm(total=total_count, desc="Evaluating") as pbar:
        for i, item in enumerate(data):
            item_id = item.get("idx", -1)

            # Skip items until the last processed item
            if skip:
                if item_id == last_processed_id:
                    skip = False
                continue

            count += 1
            tasks.append(solve_single_question(item))

            if len(tasks) == 6:
                correct = await process_batch(tasks, correct)
                tasks = []  # Reset tasks after processing
                pbar.set_postfix({"Correct": correct, "count": count})
                pbar.update(6)

                # Save running information after each batch
                await save_run_info()

        # Process remaining tasks
        if tasks:
            correct = await process_batch(tasks, correct)
            pbar.set_postfix({"Correct": correct})
            pbar.update(len(tasks))

            # Save running information after the final batch
            await save_run_info()

    return correct


async def solve_single_question(item):
    question = item["question"]
    correct_answer_str = item["answer"]
    item_id = item.get("idx", -1)  # Extract the ID or use a default value

    # Extract the correct answer after '####'

    correct_answer = extract_answer(correct_answer_str)

    # Your solver logic
    user_answer_str = await solve_question(question, route="cot")
    user_answer = extract_number_from_string(user_answer_str)

    if float(extract_number_from_string(user_answer) or "-10000") == float(extract_number_from_string(correct_answer)):
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


# Sample solver function (you'll replace this with your actual logic)
async def solve_question(question, route=None):
    # Implement your problem-solving logic here
    # For example, this could be a math solver or text parser
    brain = Brain()

    obs, score, *_ = await brain.step(query=question, route=route, ensemble_logic=GSM8K_ENSEMBLE_LOGIC)
    # print(obs)
    return obs
    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?",
    #     query_type="code_problem")
    # print(obs)


async def main():
    # file_name = "gsm8k_train.json"
    file_name = "gsm8k_test.json"
    data = load_jsonl(file_name)
    accuracy, matched_ids, mismatched_ids = await evaluate_gsm8k(data)

    print(f"Accuracy: {accuracy:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
