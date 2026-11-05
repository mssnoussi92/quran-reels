"""Meta's copyright check (Rights Manager), read before anything is published.

The first Facebook reel (93:1-11, 2026-11-05) was cut: Rights Manager recognised the
recitation. So the reel is uploaded unpublished first, and published only once Meta has
checked it:

- Facebook: draft reel, then GET /{video-id}?fields=copyright_check_information →
  {"status": {"status": "complete", "matches_found": false}, "copyright_matches": [...]}
- Instagram: container, then GET /{container-id}?fields=copyright_check_status →
  {"status": "complete", "matches_found": false} (match details only after publication).

We wait until the status is complete. Clear = complete and matches_found false; anything else
(a match, an error, no answer in time, a field the API does not know) blocks the publication.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from quran_reels.publishers.meta import Graph, GraphError

DONE = ("complete", "completed")         # the documentation uses both spellings
TERMINAL = ("error", "not_eligible")
FIELDS = {"facebook": "copyright_check_information", "instagram": "copyright_check_status"}


@dataclass
class RightsCheck:
    platform: str
    status: str                   # complete | error | not_eligible | timeout | unavailable
    matches_found: bool | None = None
    matches: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""              # Meta's error, when the check could not be read
    seconds: float = 0.0          # time until the answer

    @property
    def clear(self) -> bool:
        return self.status in DONE and self.matches_found is False

    def owners(self) -> str:
        """Who claims the content, as Meta names them."""
        out = []
        for m in self.matches:
            policy = (m.get("owner_copyright_policy") or {}).get("name")
            title, author = m.get("content_title"), m.get("author")
            kinds = sorted({s.get("segment_type", "") for s in m.get("matched_segments") or []
                            if s.get("segment_type")})
            text = " — ".join(x for x in (f"« {title} »" if title else "", author, policy) if x)
            out.append(text + (f" ({', '.join(kinds).lower()})" if kinds else ""))
        return " ; ".join(x for x in out if x)

    def describe(self) -> str:
        if self.clear:
            return "aucune correspondance"
        if self.status in DONE and self.matches_found:
            who = self.owners() or ("titulaire indiqué seulement après publication"
                                    if self.platform == "instagram" else "titulaire non indiqué")
            return f"contenu protégé reconnu : {who}"
        if self.status == "timeout":
            return f"vérification non terminée après {self.seconds:.0f} s"
        if self.status == "unavailable":
            return f"vérification indisponible ({self.detail or 'champ absent'})"
        return f"vérification en {self.status}" + (f" ({self.detail})" if self.detail else "")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"clear": self.clear, "summary": self.describe()}


def parse(platform: str, body: dict[str, Any]) -> tuple[str, bool | None, list[dict]]:
    """(status, matches_found, matches) from a Graph answer, both platforms' shapes."""
    info = body.get(FIELDS[platform]) or {}
    status = info.get("status")
    found = info.get("matches_found")
    if isinstance(status, dict):                     # Facebook nests status and matches_found
        found = status.get("matches_found", found)
        status = status.get("status")
    return str(status or "").lower(), found, list(info.get("copyright_matches") or [])


def check(graph: Graph, platform: str, object_id: str, timeout: float = 600,
          interval: float = 10, clock=time.monotonic, sleep=time.sleep) -> RightsCheck:
    """Poll the copyright check of an unpublished reel until Meta gives its answer."""
    start = clock()
    status, found, matches, transient = "", None, [], 0
    while True:
        try:
            status, found, matches = parse(platform, graph.get(object_id,
                                                               fields=FIELDS[platform]))
            transient = 0
        except GraphError as e:
            transient += 1
            if not e.transient or transient > 3:
                return RightsCheck(platform, "unavailable", detail=str(e),
                                   seconds=clock() - start)
        elapsed = clock() - start
        if status in DONE and found is not None:
            return RightsCheck(platform, status, bool(found), matches, seconds=elapsed)
        if status in TERMINAL:
            return RightsCheck(platform, status, found, matches, seconds=elapsed)
        if elapsed > timeout:
            return RightsCheck(platform, "timeout" if status else "unavailable", found, matches,
                               detail=f"dernier état : {status or 'aucun'}", seconds=elapsed)
        sleep(interval)
