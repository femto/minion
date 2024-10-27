from pathlib import Path

import typer
import yaml

app = typer.Typer(name="minion")

DEFAULT_CONFIG = {
    "llm": {"api_key": "sk-xxx", "model": "gpt-4o-mini", "base_url": "some_proxy_base_url"},
    "models": {
        "default": {"api_type": "openai", "base_url": "base_url", "api_key": "sk-xxx", "temperature": 0.7},
        "deepseek-chat": {
            "api_type": "openai",
            "base_url": "some_proxy_base_url",
            "api_key": "sk-xxx",
            "temperature": 0,
        },
        "gpt-4o": {"api_type": "openai", "base_url": "some_proxy_base_url", "api_key": "sk-xxx", "temperature": 0},
        "gpt-4o-mini": {"api_type": "openai", "base_url": "some_proxy_base_url", "api_key": "sk-xxx", "temperature": 0},
    },
}


def get_config_dir() -> Path:
    """获取配置文件目录"""
    return Path.home() / ".minion"


def get_config_path() -> Path:
    """获取配置文件完整路径"""
    return get_config_dir() / "config.yaml"


@app.callback()
def callback():
    """
    Minion CLI tool for managing AI models and configurations
    """
    pass


@app.command()
def init_config(force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing config")):
    """
    Initialize configuration file in ~/.minion/config.yaml
    """
    config_dir = get_config_dir()
    config_path = get_config_path()

    # 创建配置目录
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        typer.echo(f"Created config directory: {config_dir}")

    # 检查配置文件是否存在
    if config_path.exists() and not force:
        typer.echo(f"Config file already exists at {config_path}")
        typer.echo("Use --force to overwrite")
        raise typer.Exit(1)

    # 写入配置文件
    try:
        with open(config_path, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, sort_keys=False, allow_unicode=True)
        typer.echo(f"Created config file: {config_path}")
    except Exception as e:
        typer.echo(f"Error creating config file: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def show_config():
    """
    Display current configuration
    """
    config_path = get_config_path()
    if not config_path.exists():
        typer.echo("Config file not found. Run 'init-config' first.")
        raise typer.Exit(1)

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        typer.echo(yaml.dump(config, sort_keys=False, allow_unicode=True))
    except Exception as e:
        typer.echo(f"Error reading config file: {str(e)}", err=True)
        raise typer.Exit(1)


def cli():
    """CLI 入口点函数"""
    app()


if __name__ == "__main__":
    cli()
