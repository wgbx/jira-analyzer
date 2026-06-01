#!/usr/bin/env python3
"""在 output/ 目录启动静态文件服务；端口被占用时自动尝试下一个。"""

import os
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DEFAULT_PORT = 8080
MAX_TRIES = 20


def find_port(start: int) -> int:
    for port in range(start, start + MAX_TRIES):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("", port))
                return port
            except OSError:
                continue
    print(f"错误: {start}–{start + MAX_TRIES - 1} 端口均被占用", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not OUTPUT_DIR.is_dir():
        print(f"错误: 输出目录不存在: {OUTPUT_DIR}", file=sys.stderr)
        print("请先运行: npm start", file=sys.stderr)
        sys.exit(1)

    start = int(os.environ.get("PORT", DEFAULT_PORT))
    port = find_port(start)
    os.chdir(OUTPUT_DIR)

    handler = SimpleHTTPRequestHandler
    with ThreadingHTTPServer(("", port), handler) as httpd:
        if port != start:
            print(f"端口 {start} 已被占用，改用 {port}")
        print(f"报告预览: http://localhost:{port}/jira-report.html")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
