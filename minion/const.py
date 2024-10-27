#!/usr/bin/env python
# -*- coding: utf-8 -*-
# adapted from metagpt

import os
from pathlib import Path

from colorama import Fore, Style, init
from loguru import logger

import minion

# Initialize colorama
init(autoreset=True)


def get_minion_package_root():
    """Get the root directory of the installed package."""
    package_root = Path(minion.__file__).parent.parent
    for i in (".git", ".project_root", ".gitignore"):
        if (package_root / i).exists():
            break
    else:
        package_root = Path.cwd()

    return package_root


def get_minion_root():
    """Get the project root directory."""
    # Check if a project root is specified in the environment variable
    project_root_env = os.getenv("MINION_PROJECT_ROOT")
    if project_root_env:
        project_root = Path(project_root_env)
        logger.info(
            f"{Fore.GREEN}PROJECT_ROOT{Style.RESET_ALL} set from environment variable to {Fore.CYAN}{str(project_root)}{Style.RESET_ALL}"
        )
    else:
        # Fallback to package root if no environment variable is set
        project_root = get_minion_package_root()

    return project_root


# MINION PROJECT ROOT AND VARS
CONFIG_ROOT = Path.home() / ".minion"
MINION_ROOT = get_minion_root()
MODEL_PRICES_PATH = MINION_ROOT / "minion/utils/model_prices_and_context_window.json"
DEFAULT_WORKSPACE_ROOT = MINION_ROOT / "workspace"

EXAMPLE_PATH = MINION_ROOT / "examples"
EXAMPLE_DATA_PATH = EXAMPLE_PATH / "data"
DATA_PATH = MINION_ROOT / "data"

# Timeout
USE_CONFIG_TIMEOUT = 0  # Using llm.timeout configuration.
LLM_API_TIMEOUT = 300
