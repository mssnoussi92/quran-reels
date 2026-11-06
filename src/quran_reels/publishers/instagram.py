"""Instagram Reels (Instagram Graph API, account linked to the Page, Page token).

REELS container with resumable upload → binary upload → wait for status_code FINISHED
(prepare) → Meta's copyright check of the container, copyright_check_status (rights,
publishers/rights.py) → media_publish (commit). A dry run stops before media_publish: the
container is ready but nothing is posted, and Instagram drops it after 24 hours.

rupload answers 400 ProcessingFailedError to most uploads. Sometimes Instagram has the video
anyway (run #7: container FINISHED at once), sometimes the container stays IN_PROGRESS for
good (run #9: still after 15 min; 2026-11-06, run #10: three containers in a row). After that
error, a container not ready within stuck_after seconds is set aside and the video goes to a
new container, up to `attempts` times; the ones set aside are still watched, and the first
container ready is used. An unpublished container costs nothing: it is not posted and
expires after 24 hours.

Tried and dropped (2026-11-06, publish-test run #24): having Instagram fetch Facebook's copy
of the draft (video_url = GET /{video}?fields=source). That copy is 720x1280 at 201 kb/s,
and Instagram refused it anyway (container ERROR, code 2207076).
"""

from __future__ import annotations

import sys
import time

from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers import rights
from quran_reels.publishers.base import PublisherError, StillProcessing
from quran_reels.publishers.meta import RUPLOAD, Graph, GraphError

CAPTION_LIMIT = 2200


class InstagramPublisher:
    name = "instagram"
    mode = "auto"

    def __init__(self, graph: Graph, ig_user_id: str, poll_interval: float = 10,
                 timeout: float = 900, attempts: int = 3, stuck_after: float = 240,
                 max_hashtags: int | None = 5, rights_timeout: float = 600):
        self.graph = graph
        self.max_hashtags = max_hashtags    # Instagram allows 5 per post since December 2025
        self.ig_user_id = ig_user_id
        self.poll_interval = poll_interval
        self.timeout = timeout              # processing after a clean upload
        self.attempts = attempts            # containers tried when uploads fail
        self.stuck_after = stuck_after      # processing allowed after a failed upload
        self.rights_timeout = rights_timeout

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

    def _first_ready(self, cids: list[str], timeout: float) -> str:
        """The first of cids whose processing is done (in their order at each round); one in
        ERROR is dropped; transient errors are asked again. StillProcessing after timeout."""
        deadline = time.monotonic() + timeout
        live, error = list(cids), None
        while True:
            for cid in list(live):
                try:
                    done, _ = self._status(cid)
                except GraphError as e:
                    if not e.transient:
                        live.remove(cid)
                        error = e
                    continue
                if done:
                    return cid
            if not live:
                raise error or GraphError("instagram: no container left")
            if time.monotonic() >= deadline:
                raise StillProcessing(f"instagram container {', '.join(live)}: still processing "
                                      f"after {timeout:.0f} s")
            time.sleep(self.poll_interval)

    def _ready_container(self, reel: Reel, params: dict[str, str]) -> str:
        """Id of a container holding the processed video (status FINISHED)."""
        watched: list[str] = []         # containers still processing after a failed upload
        for attempt in range(1, self.attempts + 1):
            cid, failed = self._upload(reel, params)
            if not failed:
                return self._first_ready([cid, *watched], self.timeout)
            watched.append(cid)
            try:
                return self._first_ready(watched, self.stuck_after)
            except StillProcessing:
                if attempt == self.attempts:
                    raise
            print(f"warning: instagram container {', '.join(watched)} still IN_PROGRESS "
                  f"{self.stuck_after:.0f} s after the upload error, uploading again to a new "
                  f"container ({attempt + 1}/{self.attempts})", file=sys.stderr)
        raise AssertionError("unreachable")

    def _params(self, reel: Reel) -> dict[str, str]:
        text = reel.text(self.max_hashtags)
        if len(text) > CAPTION_LIMIT:
            raise PublisherError(f"caption longer than {CAPTION_LIMIT} characters")
        params = {"media_type": "REELS", "upload_type": "resumable", "caption": text,
                  "share_to_feed": "true"}
        if reel.cover_ms is not None:
            params["thumb_offset"] = str(reel.cover_ms)
        return params

    def prepare(self, reel: Reel) -> str:
        """Id of a container holding the processed reel, not published."""
        return self._ready_container(reel, self._params(reel))

    def rights(self, container_id: str) -> rights.RightsCheck:
        return rights.check(self.graph, self.name, container_id, self.rights_timeout,
                            self.poll_interval)

    def rights_after(self, remote_id: str, timeout: float = 0) -> rights.RightsCheck:
        """The copyright check of the published media (timeout 0: read once)."""
        return rights.check(self.graph, self.name, remote_id, timeout, self.poll_interval,
                            field_name=rights.AFTER)

    def remove(self, remote_id: str) -> None:
        """Take the published media down (GraphError if Meta refuses: the token needs instagram_manage_contents)."""
        self.graph.delete(remote_id)

    def commit(self, container_id: str, reel: Reel | None = None) -> PublishResult:
        try:
            self._quota()
            media_id = str(self.graph.post(f"{self.ig_user_id}/media_publish",
                                           creation_id=container_id)["id"])
        except (PublisherError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, remote_id=container_id,
                                 error=str(e))
        link = None
        try:
            link = self.graph.get(media_id, fields="permalink").get("permalink")
        except GraphError:
            pass
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=media_id, url=link)

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        """Instagram alone: prepare, check, then publish if the check is clear."""
        try:
            cid = self.prepare(reel)
        except (PublisherError, KeyError) as e:
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))
        check = self.rights(cid)
        if dry_run:
            return PublishResult(self.name, PublishStatus.READY, remote_id=cid,
                                 rights=check.as_dict())
        if not check.clear:
            return PublishResult(self.name, PublishStatus.BLOCKED, remote_id=cid,
                                 error=f"droits : {check.describe()}", rights=check.as_dict())
        result = self.commit(cid, reel)
        result.rights = check.as_dict()
        return result
