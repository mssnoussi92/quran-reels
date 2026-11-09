"""Facebook Page Reels (Reels Publishing API), published only after Meta's copyright check.

prepare: start → binary upload to rupload.facebook.com → finish with video_state=DRAFT → wait
for processing. The reel is then a draft in Meta Business Suite (Content → Drafts).
rights: copyright_check_information of the draft (publishers/rights.py).
commit: the same file uploaded again, finished with video_state=PUBLISHED, then the draft
deleted, then its cover set (cover: the frame Instagram uses, reel.cover_ms, as the preferred
thumbnail, POST /{video}/thumbnails; never in the way of the publication). A draft reel cannot be published through the API: its upload session ended with the
draft, and finishing it again fails («The video was not uploaded», code 6000, subcode 1363130,
publish-test run #18, 2026-11-05).
A dry run stops after the check; publish_reel then deletes the draft.

Description: the reel's short caption (≤ 400 characters, render.facebook_caption: Facebook's
quality checklist flagged the full one, 2026-11-09); the full caption with max_hashtags when
the reel has none.
"""

from __future__ import annotations

import subprocess
import sys

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
        try:
            status = self.graph.get(video_id, fields="status").get("status") or {}
        except GraphError as e:
            # Right after the finish call the new video can answer «does not exist» (code 100,
            # subcode 33) while it is already live (Budair's 2:255, publish-test, 2026-11-05):
            # asked again, like a network error.
            if "error_subcode 33" in str(e):
                raise GraphError(str(e), transient=True) from None
            raise
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

    def _upload(self, reel: Reel, state: str) -> str:
        start = self.graph.post(f"{self.page_id}/video_reels", upload_phase="start")
        video_id = str(start["video_id"])
        url = start.get("upload_url") or f"{RUPLOAD}/video-upload/{self.graph.version}/{video_id}"
        self.graph.upload(url, reel.video, f"upload facebook reel {video_id}")
        self.graph.post(f"{self.page_id}/video_reels", upload_phase="finish", video_id=video_id,
                        video_state=state,
                        description=reel.text_for(self.name, self.max_hashtags))
        return video_id

    def prepare(self, reel: Reel) -> str:
        """Id of a processed, unpublished draft reel."""
        video_id = self._upload(reel, "DRAFT")
        wait(lambda: self._status(video_id, published=False), f"facebook reel {video_id}",
             self.timeout, self.poll_interval)
        return video_id

    def cover(self, video_id: str, reel: Reel) -> bool:
        """Set the reel's cover: the frame Instagram shows (reel.cover_ms, the middle of the
        first ayah with a word meaning), as its preferred thumbnail; Facebook picks a frame
        itself otherwise. Needs pages_manage_engagement and pages_read_user_content. Never
        fails the publication: False, with a warning."""
        if reel.cover_ms is None:
            return False
        jpg = reel.video.with_suffix("") / "cover.jpg"
        try:
            jpg.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss",
                            f"{reel.cover_ms / 1000:.3f}", "-i", str(reel.video), "-frames:v",
                            "1", "-q:v", "2", "-y", str(jpg)], capture_output=True, check=True)
            self.graph.post_file(f"{video_id}/thumbnails", "source", jpg, is_preferred="true")
        except (OSError, subprocess.CalledProcessError, PublisherError) as e:
            why = "no frame" if isinstance(e, subprocess.CalledProcessError) else str(e)
            print(f"warning: facebook reel {video_id}: cover not set ({why})", file=sys.stderr)
            return False
        print(f"facebook: cover of {video_id} set ({reel.cover_ms / 1000:.1f} s into the reel)",
              file=sys.stderr)
        return True

    def rights(self, video_id: str) -> rights.RightsCheck:
        return rights.check(self.graph, self.name, video_id, self.rights_timeout,
                            self.poll_interval)

    def rights_after(self, remote_id: str, timeout: float = 0) -> rights.RightsCheck:
        """The copyright check of the published reel (timeout 0: read once)."""
        return rights.check(self.graph, self.name, remote_id, timeout, self.poll_interval,
                            field_name=rights.AFTER)

    def remove(self, remote_id: str) -> None:
        """Take the published reel down (GraphError if Meta refuses)."""
        self.graph.delete(remote_id)

    def commit(self, draft_id: str, reel: Reel) -> PublishResult:
        """Publish the checked video: uploaded again straight to PUBLISHED, draft deleted."""
        try:
            video_id = self._upload(reel, "PUBLISHED")
            wait(lambda: self._status(video_id, published=True), f"facebook reel {video_id}",
                 self.timeout, self.poll_interval)
        except (PublisherError, KeyError) as e:
            uploaded = locals().get("video_id")
            where = (f"the published reel {uploaded} may be live anyway: check the Page; "
                     f"draft {draft_id} left in Meta Business Suite → Content → Drafts"
                     if uploaded else "draft checked but not published: Meta Business Suite → "
                                      "Content → Drafts")
            return PublishResult(self.name, PublishStatus.FAILED, remote_id=draft_id,
                                 error=f"{e} ({where})")
        try:
            if draft_id != video_id:
                self.graph.delete(draft_id)
        except GraphError:
            pass                        # a leftover draft in Business Suite, harmless
        self.cover(video_id, reel)
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
