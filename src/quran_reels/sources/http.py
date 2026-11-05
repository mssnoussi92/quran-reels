"""Shared HTTP client: one session, retries, polite per-host throttling, atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from quran_reels import __version__

USER_AGENT = f"quran-reels/{__version__} (+https://github.com/mssnoussi92/quran-reels)"


class Http:
    def __init__(self, min_interval: float = 0.25, timeout: float = 30):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.min_interval = min_interval
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        with self._lock:
            wait = self._last.get(host, 0) + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()

    def get(self, url: str, **params: Any) -> requests.Response:
        self._throttle(url)
        r = self.session.get(url, params=params or None, timeout=self.timeout)
        r.raise_for_status()
        return r

    def size(self, url: str) -> int:
        """Content-Length of a file, without downloading it."""
        self._throttle(url)
        r = self.session.head(url, timeout=self.timeout, allow_redirects=True)
        r.raise_for_status()
        return int(r.headers["Content-Length"])

    def json(self, url: str, **params: Any) -> Any:
        return self.get(url, **params).json()

    def download(self, url: str, dest: Path, min_bytes: int = 1) -> Path:
        r = self.get(url)
        if len(r.content) < min_bytes:
            raise RuntimeError(f"{url}: {len(r.content)} bytes, expected at least {min_bytes}")
        write_bytes(dest, r.content)
        return dest


def write_bytes(dest: Path, data: bytes) -> None:
    """Write atomically so an interrupted ingestion never leaves a truncated cache file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(dest: Path, obj: Any) -> None:
    write_bytes(dest, json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
