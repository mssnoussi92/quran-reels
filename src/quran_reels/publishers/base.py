"""Common interface for every platform. Add a platform = add one module implementing it."""

from __future__ import annotations

from typing import Protocol

from quran_reels.models import PublishResult, Reel


class Publisher(Protocol):
    name: str            # facebook | instagram | tiktok | youtube
    mode: str            # auto | draft | manual

    def publish(self, reel: Reel) -> PublishResult: ...
