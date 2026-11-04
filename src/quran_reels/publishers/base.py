"""Common interface for every platform. Add a platform = add one module implementing it."""

from __future__ import annotations

from typing import Protocol

from quran_reels.models import PublishResult, Reel


class Publisher(Protocol):
    name: str            # facebook | instagram | tiktok | youtube
    mode: str            # auto | draft | manual

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        """dry_run: go as far as the platform allows without anything becoming public."""
        ...
