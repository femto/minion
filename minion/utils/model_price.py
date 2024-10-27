import json

from minion.const import MODEL_PRICES_PATH


def get_model_price(model_name):
    """从JSON文件获取模型价格信息，并缓存结果"""
    if not hasattr(get_model_price, "model_prices"):
        with open(MODEL_PRICES_PATH, "r") as f:
            get_model_price.model_prices = json.load(f)
    model_prices = get_model_price.model_prices

    model_info = model_prices.get(model_name)
    if model_info:
        return {
            "prompt": model_info.get("input_cost_per_token", 0),
            "completion": model_info.get("output_cost_per_token", 0),
        }
    return None
