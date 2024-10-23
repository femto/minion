import ell
from openai import OpenAI

from minion.const import MINION_ROOT


@ell.simple(model="gpt-4o-mini")
def hello(world: str):
    """You are a helpful assistant""" # System prompt
    name = world.capitalize()
    return f"What's 3+5? {name}!" # User prompt
ell.init(store=f'{MINION_ROOT}/logs', autocommit=True, verbose=True)
hello("world", client=OpenAI(api_key="sk-MVs9hGwlAof9EoVSC9A3A382940d4212BcD5B97cEc7f9dBc",
  base_url= "https://oneapi.deepwisdom.ai/v1"), api_params=dict(model="deepseek-chat", temperature=0.7))