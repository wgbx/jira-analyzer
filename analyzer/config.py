"""
配置管理模块

负责加载和管理项目的配置信息，包括 Jira 连接参数和输出设置。
"""

import json
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

    从项目根目录的 config.json 中读取配置信息，
    包括 Jira 实例地址、认证凭据、父任务编号等。

    Returns:
        dict: 配置字典

    Raises:
        SystemExit: 配置文件不存在时退出程序
    """
    if not CONFIG_PATH.exists():
        print(f"配置文件不存在: {CONFIG_PATH}")
        print("请复制 config.example.json 并填写你的 Jira API Token")
        sys.exit(1)

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_output_dir():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(exist_ok=True)
