#!/usr/bin/env python
# -*- coding: utf-8 -*-
#adapted from metagpt
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
            f"{Fore.GREEN}PROJECT_ROOT{Style.RESET_ALL} set from environment variable to {Fore.CYAN}{str(project_root)}{Style.RESET_ALL}")
    else:
        # Fallback to package root if no environment variable is set
        project_root = get_minion_package_root()

    return project_root


# MINION PROJECT ROOT AND VARS
CONFIG_ROOT = Path.home() / ".minion"
MINION_ROOT = get_minion_root()  # Dependent on MINION_PROJECT_ROOT
DEFAULT_WORKSPACE_ROOT = MINION_ROOT / "workspace"

EXAMPLE_PATH = MINION_ROOT / "examples"
EXAMPLE_DATA_PATH = EXAMPLE_PATH / "data"
DATA_PATH = MINION_ROOT / "data"
EXAMPLE_BENCHMARK_PATH = EXAMPLE_PATH / "data/rag_bm"
TEST_DATA_PATH = MINION_ROOT / "tests/data"
RESEARCH_PATH = DATA_PATH / "research"
TUTORIAL_PATH = DATA_PATH / "tutorial_docx"
INVOICE_OCR_TABLE_PATH = DATA_PATH / "invoice_table"

UT_PATH = DATA_PATH / "ut"
SWAGGER_PATH = UT_PATH / "files/api/"
UT_PY_PATH = UT_PATH / "files/ut/"
API_QUESTIONS_PATH = UT_PATH / "files/question/"

SERDESER_PATH = DEFAULT_WORKSPACE_ROOT / "storage"

TMP = MINION_ROOT / "tmp"

SOURCE_ROOT = MINION_ROOT / "minion"
PROMPT_PATH = SOURCE_ROOT / "prompts"
SKILL_DIRECTORY = SOURCE_ROOT / "skills"
TOOL_SCHEMA_PATH = MINION_ROOT / "minion/tools/schemas"
TOOL_LIBS_PATH = MINION_ROOT / "minion/tools/libs"

# REAL CONSTS

MEM_TTL = 24 * 30 * 3600

MESSAGE_ROUTE_FROM = "sent_from"
MESSAGE_ROUTE_TO = "send_to"
MESSAGE_ROUTE_CAUSE_BY = "cause_by"
MESSAGE_META_ROLE = "role"
MESSAGE_ROUTE_TO_ALL = "<all>"
MESSAGE_ROUTE_TO_NONE = "<none>"

REQUIREMENT_FILENAME = "requirement.txt"
BUGFIX_FILENAME = "bugfix.txt"
PACKAGE_REQUIREMENTS_FILENAME = "requirements.txt"

DOCS_FILE_REPO = "docs"
PRDS_FILE_REPO = "docs/prd"
SYSTEM_DESIGN_FILE_REPO = "docs/system_design"
TASK_FILE_REPO = "docs/task"
CODE_PLAN_AND_CHANGE_FILE_REPO = "docs/code_plan_and_change"
COMPETITIVE_ANALYSIS_FILE_REPO = "resources/competitive_analysis"
DATA_API_DESIGN_FILE_REPO = "resources/data_api_design"
SEQ_FLOW_FILE_REPO = "resources/seq_flow"
SYSTEM_DESIGN_PDF_FILE_REPO = "resources/system_design"
PRD_PDF_FILE_REPO = "resources/prd"
TASK_PDF_FILE_REPO = "resources/api_spec_and_task"
CODE_PLAN_AND_CHANGE_PDF_FILE_REPO = "resources/code_plan_and_change"
TEST_CODES_FILE_REPO = "tests"
TEST_OUTPUTS_FILE_REPO = "test_outputs"
CODE_SUMMARIES_FILE_REPO = "docs/code_summary"
CODE_SUMMARIES_PDF_FILE_REPO = "resources/code_summary"
RESOURCES_FILE_REPO = "resources"
SD_OUTPUT_FILE_REPO = "resources/sd_output"
GRAPH_REPO_FILE_REPO = "docs/graph_repo"
VISUAL_GRAPH_REPO_FILE_REPO = "resources/graph_db"
CLASS_VIEW_FILE_REPO = "docs/class_view"

YAPI_URL = "http://yapi.deepwisdomai.com/"

DEFAULT_LANGUAGE = "English"
DEFAULT_MAX_TOKENS = 1500
COMMAND_TOKENS = 500
BRAIN_MEMORY = "BRAIN_MEMORY"
SKILL_PATH = "SKILL_PATH"
SERPER_API_KEY = "SERPER_API_KEY"
DEFAULT_TOKEN_SIZE = 500

# format
BASE64_FORMAT = "base64"

# REDIS
REDIS_KEY = "REDIS_KEY"

# Message id
IGNORED_MESSAGE_ID = "0"

# Class Relationship
GENERALIZATION = "Generalize"
COMPOSITION = "Composite"
AGGREGATION = "Aggregate"

# Timeout
USE_CONFIG_TIMEOUT = 0  # Using llm.timeout configuration.
LLM_API_TIMEOUT = 300
