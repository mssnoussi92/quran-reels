"""Instagram Reels (Instagram Graph API, account linked to the Page, Page token).

REELS container with resumable upload → binary upload → wait for status_code FINISHED →
media_publish. A dry run stops before media_publish: the container is ready but nothing is
posted, and Instagram drops it after 24 hours.

rupload answers 400 ProcessingFailedError to most uploads. Sometimes Instagram has the video
anyway (run #7: container FINISHED at once), sometimes the container stays IN_PROGRESS for
good (run #9: still after 15 min). After that error, a container that is not ready within
stuck_after seconds is abandoned and the video goes to a new container, up to `attempts`
times. An unpublished container costs nothing: it is not posted and expires after 24 hours.
"""

from __future__ import annotations

import sys

from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers.base import PublisherError, StillProcessing
from quran_reels.publishers.meta import RUPLOAD, Graph, GraphError, wait

CAPTION_LIMIT = 2200


class InstagramPublisher:
    name = "instagram"
    mode = "auto"

    def __init__(self, graph: Graph, ig_user_id: str, poll_interval: float = 10,
                 timeout: float = 900, attempts: int = 3, stuck_after: float = 240):
        self.graph = graph
        self.ig_user_id = ig_user_id
        self.poll_interval = poll_interval
        self.timeout = timeout              # processing after a clean upload
        self.attempts = attempts            # containers tried when uploads fail
        self.stuck_after = stuck_after      # processing allowed after a failed upload

    def _status(self, container_id: str) -> tuple[bool, str]:
        c = self.graph.get(container_id, fields="status_code,status")
        code = c.get("status_code")
        if code in ("ERROR", "EXPIRED"):
            raise GraphError(f"instagram container {container_id}: {code} {c.get('status', '')}")
        return code in ("FINISHED", "PUBLISHED"), code

    def _explain(self, container_id: str) -> str:
        """What Instagram says about a container, often more precise than the upload error."""
        try:
            c = self.graph.get(container_id, fields="status_code,status")
        except GraphError as e:
            return f"status unavailable ({e})"
        return f"{c.get('status_code', '?')} {c.get('status', '')}".strip()

    def _quota(self) -> None:
        data = (self.graph.get(f"{self.ig_user_id}/content_publishing_limit",
                               fields="quota_usage,config").get("data") or [{}])[0]
        used, total = data.get("quota_usage", 0), (data.get("config") or {}).get("quota_total", 50)
        if used >= total:
            raise GraphError(f"instagram: publishing limit reached ({used}/{total} in 24 h)")

    def _upload(self, reel: Reel, params: dict[str, str]) -> tuple[str, bool]:
        """New container, video uploaded to it. Returns (container id, upload failed)."""
        container = self.graph.post(f"{self.ig_user_id}/media", **params)
        cid = str(container["id"])
        url = container.get("uri") or f"{RUPLOAD}/ig-api-upload/{self.graph.version}/{cid}"
        try:
            self.graph.upload(url, reel.video, f"upload instagram container {cid}")
        except GraphError as e:
            state = self._explain(cid)
            if not state.startswith(("IN_PROGRESS", "FINISHED")):
                raise GraphError(f"{e}; container: {state}") from None
            print(f"warning: {e}; container is {state}, waiting for it", file=sys.stderr)
            return cid, True
        return cid, False

    def _ready_container(self, reel: Reel, params: dict[str, str]) -> str:
        """Id of a container holding the processed video (status FINISHED)."""
        for attempt in range(1, self.attempts + 1):
            cid, failed = self._upload(reel, params)
            timeout = self.stuck_after if failed else self.timeout
            try:
                wait(lambda c=cid: self._status(c), f"instagram container {cid}", timeout,
                     self.poll_interval)
                return cid
            except StillProcessing:
                if not failed or attempt == self.attempts:
                    raise
            print(f"warning: instagram container {cid} still IN_PROGRESS {timeout:.0f} s after "
                  f"the upload error, uploading again to a new container "
                  f"({attempt + 1}/{self.attempts})", file=sys.stderr)
        raise AssertionError("unreachable")

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        if len(reel.caption) > CAPTION_LIMIT:
            return PublishResult(self.name, PublishStatus.FAILED,
                                 error=f"caption longer than {CAPTION_LIMIT} characters")
        params = {"media_type": "REELS", "upload_type": "resumable", "caption": reel.caption,
                  "share_to_feed": "true"}
        if reel.cover_ms is not None:
            params["thumb_offset"] = str(reel.cover_ms)
        try:
            cid = self._ready_container(reel, params)
            if dry_run:
                return PublishResult(self.name, PublishStatus.READY, remote_id=cid)
            self._quota()
            media_id = str(self.graph.post(f"{self.ig_user_id}/media_publish",
                                           creation_id=cid)["id"])
        except (PublisherError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))
        link = None
        try:
            link = self.graph.get(media_id, fields="permalink").get("permalink")
        except GraphError:
            pass
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=media_id, url=link)
