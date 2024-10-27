import os

import pytest

import minion.const
from minion.configs import config as config_module


@pytest.fixture
def sample_env(tmp_path):
    env_file = tmp_path / ".env"
    env_content = """
    OPENAI_API_KEY=sk-test-openai-key
    ANTHROPIC_API_KEY=sk-test-anthropic-key
    LITELLM_API_KEY=sk-test-litellm-key
    LLM_API_KEY=sk-test-llm-key
    LLM_BASE_URL=https://test-llm-base-url.com
    CLAUDE_BASE_URL=https://test-claude-base-url.com
    CLAUDE_API_KEY=sk-test-claude-key
    DEFAULT_BASE_URL=https://test-default-base-url.com
    DEFAULT_API_KEY=sk-test-default-key
    """
    env_file.write_text(env_content)
    return env_file


@pytest.fixture
def sample_config(tmp_path, sample_env):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.yaml"
    config_content = """
    env_file:
      - ../.env

    llm:
      api_key: "${LLM_API_KEY}"
      model: "deepseek-chat"
      base_url: "${LLM_BASE_URL}"

    models:
      "claude-3-5-sonnet-20240620":
        api_type: "openai"
        base_url: "${CLAUDE_BASE_URL}"
        api_key: "${CLAUDE_API_KEY}"
        temperature: 0.7
      "default":
        api_type: "openai"
        base_url: "${DEFAULT_BASE_URL}"
        api_key: "${DEFAULT_API_KEY}"
        model: "deepseek-chat"
        temperature: 0
    """
    config_file.write_text(config_content)
    return config_file


def test_load_config(sample_config, sample_env, monkeypatch):
    # 清除可能影响测试的环境变量
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LITELLM_API_KEY",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "CLAUDE_BASE_URL",
        "CLAUDE_API_KEY",
        "DEFAULT_BASE_URL",
        "DEFAULT_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    # 模拟 MINION_ROOT
    mock_minion_root = sample_config.parent.parent
    monkeypatch.setattr(minion.const, "MINION_ROOT", mock_minion_root)

    # 设置 HOME 环境变量
    monkeypatch.setenv("HOME", str(mock_minion_root))

    # 修改工作目录
    original_cwd = os.getcwd()
    os.chdir(mock_minion_root)

    try:
        # 重新加载配置，传入模拟的 root_path，并设置 override_env 为 True
        config_module.reload_config(root_path=mock_minion_root, override_env=True)

        # 立即验证环境变量是否被正确设置
        assert os.environ.get("OPENAI_API_KEY") == "sk-test-openai-key"
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-test-anthropic-key"
        assert os.environ.get("LITELLM_API_KEY") == "sk-test-litellm-key"

        # 验证配置
        assert isinstance(config_module.config, config_module.Config)
        assert config_module.config.llm.api_key == "sk-test-llm-key"
        assert config_module.config.llm.base_url == "https://test-llm-base-url.com"
        assert config_module.config.llm.model == "deepseek-chat"

        assert "claude-3-5-sonnet-20240620" in config_module.config.models
        claude_config = config_module.config.models["claude-3-5-sonnet-20240620"]
        assert claude_config.api_key == "sk-test-claude-key"
        assert claude_config.base_url == "https://test-claude-base-url.com"

        assert "default" in config_module.config.models
        default_config = config_module.config.models["default"]
        assert default_config.api_key == "sk-test-default-key"
        assert default_config.base_url == "https://test-default-base-url.com"

    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__])
