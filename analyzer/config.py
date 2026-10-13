"""
配置管理模块

负责加载和管理项目的配置信息。
Jira 凭据优先读环境变量（GitHub Actions）；reports 等非敏感项读仓库内配置文件。
"""

import json
import os
import shutil
import sys
from pathlib import Path

# 项目根目录（以本文件的上上级目录为准）
PROJECT_ROOT = Path(__file__).parent.parent

# 配置文件路径（本地；勿提交，见 .gitignore）
CONFIG_PATH = PROJECT_ROOT / "config.json"

# 报告输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"

DEFAULT_PARENT_ISSUE = 'KAT-12205'
DEFAULT_OUTPUT = {
    'format': 'html',
}
# GitHub Actions 无 config.json 时使用；本地模板见 README
DEFAULT_REPORTS = [
    {
        'id': 'q4',
        'label': 'Q4',
        'parent_issue': 'KAT-12205',
        'output': 'output/index.html',
    },
]


def _load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_file_config():
    """仅读取本地 config.json；不存在则返回 None（Actions 靠环境变量 + 代码默认）。"""
    if CONFIG_PATH.exists():
        return _load_json(CONFIG_PATH)
    return None


def get_reports(config):
    """
    返回要生成的报告列表。

    优先用 config.reports（跳过 enabled 为 false 的项）；否则回退为单报告（legacy parent_issue）。
    """
    reports = config.get('reports')
    if reports:
        return [r for r in reports if r.get('enabled', True)]
    return [{
        'id': 'default',
        'label': 'Q4',
        'parent_issue': config.get('parent_issue', DEFAULT_PARENT_ISSUE),
        'output': config.get('output', {}).get('path', 'output/index.html'),
    }]


def load_config():
    """
    加载配置

    优先级：
    1. 环境变量 JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN（凭据，用于 GitHub Actions）
    2. 本地 config.json（reports、filters 等；模板见 README）
    3. 无本地文件时，reports/output 使用本模块 DEFAULT_*（供 Actions）

    Returns:
        dict: 配置字典

    Raises:
        SystemExit: 配置文件不存在且环境变量不完整时退出程序
    """
    env_base_url = os.environ.get('JIRA_BASE_URL')
    env_email = os.environ.get('JIRA_EMAIL')
    env_api_token = os.environ.get('JIRA_API_TOKEN')
    file_config = _load_file_config()

    if env_base_url and env_email and env_api_token:
        config = dict(file_config) if file_config else {}
        config['jira'] = {
            'base_url': env_base_url,
            'email': env_email,
            'api_token': env_api_token,
        }
        config.setdefault('reports', DEFAULT_REPORTS)
        config.setdefault('output', DEFAULT_OUTPUT)
        return config

    if not file_config:
        print(f"配置文件不存在: {CONFIG_PATH}")
        print("请按 README「本地运行 → 配置」创建 config.json 并填写 Jira API Token")
        print("或设置环境变量: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN")
        sys.exit(1)

    return file_config


def ensure_output_dir():
    """确保输出目录存在，并同步站点图标到 output/。"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    favicon_src = PROJECT_ROOT / 'assets' / 'favicon.svg'
    if favicon_src.is_file():
        shutil.copy2(favicon_src, OUTPUT_DIR / 'favicon.svg')
