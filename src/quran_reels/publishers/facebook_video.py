"""Facebook Page videos longer than the Reels API allows (3 to 90 s): the theme films and shorts.

Same steps and same rule as the reels (facebook.py), on the Page's video edge:

prepare: the whole file sent to graph-video.facebook.com/{page}/videos with published=false,
         then processing waited for. Nothing is public.
rights:  Meta's copyright check of that unpublished video (publishers/rights.py).
commit:  the same file sent again with published=true, processing and publication waited for,
         the unpublished copy deleted, the cover set (the image the owner validated).
A dry run stops after the check and the unpublished video is deleted (themepub).

Facebook shows a vertical video posted this way like a reel. The unpublished copy is not edited
into a published one: the reels showed that a draft cannot be published through the API
(code 6000, 2026-11-05), so the same two-upload path is used here.
"""

from __future__ import annotations

import sys
from pathlib import Path

from quran_reels.models import PublishResult, PublishStatus
from quran_reels.publishers import rights
from quran_reels.publishers.base import PublisherError
from quran_reels.publishers.meta import Graph, GraphError, wait


class FacebookVideoPublisher:
    name = "facebook"
    mode = "auto"

    def __init__(self, graph: Graph, page_id: str, poll_interval: float = 15,
                 timeout: float = 1800, rights_timeout: float = 600):
        self.graph = graph
        self.page_id = page_id
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.rights_timeout = rights_timeout

    def _status(self, video_id: str, published: bool) -> tuple[bool, dict]:
        try:
            status = self.graph.get(video_id, fields="status").get("status") or {}
        except GraphError as e:
            if "error_subcode 33" in str(e):          # not visible yet right after the upload
                raise GraphError(str(e), transient=True) from None
            raise
        for phase in ("uploading_phase", "processing_phase", "publishing_phase"):
            p = status.get(phase) or {}
            if p.get("status") == "error":
                errors = "; ".join(e.get("message", "") for e in p.get("errors") or [])
                raise GraphError(f"facebook video {video_id}: {phase} error {errors}".strip())
        if status.get("video_status") == "error":
            raise GraphError(f"facebook video {video_id}: video_status error")
        processed = (status.get("processing_phase") or {}).get("status") == "complete" or \
            status.get("video_status") == "ready"
        live = (status.get("publishing_phase") or {}).get("status") == "complete"
        return processed and (live or not published), status

    def _upload(self, reel, published: bool) -> str:
        data = {"description": reel.text_for(self.name),
                "published": "true" if published else "false"}
        if getattr(reel, "title", ""):
            data["title"] = reel.title
        body = self.graph.post_video(f"{self.page_id}/videos", Path(reel.video), **data)
        if not body.get("id"):
            raise GraphError(f"facebook video upload of {Path(reel.video).name}: no id in the answer")
        return str(body["id"])

    def prepare(self, reel) -> str:
        """Id of a processed, unpublished Page video."""
        video_id = self._upload(reel, published=False)
        wait(lambda: self._status(video_id, published=False), f"facebook video {video_id}",
             self.timeout, self.poll_interval)
        return video_id

    def rights(self, video_id: str) -> rights.RightsCheck:
        return rights.check(self.graph, self.name, video_id, self.rights_timeout,
                            self.poll_interval)

    def remove(self, remote_id: str) -> None:
        self.graph.delete(remote_id)

    def cover(self, video_id: str, reel) -> bool:
        """The validated cover image as the preferred thumbnail; never fails the publication."""
        jpg = getattr(reel, "cover_image", None)
        if not jpg or not Path(jpg).is_file():
            return False
        try:
            self.graph.post_file(f"{video_id}/thumbnails", "source", Path(jpg),
                                 is_preferred="true")
        except PublisherError as e:
            print(f"warning: facebook video {video_id}: cover not set ({e})", file=sys.stderr)
            return False
        print(f"facebook: cover of {video_id} set ({Path(jpg).name})", file=sys.stderr)
        return True

    def commit(self, draft_id: str, reel) -> PublishResult:
        """Publish the checked video: sent again as published, the unpublished copy deleted."""
        try:
            video_id = self._upload(reel, published=True)
            wait(lambda: self._status(video_id, published=True), f"facebook video {video_id}",
                 self.timeout, self.poll_interval)
        except (PublisherError, KeyError) as e:
            uploaded = locals().get("video_id")
            where = (f"the published video {uploaded} may be live anyway: check the Page; "
                     f"unpublished copy {draft_id} left" if uploaded else
                     f"checked but not published; unpublished copy {draft_id} left")
            return PublishResult(self.name, PublishStatus.FAILED, remote_id=uploaded or draft_id,
                                 error=f"{e} ({where})")
        try:
            if draft_id != video_id:
                self.graph.delete(draft_id)
        except GraphError:
            pass                        # an unpublished copy left: harmless, nobody sees it
        self.cover(video_id, reel)
        link = None
        try:
            link = self.graph.get(video_id, fields="permalink_url").get("permalink_url")
        except GraphError:
            pass
        if link and link.startswith("/"):
            link = f"https://www.facebook.com{link}"
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=video_id,
                             url=link or f"https://www.facebook.com/{video_id}")
