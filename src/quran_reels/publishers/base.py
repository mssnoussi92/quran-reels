"""Common interface for every platform. Add a platform = add one module implementing it."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from quran_reels.models import PublishResult, Reel


class Publisher(Protocol):
    name: str            # facebook | instagram | tiktok | youtube
    mode: str            # auto | draft | manual

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        """dry_run: go as far as the platform allows without anything becoming public."""
        ...


class PublisherError(RuntimeError):
    """An API refused or failed. Messages never contain a token."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient      # network error or HTTP 5xx: worth asking again


def wait(check: Callable[[], tuple[bool, Any]], what: str, timeout: float = 900,
         interval: float = 10) -> Any:
    """Call check() until it reports done; check raises on a terminal error.

    Up to 3 transient errors in a row are tolerated: the upload is already done and the
    platform keeps processing it, whatever happens to one status request.
    """
    deadline = time.monotonic() + timeout
    transient = 0
    while True:
        try:
            done, value = check()
            transient = 0
        except PublisherError as e:
            transient += 1
            if not e.transient or transient > 3:
                raise
            done, value = False, None
        if done:
            return value
        if time.monotonic() > deadline:
            raise PublisherError(f"{what}: still processing after {timeout:.0f} s")
        time.sleep(interval)
