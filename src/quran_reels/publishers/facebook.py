"""Facebook Page Reels (Reels Publishing API).

start → binary upload to rupload.facebook.com → finish with video_state=PUBLISHED, or DRAFT
for a dry run: the reel then waits in Meta Business Suite (Content → Drafts), unpublished.
"""

from __future__ import annotations

from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers.meta import RUPLOAD, Graph, GraphError, wait


class FacebookPublisher:
    name = "facebook"
    mode = "auto"

    def __init__(self, graph: Graph, page_id: str, poll_interval: float = 10,
                 timeout: float = 900):
        self.graph = graph
        self.page_id = page_id
        self.poll_interval = poll_interval
        self.timeout = timeout

    def _status(self, video_id: str, published: bool) -> tuple[bool, dict]:
        status = self.graph.get(video_id, fields="status").get("status") or {}
        for phase in ("uploading_phase", "processing_phase", "publishing_phase"):
            p = status.get(phase) or {}
            if p.get("status") == "error":
                errors = "; ".join(e.get("message", "") for e in p.get("errors") or [])
                raise GraphError(f"facebook reel {video_id}: {phase} error {errors}".strip())
        if status.get("video_status") == "error":
            raise GraphError(f"facebook reel {video_id}: video_status error")
        processed = (status.get("processing_phase") or {}).get("status") == "complete"
        live = (status.get("publishing_phase") or {}).get("status") == "complete"
        return processed and (live or not published), status

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        try:
            start = self.graph.post(f"{self.page_id}/video_reels", upload_phase="start")
            video_id = str(start["video_id"])
            url = start.get("upload_url") or \
                f"{RUPLOAD}/video-upload/{self.graph.version}/{video_id}"
            self.graph.upload(url, reel.video, f"upload facebook reel {video_id}")
            self.graph.post(f"{self.page_id}/video_reels", upload_phase="finish",
                            video_id=video_id, video_state="DRAFT" if dry_run else "PUBLISHED",
                            description=reel.caption)
            wait(lambda: self._status(video_id, published=not dry_run),
                 f"facebook reel {video_id}", self.timeout, self.poll_interval)
        except (GraphError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))

        if dry_run:
            return PublishResult(self.name, PublishStatus.DRAFT, remote_id=video_id)
        link = None
        try:
            link = self.graph.get(video_id, fields="permalink_url").get("permalink_url")
        except GraphError:
            pass
        if link and link.startswith("/"):
            link = f"https://www.facebook.com{link}"
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=video_id,
                             url=link or f"https://www.facebook.com/reel/{video_id}")
