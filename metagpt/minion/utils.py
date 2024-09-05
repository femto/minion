import json
import os
import re
from difflib import SequenceMatcher

import aiofiles
from nltk.corpus import wordnet

from metagpt.logs import logger


def extract_id_and_command(full_command):
    # Extract the ID using regex
    match = re.match(r"<id>(.+?)</id>(.*)", full_command, re.DOTALL)
    if match:
        full_id = match.group(1)
        command = match.group(2).strip()
        return full_id, command
    else:
        return "DEFAULT_GLOBAL", full_command


def replace_placeholders_with_env(config):
    # Define a regex pattern to match placeholders like "${ENV_VAR}"
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replace_in_value(value):
        if isinstance(value, str):
            # Search for the placeholder pattern
            match = pattern.search(value)
            if match:
                env_var = match.group(1)
                return os.getenv(env_var, value)  # Replace with env var if available, otherwise keep the original value
        return value

    def recursive_replace(obj):
        if isinstance(obj, dict):
            return {key: recursive_replace(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [recursive_replace(item) for item in obj]
        else:
            return replace_in_value(obj)

    return recursive_replace(config)


def extract_number_from_string(price_str):
    if isinstance(price_str, int) or isinstance(price_str, float):
        return price_str

    price_str = price_str or ""
    # Remove commas from the string
    price_str = price_str.replace(",", "")

    try:
        # Regular expression to match all numeric values
        matches = re.findall(r"\d+(?:\.\d+)?", price_str)

        if len(matches) == 1:
            # Only one number found, return it as int or float
            number_str = matches[0]
            return float(number_str) if "." in number_str else int(number_str)
        elif len(matches) > 1:
            # More than one number found, handle accordingly
            logger.warning(f"Multiple numbers found in string: {matches}, str: {price_str}")
            raise ValueError("Multiple numbers found")
            # return None
        else:
            return None  # Return None if no number is found
    except Exception as e:
        logger.error("extract_number_from_string failed: " + str(e) + f", str: {price_str}")
        return None  # Return None if there is an error


def compare_number_result(result, correct_answer, tolerance=0.0):
    try:
        return abs(float(result) - float(correct_answer)) <= tolerance
    except Exception:
        return False


async def read_json_file(filename):
    async with aiofiles.open(filename, "r") as f:
        contents = await f.read()
        data = json.loads(contents)
    return data


async def save_stats_async(stats, output_file_path):
    """Asynchronously save stats to a JSON file."""
    async with aiofiles.open(output_file_path, "w") as output_file:
        await output_file.write(json.dumps(stats, indent=4))
    # print(f"Stats saved to {output_file_path}")


# Function to find synonyms
def get_synonyms(word):
    synonyms = set()
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            synonyms.add(lemma.name().lower())
    return synonyms


# Function to preprocess names for synonym replacement
def preprocess_name(name, synonym_map):
    words = name.split()
    preprocessed_words = [synonym_map.get(word.lower(), word.lower()) for word in words]
    return " ".join(preprocessed_words)


synonym_map = {
    "cot": "cot",
    "programme": "plan",
    "plan": "plan",
    "architectural_plan": "plan",
    "project": "plan",
    "contrive": "plan",
    "design": "plan",
    "be_after": "plan",
    "program": "plan",
    "python": "python",
    "math": "math",
    "mathematics": "math",
    "maths": "math",
}


# Function to find the most similar minion considering synonyms
def most_similar_minion(input_name, minions):
    # import nltk
    # nltk.download('wordnet')

    max_similarity = 0
    best_match = None

    # Build a synonym map
    # synonym_map = {}
    # for minion in minions:
    #     for word in minion.split():
    #         for synonym in get_synonyms(word):
    #             synonym_map[synonym] = word.lower()

    # Preprocess input_name and minions
    input_name_preprocessed = preprocess_name(input_name, synonym_map)

    for minion in minions:
        minion_preprocessed = preprocess_name(minion, synonym_map)
        similarity = SequenceMatcher(None, input_name_preprocessed, minion_preprocessed).ratio()

        if similarity > max_similarity:
            max_similarity = similarity
            best_match = minion

    return best_match


def main():
    result = get_synonyms("Trigonometry")
    print(result)


if __name__ == "__main__":
    main()
