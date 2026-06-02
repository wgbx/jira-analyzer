#!/usr/bin/env python3
"""
在 output/ 目录启动静态文件服务。

--watch：后台按间隔重新拉取 Jira 并生成报告；浏览器每 10 秒检测 report-version.json 并自动刷新。
"""

import argparse
import os
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / 'output'
DEFAULT_PORT = 8080
MAX_TRIES = 20
LIVE_RELOAD_POLL_MS = 10_000

LIVE_RELOAD_SCRIPT = """
<script>
(function () {
  let version = null;
  async function check() {
    try {
      const res = await fetch("/report-version.json?_=" + Date.now());
      if (!res.ok) return;
      const data = await res.json();
      if (version !== null && version !== data.updated) {
        location.reload();
        return;
      }
      version = data.updated;
    } catch (e) { /* 忽略网络错误 */ }
  }
  setInterval(check, """ + str(LIVE_RELOAD_POLL_MS) + """);
  check();
})();
</script>
"""


def find_port(start: int) -> int:
    for port in range(start, start + MAX_TRIES):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('', port))
                return port
            except OSError:
                continue
    print(f'错误: {start}–{start + MAX_TRIES - 1} 端口均被占用', file=sys.stderr)
    sys.exit(1)


def _load_refresh_interval(watch_mode: bool) -> int:
    """返回刷新间隔（秒）；0 表示不自动刷新。"""
    env_val = os.environ.get('REFRESH_INTERVAL')
    if env_val is not None:
        try:
            return max(0, int(env_val))
        except ValueError:
            pass

    if not watch_mode:
        return 0

    if (ROOT / 'config.json').is_file():
        try:
            import json
            with open(ROOT / 'config.json', encoding='utf-8') as f:
                cfg = json.load(f)
            interval = cfg.get('watch', {}).get('refresh_interval_seconds', 120)
            return max(0, int(interval))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return 120


class ReportHandler(SimpleHTTPRequestHandler):
    """静态文件服务；对 HTML 报告注入自动刷新脚本。"""

    inject_live_reload = False

    def end_headers(self):
        if self.path.endswith('.html') or self.path.endswith('.json'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        path = self.translate_path(self.path)
        if (
            self.inject_live_reload
            and self.path.rstrip('/').endswith('jira-report.html')
            and os.path.isfile(path)
        ):
            with open(path, encoding='utf-8') as f:
                body = f.read()
            if LIVE_RELOAD_SCRIPT.strip() not in body:
                body = body.replace('</body>', LIVE_RELOAD_SCRIPT + '\n</body>', 1)

            encoded = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        super().do_GET()


def _refresh_loop(interval: int, stop_event: threading.Event):
    sys.path.insert(0, str(ROOT))
    from jira_analyzer import run_analyzer

    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        try:
            run_analyzer(quiet=True, open_browser=False)
            print(f'[watch] 报告已更新 ({time.strftime("%H:%M:%S")})')
        except Exception as exc:
            print(f'[watch] 刷新失败: {exc}', file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description='预览 Jira 分析报告')
    parser.add_argument(
        '--watch', '-w',
        action='store_true',
        help='后台定时重新拉取 Jira；浏览器自动刷新页面',
    )
    args = parser.parse_args()

    if not OUTPUT_DIR.is_dir():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    refresh_interval = _load_refresh_interval(args.watch)
    stop_event = threading.Event()

    if args.watch or refresh_interval > 0:
        sys.path.insert(0, str(ROOT))
        from jira_analyzer import run_analyzer

        print('首次生成报告…')
        report_path = OUTPUT_DIR / 'jira-report.html'
        try:
            run_analyzer(quiet=False, open_browser=False)
        except SystemExit:
            raise
        except Exception as exc:
            print(f'首次生成失败: {exc}', file=sys.stderr)
            if report_path.is_file():
                print('将使用已有报告启动预览，后台会继续重试拉取 Jira', file=sys.stderr)
            else:
                print('无可用报告，请检查网络/VPN 后重试', file=sys.stderr)
                sys.exit(1)

        interval = refresh_interval or 120
        thread = threading.Thread(
            target=_refresh_loop,
            args=(interval, stop_event),
            daemon=True,
        )
        thread.start()
        print(f'[watch] 每 {interval} 秒自动拉取 Jira 并更新报告')
        ReportHandler.inject_live_reload = True
    elif not (OUTPUT_DIR / 'jira-report.html').is_file():
        print(f'错误: 报告不存在，请先运行: npm start', file=sys.stderr)
        print('或使用: npm run dev', file=sys.stderr)
        sys.exit(1)

    start = int(os.environ.get('PORT', DEFAULT_PORT))
    port = find_port(start)
    os.chdir(OUTPUT_DIR)

    with ThreadingHTTPServer(('', port), ReportHandler) as httpd:
        if port != start:
            print(f'端口 {start} 已被占用，改用 {port}')
        print(f'报告预览: http://localhost:{port}/jira-report.html')
        if ReportHandler.inject_live_reload:
            print('页面将在报告更新后自动刷新（无需手动 npm start）')
        print('按 Ctrl+C 停止')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n已停止')
        finally:
            stop_event.set()


if __name__ == '__main__':
    main()
