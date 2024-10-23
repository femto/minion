import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field

class LLMConfig(BaseModel):
    api_type: str
    base_url: str
    api_key: str
    temperature: float

class Config(BaseModel):
    default: LLMConfig
    deepseek_chat: LLMConfig = Field(alias="deepseek-chat")
    gpt_4o: LLMConfig = Field(alias="gpt-4o")
    gpt_4o_mini: LLMConfig = Field(alias="gpt-4o-mini")
    
    class Config:
        allow_population_by_field_name = True

def load_config() -> Config:
    # 定义配置文件路径
    base_config_path = Path(__file__).parent / "default.yaml"
    user_config_path = Path.home() / ".minion/config.yaml"

    # 加载基础配置
    config_dict: Dict[str, Any] = {}
    if base_config_path.exists():
        with base_config_path.open("r") as f:
            config_dict = yaml.safe_load(f)

    # 如果用户配置文件存在，则加载并合并
    if user_config_path.exists():
        with user_config_path.open("r") as f:
            user_config = yaml.safe_load(f)
        
        # 合并配置，用户配置优先级更高
        config_dict.update(user_config)

    # 将字典转换为 Pydantic 模型
    return Config(**config_dict)

# 创建一个全局的配置对象
config = load_config()
