"""
配置管理模块

负责加载和管理项目的配置信息。
支持从 config.json 文件和環境变量两种方式读取 Jira 凭据。
在 GitHub Actions 中，优先使用环境变量。
"""

import json
import os
import sys
from pathlib import Path

# 项目根目录（以本文件的上上级目录为准）
PROJECT_ROOT = Path(__file__).parent.parent

# 配置文件路径
CONFIG_PATH = PROJECT_ROOT / "config.json"

# 报告输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_config():
    """
    加载配置文件

    优先级：
    1. 环境变量 JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN（用于 GitHub Actions）
    2. config.json 文件中的配置（用于本地运行）

    Returns:
        dict: 配置字典

    Raises:
        SystemExit: 配置文件不存在且环境变量不完整时退出程序
    """
    # 尝试从环境变量构建配置
    env_base_url = os.environ.get('JIRA_BASE_URL')
    env_email = os.environ.get('JIRA_EMAIL')
    env_api_token = os.environ.get('JIRA_API_TOKEN')

    if env_base_url and env_email and env_api_token:
        return {
            'jira': {
                'base_url': env_base_url,
                'email': env_email,
                'api_token': env_api_token,
            },
            'parent_issue': os.environ.get('JIRA_PARENT_ISSUE', 'KAT-10938'),
            'output': {
                'format': 'html',
                'path': 'output/jira-report.html',
            },
        }

    # 从配置文件读取
    if not CONFIG_PATH.exists():
        print(f"配置文件不存在: {CONFIG_PATH}")
        print("请复制 config.example.json 为 config.json 并填写你的 Jira API Token")
        print("或设置环境变量: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN")
        sys.exit(1)

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_output_dir():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(exist_ok=True)
