import asyncio
import json
import re

import aiofiles
from tqdm.asyncio import tqdm

from metagpt.minion.brain import Brain
from metagpt.minion.minion import extract_number_from_string


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


async def evaluate_aime(data, last_processed_id=0, to_processed_id=None, route="cot"):
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
        async with aiofiles.open("run_aime.json", "w") as f:
            await f.write(json.dumps(run_info, indent=4))

    with tqdm(total=total_count, desc="Evaluating") as pbar:
        for i, item in enumerate(data):
            item_id = item.get("idx", -1)

            if item_id <= last_processed_id:
                continue
            if to_processed_id and item_id > to_processed_id:
                break

            count += 1
            tasks.append(solve_single_question(item, route=route))

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

    return correct, count, matched_ids, mismatch


async def solve_single_question(item, route="cot"):
    question = item["question"]
    correct_answer_str = item["answer"]
    item_id = item.get("idx", -1)  # Extract the ID or use a default value

    # Extract the correct answer after '####'

    correct_answer = extract_answer(correct_answer_str)

    # Your solver logic
    user_answer_str = await solve_question(question, route=route)
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


# Load ensemble logic from JSON files
def load_ensemble_logic(file_path):
    with open(file_path, "r") as file:
        ensemble_logic = json.load(file)
    return ensemble_logic


# Sample solver function (you'll replace this with your actual logic)
async def solve_question(question, route=None):
    # Implement your problem-solving logic here
    # For example, this could be a math solver or text parser
    brain = Brain()

    obs, score, *_ = await brain.step(
        query=question, route=route, ensemble_logic=load_ensemble_logic("aime_ensemble.json")
    )
    # print(obs)
    return obs


async def main():
    file_name = "aime.json"
    data = load_json(file_name)

    correct, count, matched_ids, mismatched_ids = await evaluate_aime(data, last_processed_id=3, to_processed_id=4)

    print(f"Accuracy: {correct/count:.2%}")
    print(f"Mismatched IDs: {mismatched_ids}")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
# Example usage
