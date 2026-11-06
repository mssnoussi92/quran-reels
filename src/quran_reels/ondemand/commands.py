"""Who may drive the flow, and what a comment asks.

The repository is public: anyone can open an issue or comment. Only the owner's own issues
and comments count (login == repository owner and author_association == OWNER), checked by
the workflow's `if:` before any job starts and again here on the event file. A publication
needs the owner's `/publier` posted after the latest preview, which must come from
github-actions[bot] (anyone could paste a fake marker in a comment).
"""

from __future__ import annotations

from dataclasses import dataclass

from quran_reels.ondemand.comments import read_marker
from quran_reels.ondemand.gh import BOT

COMMANDS = {"/publier": "publish", "/publish": "publish", "/essai": "dry-run",
            "/dry-run": "dry-run", "/apercu": "preview", "/aperçu": "preview",
            "/preview": "preview", "/youtube": "youtube", "/mots": "words", "/words": "words"}


class Refused(Exception):
    """A command that cannot be carried out; the message is for the owner."""


def command(text: str | None) -> tuple[str, str]:
    """('publish', '') for «/publier»; ('youtube', 'https://…') for «/youtube https://…»;
    ('', '') when the comment is not a command (only its first line counts)."""
    first = (text or "").strip().split("\n", 1)[0].strip()
    if not first.startswith("/"):
        return "", ""
    word, _, rest = first.partition(" ")
    return COMMANDS.get(word.lower(), ""), rest.strip()


def is_owner(user: dict | None, association: str | None, owner: str) -> bool:
    return bool(user) and user.get("login") == owner and association == "OWNER"


def authorized(event: str, payload: dict, owner: str) -> str | None:
    """None when the event comes from the owner; otherwise why it is ignored."""
    if event == "workflow_dispatch":
        actor = (payload.get("sender") or {}).get("login")
        return None if actor == owner else f"lancé par {actor}, pas par {owner}"
    issue = payload.get("issue") or {}
    if event == "issues":
        if not is_owner(issue.get("user"), issue.get("author_association"), owner):
            return "ticket ouvert par un autre compte"
        if (payload.get("sender") or {}).get("login") != owner:
            return "ticket modifié par un autre compte"
        return None
    if event == "issue_comment":
        c = payload.get("comment") or {}
        if "pull_request" in issue:
            return "commentaire sur une pull request"
        return None if is_owner(c.get("user"), c.get("author_association"), owner) \
            else "commentaire d'un autre compte"
    return f"événement {event} non géré"


@dataclass
class Approval:
    meta: dict                 # the preview's marker
    preview: dict              # the preview comment
    comment: dict              # the owner's /publier or /essai


def approval(comments: list[dict], owner: str, mode: str,
             comment_id: int | None = None) -> Approval:
    """The latest bot preview and the owner's command for it (comment_id: the one that
    triggered the run; otherwise the latest such command, for a run started by hand)."""
    previews = [c for c in comments if (c.get("user") or {}).get("login") == BOT
                and read_marker(c.get("body", ""))]
    if not previews:
        raise Refused("pas d'aperçu sur ce ticket : attends-le (ou `/apercu`) avant de publier")
    last = previews[-1]
    after = [c for c in comments
             if is_owner(c.get("user"), c.get("author_association"), owner)
             and command(c.get("body"))[0] == mode and c["created_at"] > last["created_at"]]
    if comment_id is not None:
        found = [c for c in after if c["id"] == comment_id]
        if not found:
            raise Refused("cette commande précède le dernier aperçu : relis-le, puis réponds "
                          "à nouveau")
        chosen = found[0]
    elif after:
        chosen = after[-1]
    else:
        word = "/publier" if mode == "publish" else "/essai"
        raise Refused(f"pas de `{word}` du propriétaire après le dernier aperçu")
    return Approval(meta=read_marker(last["body"]), preview=last, comment=chosen)
