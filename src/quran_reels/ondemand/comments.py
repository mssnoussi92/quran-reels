"""The comments the owner reads on a request issue, from page.data() and check.Checked.

The preview comment carries a hidden marker (MARKER + JSON): the run, the artifact, the MP4's
SHA-256 and the issue body's hash. publish.py trusts it only from github-actions[bot].
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from quran_reels.ondemand.check import Checked

MARKER = "on-demand-preview"
_MARK = re.compile(r"<!-- " + MARKER + r" (\{.*?\}) -->", re.DOTALL)
FOOTER = ("\n\n<sub>Rien n'est publié sans ta réponse. Commandes : `/publier` · `/essai` "
          "(dry run) · `/apercu` · `/mots` · `/youtube <lien>` — "
          "[comment ça marche](https://github.com/mssnoussi92/quran-reels/blob/main/docs/"
          "on-demand.md)</sub>")


def body_hash(body: str | None) -> str:
    text = (body or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def marker(meta: dict[str, Any]) -> str:
    return f"<!-- {MARKER} {json.dumps(meta, ensure_ascii=False, separators=(',', ':'))} -->"


def read_marker(text: str) -> dict | None:
    m = _MARK.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m[1])
    except ValueError:
        return None


def _block(text: str) -> list[str]:
    return ["```text", text.strip(), "```"]


def refused(checked: Checked | None, problems: list[str], passage: str = "") -> str:
    key = (checked.key if checked and checked.key else passage) or "?"
    lines = [f"## ⛔ Demande refusée · {key}", ""]
    lines += [f"- {p}" for p in problems]
    if checked and checked.suggestions:
        who = (f"durées avec {checked.reciter_label}" if checked.request.reciter != "auto"
               and checked.reciter_label else "durées du récitateur prêt le plus court")
        lines += ["", f"**Plages valides** (phrases entières, {who}) : "
                  + " · ".join(f"`{s}`" for s in checked.suggestions)]
    if checked and checked.alternatives:
        lines += ["", f"**{checked.key} avec un autre récitateur** : "
                  + " · ".join(str(s) for s in checked.alternatives)]
    lines += ["", ("Modifie le ticket (✏️ en haut du ticket) : la vérification repart toute "
                   "seule. Rien n'est publié.")]
    return "\n".join(lines) + FOOTER


def splitting(reciter: str, key: str) -> str:
    return "\n".join([
        f"## ⏳ Découpe de la récitation · {reciter} · {key}", "",
        (f"La récitation de {reciter} n'est pas encore découpée et vérifiée pour ce passage. "
         "Je la découpe maintenant (reconnaissance vocale : chaque ayah et chaque coupe sont "
         "vérifiées), en général **3 à 10 min** selon la longueur de la sourate, puis "
         "l'aperçu suit dans un autre commentaire.")]) + FOOTER


def _facts(d: dict) -> str:
    parts = [f"**Récitateur** {d['reciter']}"]
    if d.get("seconds"):
        parts.append(f"**durée** {d['seconds']:.0f} s")
    if d.get("background"):
        parts.append(f"**fond** {d['background']}")
    parts.append("**plateformes** " + ", ".join(d["platforms"]))
    return " · ".join(parts)


def preview(d: dict, meta: dict, page: str, notes: list[str]) -> str:
    v = d.get("video") or {}
    lines = [marker(meta), f"## 👀 Aperçu · {d['title']}", "", _facts(d), "",
             f"▶️ **[Ouvrir l'aperçu]({page})** (lecteur, légendes à copier)"
             + (f" · ⬇️ [MP4 d'aperçu, 540p]({v['preview']})" if v.get("preview") else ""), ""]
    if d.get("frames"):
        lines += [" ".join(f'<img src="{u}" width="32%" alt="image {i}">'
                           for i, u in enumerate(d["frames"], 1)), ""]
    for n in notes:
        lines.append(f"> ⚠️ {n}")
    if notes:
        lines.append("")
    lines += _words(d)
    lines += [("**Pour publier, réponds `/publier`.** Essai sans rien publier : `/essai` · "
               "refaire l'aperçu : `/apercu` (ou modifie le ticket)."), "",
              "<details><summary>Légendes</summary>", ""]
    for c in d["captions"]:
        lines += [f"**{c['label']}**", "", *_block(c["text"]), ""]
    lines.append("</details>")
    return "\n".join(lines) + FOOTER


def _short(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1].rsplit(" ", 1)[0] + "…"


def _words(d: dict) -> list[str]:
    """The source's word meanings for the passage, numbered, ✅ for those shown: the owner
    picks with /mots (ondemand/words.py)."""
    found = d.get("words") or []
    shown = [w for w in found if w["shown"]]
    mode = d.get("words_mode", "auto")
    how = {"auto": "choisis par les règles habituelles", "aucun": "aucun, à ta demande"}.get(
        mode, f"ton choix : {mode}")
    if not found:
        return ["**Mots expliqués** : le Muyassar n'explique aucun mot de ce passage.", ""]
    lines = [(f"<details><summary><b>Mots expliqués</b> : {len(shown)} sur {len(found)} "
              f"({how})</summary>"), ""]
    for w in found:
        mark = "✅" if w["shown"] else ("◻️" if w["usable"] else "✖️")
        tail = f" — {_short(w['gloss'])}" if w["usable"] else f" — _{w['why']}_"
        lines.append(f"- {mark} **{w['n']}** · {w['ref']} · {w['word']}{tail}")
    lines += ["", ("Pour choisir : réponds `/mots 1 4` (ces numéros, 2 au plus par ayah) · un "
                   "mot précis de la citation : `/mots 4=قلى` · `/mots aucun` · `/mots auto`. "
                   "Le sens vient toujours du Muyassar, tel quel ; un nouvel aperçu suit."),
              "", "</details>", ""]
    return lines


def _rights(r: dict) -> str:
    rights = r.get("rights")
    if not rights:
        return ""
    return ("✅ " if rights.get("clear") else "⛔ ") + str(rights.get("summary", ""))


def result(d: dict, rows: list[dict], page: str, rights_only: dict | None = None,
           tiktok_caption: str = "") -> str:
    icon = {"published": "📣", "partial": "📣", "dry-run": "🧪", "blocked": "⛔",
            "failed": "❌"}.get(d["stage"], "📣")
    lines = [f"## {icon} {d['stage_label']} · {d['title']}", "", _facts(d), "",
             "| Plateforme | Résultat | Droits (Meta) |", "|---|---|---|"]
    for r in rows:
        what = f"[{r['label']}]({r['url']})" if r.get("url") else r["label"]
        if r.get("error"):
            what += f" : {r['error']}"
        lines.append(f"| {r['name']} | {what} | {_rights(r)} |")
    if rights_only:
        lines += ["", ("Vérification des droits de Meta (brouillon vérifié puis supprimé) : "
                       f"{rights_only['summary']}")]
    if tiktok_caption:
        lines += ["", "**Légende à coller sur le brouillon TikTok** (il arrive dans ta boîte) :",
                  "", *_block(tiktok_caption)]
    yt = d.get("youtube")
    if yt and yt.get("file"):
        lines += ["", "### 📺 YouTube, à la main", "",
                  (f"1. ⬇️ **[Télécharger le MP4 1080p]({yt['file']})** (il va dans "
                   "Téléchargements, la galerie et l'app YouTube le voient)"),
                  ("2. App YouTube → ➕ → Short → la vidéo ; colle le titre, la description et "
                   "les hashtags ci-dessous (ou depuis la "
                   f"[page avec boutons Copier]({page}))"),
                  (f"3. Une fois en ligne, réponds `{yt['command']} <lien du Short>` (lien "
                   "facultatif) : c'est noté « mis en ligne à la main »."), "",
                  f"**Titre** ({len(yt['title'])}/100)", "", *_block(yt["title"]), "",
                  "**Description**", "", *_block(yt["description"]), "",
                  "**Hashtags**", "", *_block(yt["hashtags"])]
    elif yt and d["stage"] == "blocked":
        lines += ["", "📺 YouTube : pas proposé, la vérification des droits n'est pas propre."]
    for n in d.get("notes") or []:
        lines += ["", f"> ⚠️ {n}"]
    return "\n".join(lines) + FOOTER


def youtube_done(url: str | None, what: str) -> str:
    link = f" : {url}" if url else ""
    return f"✅ YouTube noté pour {what} (mis en ligne à la main){link}."
