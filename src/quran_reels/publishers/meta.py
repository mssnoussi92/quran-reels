"""Meta Graph API client and Page token check, shared by Facebook and Instagram.

The token travels in the Authorization header and error messages are rebuilt from the
Graph error, never from the request URL, so it cannot end up in a log.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from quran_reels import __version__
from quran_reels.publishers.base import PublisherError, wait  # noqa: F401 (re-export)

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com"
USER_AGENT = f"quran-reels/{__version__} (+https://github.com/mssnoussi92/quran-reels)"

REQUIRED_SCOPES = {
    "facebook": {"pages_show_list", "pages_read_engagement", "pages_manage_posts"},
    "instagram": {"instagram_basic", "instagram_content_publish", "pages_show_list"},
}

RENEW = (
    "Renouveler : explorateur Graph → jeton utilisateur → prolonger → me/accounts → copier le "
    "jeton de la Page → GitHub, Settings → Secrets and variables → Actions → META_PAGE_TOKEN."
)


class GraphError(PublisherError):
    pass


class TokenProblem(RuntimeError):
    pass


class Graph:
    def __init__(self, token: str, version: str, session: requests.Session | None = None,
                 timeout: float = 120):
        self.token = token
        self.version = version
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout

    def _call(self, method: str, url: str, what: str, **kw: Any) -> dict:
        try:
            r = self.session.request(method, url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise GraphError(f"{what}: network error ({type(e).__name__})", transient=True) from None
        try:
            body = r.json()
        except ValueError:
            body = {}
        body = body if isinstance(body, dict) else {}
        err = body.get("error")
        if r.status_code >= 400 or err:
            err = err if isinstance(err, dict) else {}
            # rupload.facebook.com answers {"debug_info": {"type": ..., "message": ...}}
            debug = body.get("debug_info") if isinstance(body.get("debug_info"), dict) else {}
            detail = (err.get("error_user_msg") or err.get("message") or debug.get("message")
                      or self._snippet(r) or "no details")
            codes = ", ".join(f"{k} {v}" for k, v in (
                ("HTTP", r.status_code), ("type", debug.get("type")), ("code", err.get("code")),
                ("error_subcode", err.get("error_subcode")), ("fbtrace_id", err.get("fbtrace_id")))
                if v)
            raise GraphError(f"{what}: {detail} ({codes})",
                             transient=r.status_code >= 500 or bool(err.get("is_transient"))
                             or bool(debug.get("retriable")))
        return body

    def _snippet(self, r: requests.Response) -> str:
        """Start of a non-JSON error body, with the token blanked out should it appear."""
        try:
            text = r.text or ""
        except Exception:  # noqa: BLE001
            return ""
        return " ".join(text.replace(self.token, "***").split())[:300]

    def _auth(self, scheme: str = "Bearer") -> dict[str, str]:
        return {"Authorization": f"{scheme} {self.token}"}

    def get(self, path: str, **params: Any) -> dict:
        return self._call("GET", f"{GRAPH}/{self.version}/{path}", f"GET {path}",
                          params=params, headers=self._auth())

    def post(self, path: str, **data: Any) -> dict:
        return self._call("POST", f"{GRAPH}/{self.version}/{path}", f"POST {path}",
                          data=data, headers=self._auth())

    def post_file(self, path: str, field: str, file: Path, **data: Any) -> dict:
        """Multipart upload of a small file (Page photos)."""
        with file.open("rb") as f:
            return self._call("POST", f"{GRAPH}/{self.version}/{path}", f"POST {path}",
                              data=data, files={field: (file.name, f, "image/jpeg")},
                              headers=self._auth())

    def delete(self, path: str) -> dict:
        return self._call("DELETE", f"{GRAPH}/{self.version}/{path}", f"DELETE {path}",
                          headers=self._auth())

    def upload(self, url: str, video: Path, what: str) -> dict:
        """Binary upload to rupload.facebook.com (Reels and Instagram resumable uploads)."""
        size = video.stat().st_size
        headers = {**self._auth("OAuth"), "offset": "0", "file_size": str(size),
                   "Content-Type": "application/octet-stream"}
        with video.open("rb") as f:
            return self._call("POST", url, what, data=f, headers=headers)


@dataclass
class TokenReport:
    page_id: str
    page_name: str
    instagram_id: str | None
    scopes: set[str]
    expires_at: datetime | None              # None: never
    data_access_expires_at: datetime
    days_left: float
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"Jeton de Page « {self.page_name} » : accès aux données jusqu'au "
                f"{self.data_access_expires_at:%Y-%m-%d} ({self.days_left:.0f} jours)")


def _when(ts: Any) -> datetime | None:
    return datetime.fromtimestamp(int(ts), UTC) if ts else None


def check_token(graph: Graph, page_id: str, ig_user_id: str | None, platforms: list[str],
                min_days: float = 14, now: datetime | None = None) -> TokenReport:
    """Fail (TokenProblem) unless the Page token can publish for at least min_days more."""
    now = now or datetime.now(UTC)
    d = graph.get("debug_token", input_token=graph.token).get("data") or {}
    problems: list[str] = []

    if not d.get("is_valid"):
        reason = (d.get("error") or {}).get("message", "")
        raise TokenProblem(f"META_PAGE_TOKEN n'est pas valide. {reason}\n{RENEW}".strip())
    if d.get("type") != "PAGE":
        problems.append(f"META_PAGE_TOKEN est un jeton {d.get('type')}, pas un jeton de Page.")
    if d.get("profile_id") and str(d["profile_id"]) != str(page_id):
        problems.append(f"Le jeton appartient à la Page {d['profile_id']}, pas à META_PAGE_ID.")

    scopes = set(d.get("scopes") or [])
    missing = set().union(*(REQUIRED_SCOPES[p] for p in platforms)) - scopes
    if missing:
        problems.append(f"Permissions manquantes : {', '.join(sorted(missing))}.")

    expires_at = _when(d.get("expires_at"))
    if expires_at and (expires_at - now).total_seconds() < min_days * 86400:
        problems.append(f"Le jeton expire le {expires_at:%Y-%m-%d}.")
    data_access = _when(d.get("data_access_expires_at"))
    if data_access is None:
        problems.append("debug_token ne donne pas data_access_expires_at.")
        days_left = 0.0
    else:
        days_left = (data_access - now).total_seconds() / 86400
        if days_left < min_days:
            problems.append(
                f"L'accès aux données du jeton expire le {data_access:%Y-%m-%d} "
                f"(dans {max(days_left, 0):.0f} jours, minimum {min_days:.0f}).")

    page = graph.get(str(page_id), fields="name,instagram_business_account")
    instagram_id = (page.get("instagram_business_account") or {}).get("id")
    if "instagram" in platforms and str(instagram_id) != str(ig_user_id):
        problems.append(
            f"IG_USER_ID ({ig_user_id}) n'est pas le compte Instagram relié à la Page "
            f"({instagram_id}). Relier depuis la Page : Paramètres → Comptes liés.")

    if problems:
        raise TokenProblem("\n".join([*problems, RENEW]))
    warnings = []
    if days_left < 30:
        warnings.append(f"Accès aux données du jeton : {days_left:.0f} jours restants. {RENEW}")
    return TokenReport(page_id=str(page_id), page_name=page.get("name", ""),
                       instagram_id=instagram_id, scopes=scopes, expires_at=expires_at,
                       data_access_expires_at=data_access, days_left=days_left,
                       warnings=warnings)


@dataclass
class MetaEnv:
    page_id: str
    token: str
    ig_user_id: str | None

    @classmethod
    def from_environ(cls, platforms: list[str]) -> MetaEnv:
        names = ["META_PAGE_ID", "META_PAGE_TOKEN"] + (["IG_USER_ID"] if "instagram" in platforms
                                                       else [])
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            raise SystemExit(f"missing environment variables: {', '.join(missing)} "
                             "(GitHub Actions secrets, see docs/plateformes.md)")
        return cls(page_id=os.environ["META_PAGE_ID"], token=os.environ["META_PAGE_TOKEN"],
                   ig_user_id=os.environ.get("IG_USER_ID"))
