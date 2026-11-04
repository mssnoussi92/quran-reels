"""Instagram Reels (Instagram Graph API, account linked to the Page, Page token).

REELS container with resumable upload → binary upload → wait for status_code FINISHED →
media_publish. A dry run stops before media_publish: the container is ready but nothing is
posted, and Instagram drops it after 24 hours.
"""

from __future__ import annotations

import sys

from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers.meta import RUPLOAD, Graph, GraphError, wait

CAPTION_LIMIT = 2200


class InstagramPublisher:
    name = "instagram"
    mode = "auto"

    def __init__(self, graph: Graph, ig_user_id: str, poll_interval: float = 10,
                 timeout: float = 900):
        self.graph = graph
        self.ig_user_id = ig_user_id
        self.poll_interval = poll_interval
        self.timeout = timeout

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

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        if len(reel.caption) > CAPTION_LIMIT:
            return PublishResult(self.name, PublishStatus.FAILED,
                                 error=f"caption longer than {CAPTION_LIMIT} characters")
        params = {"media_type": "REELS", "upload_type": "resumable", "caption": reel.caption,
                  "share_to_feed": "true"}
        if reel.cover_ms is not None:
            params["thumb_offset"] = str(reel.cover_ms)
        try:
            container = self.graph.post(f"{self.ig_user_id}/media", **params)
            cid = str(container["id"])
            url = container.get("uri") or f"{RUPLOAD}/ig-api-upload/{self.graph.version}/{cid}"
            try:
                self.graph.upload(url, reel.video, f"upload instagram container {cid}")
            except GraphError as e:
                # Seen on real uploads: rupload answers 400 ProcessingFailedError although
                # Instagram received the video and is processing it. Trust the container.
                state = self._explain(cid)
                if not state.startswith(("IN_PROGRESS", "FINISHED")):
                    raise GraphError(f"{e}; container: {state}") from None
                print(f"warning: {e}; container is {state}, waiting for it",
                      file=sys.stderr)
            wait(lambda: self._status(cid), f"instagram container {cid}",
                 self.timeout, self.poll_interval)
            if dry_run:
                return PublishResult(self.name, PublishStatus.READY, remote_id=cid)
            self._quota()
            media_id = str(self.graph.post(f"{self.ig_user_id}/media_publish",
                                           creation_id=cid)["id"])
        except (GraphError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))
        link = None
        try:
            link = self.graph.get(media_id, fields="permalink").get("permalink")
        except GraphError:
            pass
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=media_id, url=link)
