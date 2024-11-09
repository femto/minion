import base64
import io
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Union

import aiofiles
from nltk.corpus import wordnet
from PIL import Image

from minion.utils.custom_decoder import CustomDecoder
from minion.utils.sanitize import sanitize


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


def extract_json(text: str) -> Union[str, dict]:
    """
    从文本中提取 JSON 内容，支持处理嵌套的代码块
    
    Args:
        text: 输入文本，可能包含 JSON 字符串或被 ``` 包裹的 JSON
        
    Returns:
        解析后的 JSON 对象或原始字符串
    """
    text = text.strip()
    
    # 处理被多层 ``` 包裹的情况
    if text.startswith('```'):
        # 移除开头的 ```
        text = text[3:]
        # 检查是否有语言标识符（如 json）
        first_line_end = text.find('\n')
        if first_line_end != -1:
            first_line = text[:first_line_end].strip()
            if first_line.lower() == 'json':
                text = text[first_line_end + 1:].strip()
        
        # 移除结尾的 ```
        if text.endswith('```'):
            text = text[:-3].strip()
    
    try:
        # 尝试解析 JSON
        dict = CustomDecoder(strict=False).decode(text)
        return json.dumps(dict)
        #return json.dumps(json.loads(text))
    except json.JSONDecodeError:
        # 如果解析失败，尝试在文本中查找 JSON 对象
        start_brace = text.find('{')
        end_brace = text.rfind('}')
        
        if start_brace != -1 and end_brace != -1:
            try:
                json_str = text[start_brace:end_brace + 1]
                dict = CustomDecoder(strict=False).decode(json_str)
                return json.dumps(dict)
            except json.JSONDecodeError:
                pass
                
        return text

def extract_last_number(text: str):
    """Clean text and extract a single number"""
    matches = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?|\d+\.\d+", text)
    if matches:
        last_number = matches[-1].replace(",", "")
        try:
            return float(last_number)
        except ValueError:
            return None
    else:
        return None


def extract_number_from_string(price_str):
    # use deepseek eval logic, only looks last number
    return extract_last_number(str(price_str))
    # if isinstance(price_str, int) or isinstance(price_str, float):
    #     return price_str
    #
    # price_str = price_str or ""
    # # Remove commas from the string
    # price_str = price_str.replace(",", "")
    #
    # try:
    #     # Regular expression to match all numeric values
    #     matches = re.findall(r"\d+(?:\.\d+)?", price_str)
    #
    #     if len(matches) == 1:
    #         # Only one number found, return it as int or float
    #         number_str = matches[0]
    #         return float(number_str) if "." in number_str else int(number_str)
    #     elif len(matches) > 1:
    #         # More than one number found, handle accordingly
    #         logger.warning(f"Multiple numbers found in string: {matches}, str: {price_str}")
    #         raise ValueError("Multiple numbers found")
    #         # return None
    #     else:
    #         return None  # Return None if no number is found
    # except Exception as e:
    #     logger.error("extract_number_from_string failed: " + str(e) + f", str: {price_str}")
    #     return None  # Return None if there is an error


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


# minion part
def extract_content(text):
    pattern = r"\[CONTENT\](.*?)\[/CONTENT\]"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def snake_case_to_camel_case(snake_str: str, suffix: str = "Minion") -> str:
    # Split the snake case string by underscores and capitalize each word
    components = snake_str.split("_")
    # Capitalize each component and join them
    camel_case_str = "".join(x.capitalize() for x in components)
    # Add the suffix
    camel_case_with_suffix = camel_case_str + suffix
    return camel_case_with_suffix


def camel_case_to_snake_case(camel_str: str, suffix: str = "Minion") -> str:
    # Remove the suffix
    if camel_str.endswith(suffix):
        camel_str = camel_str[: -len(suffix)]

    # Find all places where a lowercase letter is followed by an uppercase letter
    snake_case_str = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()
    return snake_case_str


def process_image(image_input):
    # Check if it's already a base64 string
    try:
        base64.b64decode(image_input)
        return image_input  # It's already base64, return as is
    except:
        pass  # Not base64, continue to other checks

    # Check if it's a file path
    if isinstance(image_input, str):
        try:
            path = Path(image_input)
            if path.is_file():
                with open(path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode("utf-8")
        except:
            pass  # Not a valid file path, continue to other checks

    # Check if it's a PIL Image
    if isinstance(image_input, Image.Image):
        buffered = io.BytesIO()
        image_input.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    # If we've reached here, the input is not in a recognized format
    raise ValueError("Input is not a recognized image format (base64 string, file path, or PIL Image)")

def main():
    result = get_synonyms("Trigonometry")
    print(result)


if __name__ == "__main__":
    main()
