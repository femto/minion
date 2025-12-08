import json
from typing import Optional, Dict, Any

from minion.const import MODEL_PRICES_PATH

# Default context window size (128K tokens)
DEFAULT_CONTEXT_WINDOW = 128000

# Cache for model prices data
_model_prices_cache: Optional[Dict[str, Any]] = None


def _load_model_prices() -> Dict[str, Any]:
    """Load and cache model prices data from JSON file."""
    global _model_prices_cache
    if _model_prices_cache is None:
        with open(MODEL_PRICES_PATH, "r") as f:
            _model_prices_cache = json.load(f)
    return _model_prices_cache


def get_model_price(model_name: str) -> Optional[Dict[str, float]]:
    """Get model price information from JSON file with caching.

    Args:
        model_name: The name of the model (e.g., "gpt-4o", "claude-3-opus")

    Returns:
        Dictionary with "prompt" and "completion" costs per token, or None if not found.
    """
    model_prices = _load_model_prices()
    model_info = model_prices.get(model_name)
    if model_info:
        return {
            "prompt": model_info.get("input_cost_per_token", 0),
            "completion": model_info.get("output_cost_per_token", 0),
        }
    return None


def get_model_context_window(model_name: str) -> Dict[str, int]:
    """Get model's context window information.

    Args:
        model_name: The name of the model (e.g., "gpt-4o", "claude-3-opus")

    Returns:
        Dictionary with context window info:
        - max_input_tokens: Maximum input tokens (context window)
        - max_output_tokens: Maximum output tokens
        - max_tokens: Total max tokens (if available)

        Returns default values if model not found.
    """
    model_prices = _load_model_prices()
    model_info = model_prices.get(model_name)

    if model_info:
        return {
            "max_input_tokens": model_info.get("max_input_tokens", DEFAULT_CONTEXT_WINDOW),
            "max_output_tokens": model_info.get("max_output_tokens", 4096),
            "max_tokens": model_info.get("max_tokens", model_info.get("max_output_tokens", 4096)),
        }

    # Return defaults if model not found
    return {
        "max_input_tokens": DEFAULT_CONTEXT_WINDOW,
        "max_output_tokens": 4096,
        "max_tokens": 4096,
    }
