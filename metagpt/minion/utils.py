import os
import re


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
            return None
        else:
            return None  # Return None if no number is found
    except Exception as e:
        logger.error("extract_number_from_string failed: " + str(e) + f", str: {price_str}")
        return None  # Return None if there is an error
