"""
Jira HTTP 请求封装：Session、重试、瞬时 SSL/网络错误恢复。
"""

import time

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

_RETRYABLE_EXC = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

_DEFAULT_RETRIES = 5
_DEFAULT_BACKOFF = 1.0


def build_jira_session(config):
    """创建带认证与重试的 requests Session。"""
    jira = config['jira']
    session = requests.Session()
    session.auth = HTTPBasicAuth(jira['email'], jira['api_token'])
    session.headers.update({'Content-Type': 'application/json'})

    retry = Retry(
        total=_DEFAULT_RETRIES,
        connect=_DEFAULT_RETRIES,
        read=_DEFAULT_RETRIES,
        backoff_factor=_DEFAULT_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['GET', 'POST']),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def jira_request(session, method, url, *, timeout=60, **kwargs):
    """
    发起 Jira API 请求；对 SSL/连接类错误额外重试。

    Raises:
        requests.RequestException: 重试耗尽仍失败
    """
    last_error = None
    for attempt in range(_DEFAULT_RETRIES):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            return response
        except _RETRYABLE_EXC as exc:
            last_error = exc
            wait = _DEFAULT_BACKOFF * (2 ** attempt)
            print(f'  网络异常，{wait:.0f}s 后重试 ({attempt + 1}/{_DEFAULT_RETRIES}): {exc.__class__.__name__}')
            time.sleep(wait)

    raise last_error
