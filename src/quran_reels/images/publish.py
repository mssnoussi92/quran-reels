"""Image posts: a Facebook multi-photo post and an Instagram carousel (or single image).

Instagram's API only takes images by public URL (image_url), never as an upload. Chosen
solution: the photos are first uploaded to the Page unpublished (published=false), which the
Facebook post needs anyway; Facebook then serves each one from its CDN, and that URL
(GET /{photo-id}?fields=images, the largest) is what Instagram fetches. Why not GitHub Pages:
it would mean committing three JPEGs a day to the repository (about 160 MB a year of history),
waiting for each Pages deployment, and the images would be public before the post. The CDN
URL is signed and unlisted, available as soon as the upload returns, and costs nothing more.

  1. Facebook: POST /{page}/photos (multipart, published=false) for each image → photo ids
  2. GET /{photo-id}?fields=images → CDN URLs
  3. Instagram: one container per image (image_url, is_carousel_item=true), a CAROUSEL
     container with the children and the caption, then media_publish. One image: a single
     container (Ayah of the day).
  4. Facebook: POST /{page}/feed with attached_media in order and the caption.

Dry run: steps 1-3 without media_publish nor the Facebook post; the unpublished photos are
deleted at the end. No rights check: no audio, and the images are generated.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from quran_reels.models import PublishResult, PublishStatus
from quran_reels.publishers.base import PublisherError
from quran_reels.publishers.meta import Graph, GraphError, wait


class ImagePublisher:
    def __init__(self, graph: Graph, page_id: str, ig_user_id: str | None,
                 poll_interval: float = 5, timeout: float = 300):
        self.graph = graph
        self.page_id = page_id
        self.ig_user_id = ig_user_id
        self.poll_interval = poll_interval
        self.timeout = timeout

    # ---- Facebook photos (also the source of Instagram's URLs) --------------------------

    def upload_photos(self, files: list[Path]) -> list[str]:
        return [str(self.graph.post_file(f"{self.page_id}/photos", "source", f,
                                         published="false")["id"]) for f in files]

    def photo_url(self, photo_id: str, attempts: int = 6) -> str:
        """The largest version on Facebook's CDN (may take a moment after the upload)."""
        for n in range(attempts):
            images = self.graph.get(photo_id, fields="images").get("images") or []
            if images:
                return max(images, key=lambda i: i.get("width", 0))["source"]
            time.sleep(self.poll_interval * (n + 1))
        raise GraphError(f"facebook photo {photo_id}: no image URL yet")

    def delete_photos(self, photo_ids: list[str]) -> None:
        for pid in photo_ids:
            try:
                self.graph.delete(pid)
            except GraphError:
                pass                # an unpublished photo left behind is harmless

    def facebook_post(self, photo_ids: list[str], message: str) -> PublishResult:
        try:
            media = {f"attached_media[{i}]": json.dumps({"media_fbid": pid})
                     for i, pid in enumerate(photo_ids)}
            post_id = str(self.graph.post(f"{self.page_id}/feed", message=message,
                                          **media)["id"])
        except (PublisherError, KeyError) as e:
            return PublishResult("facebook", PublishStatus.FAILED, error=str(e))
        link = None
        try:
            link = self.graph.get(post_id, fields="permalink_url").get("permalink_url")
        except GraphError:
            pass
        return PublishResult("facebook", PublishStatus.PUBLISHED, remote_id=post_id,
                             url=link or f"https://www.facebook.com/{post_id}")

    # ---- Instagram ----------------------------------------------------------------------

    def _ready(self, container_id: str) -> None:
        def status() -> tuple[bool, str]:
            c = self.graph.get(container_id, fields="status_code,status")
            code = c.get("status_code")
            if code in ("ERROR", "EXPIRED"):
                raise GraphError(f"instagram container {container_id}: {code} "
                                 f"{c.get('status', '')}".strip())
            return code in ("FINISHED", "PUBLISHED"), code
        wait(status, f"instagram container {container_id}", self.timeout, self.poll_interval)

    def instagram_container(self, urls: list[str], caption: str) -> str:
        """A container ready to publish: carousel for several images, single otherwise."""
        if len(urls) == 1:
            cid = str(self.graph.post(f"{self.ig_user_id}/media", image_url=urls[0],
                                      caption=caption)["id"])
        else:
            children = []
            for url in urls:
                child = str(self.graph.post(f"{self.ig_user_id}/media", image_url=url,
                                            is_carousel_item="true")["id"])
                self._ready(child)
                children.append(child)
            cid = str(self.graph.post(f"{self.ig_user_id}/media", media_type="CAROUSEL",
                                      children=",".join(children), caption=caption)["id"])
        self._ready(cid)
        return cid

    def instagram_publish(self, container_id: str) -> PublishResult:
        try:
            data = (self.graph.get(f"{self.ig_user_id}/content_publishing_limit",
                                   fields="quota_usage,config").get("data") or [{}])[0]
            used = data.get("quota_usage", 0)
            total = (data.get("config") or {}).get("quota_total", 50)
            if used >= total:
                raise GraphError(f"instagram: publishing limit reached ({used}/{total} in 24 h)")
            media_id = str(self.graph.post(f"{self.ig_user_id}/media_publish",
                                           creation_id=container_id)["id"])
        except (PublisherError, KeyError) as e:
            return PublishResult("instagram", PublishStatus.FAILED, remote_id=container_id,
                                 error=str(e))
        link = None
        try:
            link = self.graph.get(media_id, fields="permalink").get("permalink")
        except GraphError:
            pass
        return PublishResult("instagram", PublishStatus.PUBLISHED, remote_id=media_id, url=link)

    # ---- both ---------------------------------------------------------------------------

    def publish(self, files: list[Path], captions: dict[str, str], platforms: list[str],
                dry_run: bool = False) -> list[PublishResult]:
        """captions: per platform (each has its own hashtag limit)."""
        results: dict[str, PublishResult] = {}
        try:
            photo_ids = self.upload_photos(files)
            urls = [self.photo_url(p) for p in photo_ids] if "instagram" in platforms else []
        except (PublisherError, KeyError) as e:
            return [PublishResult(p, PublishStatus.FAILED, error=f"photo upload: {e}")
                    for p in platforms]

        if "instagram" in platforms:
            try:
                cid = self.instagram_container(urls, captions["instagram"])
                results["instagram"] = (PublishResult("instagram", PublishStatus.READY,
                                                      remote_id=cid) if dry_run
                                        else self.instagram_publish(cid))
            except (PublisherError, KeyError) as e:
                results["instagram"] = PublishResult("instagram", PublishStatus.FAILED,
                                                     error=str(e))
        if "facebook" in platforms:
            results["facebook"] = (
                PublishResult("facebook", PublishStatus.DRAFT, remote_id=",".join(photo_ids))
                if dry_run else self.facebook_post(photo_ids, captions["facebook"]))
        if dry_run or "facebook" not in platforms:
            self.delete_photos(photo_ids)   # Instagram has fetched its copies by now
        return [results[p] for p in platforms]
