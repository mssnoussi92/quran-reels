"""Facebook Page Reels (Reels Publishing API), published only after Meta's copyright check.

prepare: start → binary upload to rupload.facebook.com → finish with video_state=DRAFT → wait
for processing. The reel is then a draft in Meta Business Suite (Content → Drafts).
rights: copyright_check_information of the draft (publishers/rights.py).
commit: finish again with video_state=PUBLISHED, wait until it is live.
A dry run stops after the check: the draft stays unpublished.
"""

from __future__ import annotations

from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers import rights
from quran_reels.publishers.base import PublisherError
from quran_reels.publishers.meta import RUPLOAD, Graph, GraphError, wait


class FacebookPublisher:
    name = "facebook"
    mode = "auto"

    def __init__(self, graph: Graph, page_id: str, poll_interval: float = 10,
                 timeout: float = 900, max_hashtags: int | None = None,
                 rights_timeout: float = 600):
        self.graph = graph
        self.page_id = page_id
        self.max_hashtags = max_hashtags
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.rights_timeout = rights_timeout

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

    def prepare(self, reel: Reel) -> str:
        """Id of a processed, unpublished draft reel."""
        start = self.graph.post(f"{self.page_id}/video_reels", upload_phase="start")
        video_id = str(start["video_id"])
        url = start.get("upload_url") or f"{RUPLOAD}/video-upload/{self.graph.version}/{video_id}"
        self.graph.upload(url, reel.video, f"upload facebook reel {video_id}")
        self.graph.post(f"{self.page_id}/video_reels", upload_phase="finish", video_id=video_id,
                        video_state="DRAFT", description=reel.text(self.max_hashtags))
        wait(lambda: self._status(video_id, published=False), f"facebook reel {video_id}",
             self.timeout, self.poll_interval)
        return video_id

    def rights(self, video_id: str) -> rights.RightsCheck:
        return rights.check(self.graph, self.name, video_id, self.rights_timeout,
                            self.poll_interval)

    def commit(self, video_id: str, reel: Reel) -> PublishResult:
        """Publish the checked draft."""
        try:
            self.graph.post(f"{self.page_id}/video_reels", upload_phase="finish",
                            video_id=video_id, video_state="PUBLISHED",
                            description=reel.text(self.max_hashtags))
            wait(lambda: self._status(video_id, published=True), f"facebook reel {video_id}",
                 self.timeout, self.poll_interval)
        except (PublisherError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, remote_id=video_id,
                                 error=f"{e} (draft checked but not published: Meta Business "
                                       "Suite → Content → Drafts)")
        link = None
        try:
            link = self.graph.get(video_id, fields="permalink_url").get("permalink_url")
        except GraphError:
            pass
        if link and link.startswith("/"):
            link = f"https://www.facebook.com{link}"
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=video_id,
                             url=link or f"https://www.facebook.com/reel/{video_id}")

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        """Facebook alone: prepare, check, then publish if the check is clear."""
        try:
            video_id = self.prepare(reel)
        except (PublisherError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))
        check = self.rights(video_id)
        if dry_run:
            return PublishResult(self.name, PublishStatus.DRAFT, remote_id=video_id,
                                 rights=check.as_dict())
        if not check.clear:
            return PublishResult(self.name, PublishStatus.BLOCKED, remote_id=video_id,
                                 error=f"droits : {check.describe()}", rights=check.as_dict())
        result = self.commit(video_id, reel)
        result.rights = check.as_dict()
        return result
