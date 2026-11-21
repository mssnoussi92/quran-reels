"""The dashboard of the « Statistiques » page (owner's choice, 2026-11-21: « un dashboard complet,
bien classé, utile aux autres sessions pour faire des audits et voir ce qui marche et ce qui ne
marche pas, avec des courbes »), from the design he validated the same day.

Two outputs, both data (the page draws the charts from them, catalog/charts.py):

- `dataset()`: one row per video and per platform, everything known about it (kind, series,
  passage, reciter, background, length, day and hour, short version, title) and its numbers at
  48 h, 7 days, 28 days and the latest reading, plus the YouTube Studio numbers of the owner's
  exports and the YouTube detail of the night. Published as `catalog/dataset.json`: the review and
  any session audit from that file.
- `compute()`: what the page shows: followers, each kind of video as a row of dots, audits (by
  reciter, background, length, series, weekday, short version against whole), before and after
  each change (`trials` of config/insights.yaml), the YouTube detail (where views come from, who
  watches, how many stay, what people search), Facebook's retention, TikTok's captures, what is
  still missing and when it last came.

The prudence rule of the page holds everywhere: a group of fewer than `compare.min_videos` videos
is marked, and no difference is claimed below `compare.min_points` points.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from quran_reels.insights.classify import KINDS

SHORT_KIND = {   # kind → a label that fits beside a chart's row on a phone
    "reel-morning": "Reel du matin", "reel-kahf": "Al-Kahf (vendredi)",
    "reel-series": "Reel de série", "reel-on-demand": "Reel à la demande",
    "reel-hand": "Reel à la main", "word": "Word of the day", "theme-film": "Film",
    "theme-short": "Short thématique", "theme-short-cut": "Short, version courte",
    "theme-episode": "Épisode de série", "other": "Autre"}
GROUPS = ("Reels", "Shorts thématiques", "Films")
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
LENGTHS = ((30, "moins de 30 s"), (60, "30 s à 1 min"), (90, "1 min à 1 min 30"),
           (180, "1 min 30 à 3 min"), (10 ** 6, "plus de 3 min"))
SOURCES = {"SHORTS": "Fil des Shorts", "YT_SEARCH": "Recherche", "RELATED_VIDEO": "Suggérées",
           "SUBSCRIBER": "Abonnés", "YT_CHANNEL": "Page de la chaîne"}
OTHER_SOURCE = "Autres"
COUNTRIES = {"DZ": "Algérie", "SY": "Syrie", "MA": "Maroc", "UZ": "Ouzbékistan", "IQ": "Irak",
             "EG": "Égypte", "DE": "Allemagne", "SA": "Arabie saoudite", "JO": "Jordanie",
             "ID": "Indonésie", "FR": "France", "TN": "Tunisie", "TR": "Turquie", "IN": "Inde",
             "LB": "Liban", "YE": "Yémen", "SN": "Sénégal", "PS": "Palestine", "OM": "Oman",
             "AE": "Émirats arabes unis", "ES": "Espagne", "KW": "Koweït", "SO": "Somalie",
             "LY": "Libye", "SD": "Soudan", "QA": "Qatar", "BH": "Bahreïn", "MR": "Mauritanie",
             "GB": "Royaume-Uni", "US": "États-Unis", "BE": "Belgique", "CA": "Canada",
             "PK": "Pakistan", "BD": "Bangladesh", "MY": "Malaisie", "NL": "Pays-Bas",
             "IT": "Italie", "SE": "Suède"}
STUDIO = ("impressions", "ctr", "viewed_pct")
PLATFORMS = ("facebook", "instagram", "youtube", "tiktok")
PLATFORM_NAMES = {"facebook": "Facebook", "instagram": "Instagram", "youtube": "YouTube",
                  "tiktok": "TikTok"}


def group_of(kind: str) -> str | None:
    if kind.startswith("reel"):
        return "Reels"
    if kind == "theme-film":
        return "Films"
    if kind.startswith("theme"):
        return "Shorts thématiques"
    return None


def _median(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def _length(seconds: float | None) -> str | None:
    if not seconds:
        return None
    return next(name for top, name in LENGTHS if seconds < top)


def _snap(rec: dict, name: str) -> dict[str, Any] | None:
    s = (rec.get("snapshots") or {}).get(name)
    if not s:
        return None
    return {"age_h": s.get("age_h"), "at": s.get("at"), **(s.get("m") or {})}


def _series_of(rec: dict) -> str:
    ref = rec.get("ref") or {}
    if ref.get("series"):
        return str(ref["series"])
    item = ref.get("item") or ""
    return item.split("/", 1)[0] if "/" in item else ""


def dataset(posts: dict[str, dict], manual: list[dict], keep: Callable[[dict], bool],
            key_of: Callable[[dict], str], tz: ZoneInfo, backgrounds: dict[str, dict],
            series_names: dict[str, str], reciters: dict[str, str],
            detail: dict | None) -> list[dict[str, Any]]:
    """One row per video and platform (see the module). `keep` drops what the page drops (a post
    gone, a draft left by a test); `key_of` finds the video of a manual entry (a capture, an
    export); `backgrounds` gives a slot's background ({"id", "theme", "kind"}) by its key."""
    yt_detail = {v["id"]: v for v in (detail or {}).get("videos") or []}
    rows: list[dict[str, Any]] = []
    by_key: dict[str, dict] = {}
    for uid, rec in sorted(posts.items(), key=lambda kv: kv[1].get("published", "")):
        if not keep(rec):
            continue
        try:
            published = datetime.fromisoformat(rec["published"])
        except (KeyError, ValueError):
            continue
        ref = rec.get("ref") or {}
        key = rec.get("key") or uid
        kind = rec.get("kind", "other")
        local = published.astimezone(tz)
        bg = backgrounds.get(key) or {}
        series = _series_of(rec)
        row: dict[str, Any] = {
            "video": key, "platform": rec.get("platform"), "id": uid, "kind": kind,
            "kind_label": KINDS.get(kind, kind), "group": group_of(kind),
            "label": rec.get("label") or key, "title": rec.get("first_line") or "",
            "url": rec.get("url") or "", "published": published.isoformat(),
            "weekday": local.weekday(), "hour": f"{local:%H:%M}",
            "seconds": rec.get("seconds"), "length": _length(rec.get("seconds")),
            "series": series, "series_label": series_names.get(series, series),
            "passage": ref.get("passage") or "", "theme": ref.get("theme") or "",
            "reciter": reciters.get(ref.get("reciter") or "", ref.get("reciter") or ""),
            "background": bg.get("id") or "", "background_theme": bg.get("theme") or "",
            "background_kind": bg.get("kind") or "",
            "cut": bool(ref.get("cut")), "cut_file": ref.get("cut") or "",
            "m48": _snap(rec, "48h"), "m7d": _snap(rec, "7d"), "m28d": _snap(rec, "28d"),
            "latest": _snap(rec, "latest")}
        if rec.get("platform") == "youtube":
            v = yt_detail.get(uid.split(":", 1)[1])
            if v:
                row["yt"] = {
                    "sources": {s["insightTrafficSourceType"]: s["pct"]
                                for s in v.get("sources") or []},
                    "countries": {c["country"]: c["pct"] for c in (v.get("countries") or [])[:5]},
                    "engaged": v.get("engaged")}
        rows.append(row)
        by_key.setdefault(key, row)
    # The owner's captures and exports: YouTube Studio's numbers join the YouTube row; a TikTok
    # capture is a row of its own (TikTok has no other source), with the video's attributes.
    for e in sorted(manual, key=lambda e: e.get("seen", "")):
        key = key_of(e)
        m = e.get("m") or {}
        if e.get("platform") == "youtube":
            target = next((r for r in rows if r["video"] == key and r["platform"] == "youtube"),
                          None)
            studio = {k: m[k] for k in STUDIO if m.get(k) is not None}
            if target is not None and studio:
                target["studio"] = (target.get("studio") or {}) | studio | {"seen": e.get("seen")}
            continue
        if e.get("platform") != "tiktok":
            continue
        base = by_key.get(key) or {}
        row = {k: base.get(k) for k in ("kind", "kind_label", "group", "label", "seconds",
                                        "length", "series", "series_label", "passage", "theme",
                                        "reciter", "background", "background_theme",
                                        "background_kind", "weekday", "hour")}
        row |= {"video": key, "platform": "tiktok", "id": f"tiktok:{key}",
                "title": base.get("title") or e.get("video", ""),
                "published": e.get("published") or base.get("published") or "",
                "cut": False, "cut_file": "", "m48": None, "m7d": None, "m28d": None,
                "latest": dict(m) | {"seen": e.get("seen")}}
        if not row["kind"]:
            row |= {"kind": "other", "kind_label": KINDS["other"], "label": e.get("video", "")}
        rows = [r for r in rows if r["id"] != row["id"]] + [row]       # the latest capture
    return rows


# ---------------------------------------------------------------- what the page shows

def _value(row: dict, metric: str, at: str = "m48") -> float | None:
    m = row.get(at) or {}
    v = m.get(metric)
    return float(v) if isinstance(v, (int, float)) else None


def _followers(accounts: dict, tz_today: date) -> dict[str, Any]:
    days = sorted(set().union(*[set(v) for v in accounts.values()])) if accounts else []
    days = days[-35:]
    lines, tiles = [], []
    for p in ("youtube", "facebook", "instagram"):
        per = accounts.get(p) or {}
        pts = [(d, (per.get(d) or {}).get("followers_count")) for d in days]
        known = [(d, v) for d, v in pts if v is not None]
        if not known:
            continue
        lines.append({"platform": p, "name": PLATFORM_NAMES[p], "points": pts})
        last_day, now = known[-1]
        week = (date.fromisoformat(last_day) - timedelta(days=7)).isoformat()
        before = [v for d, v in known if d <= week]
        tiles.append({"platform": p, "name": PLATFORM_NAMES[p], "now": now, "day": last_day,
                      "week": now - before[-1] if before else None,
                      "since": now - known[0][1], "first": known[0][0]})
    return {"days": days, "lines": lines, "tiles": tiles}


def _kind_rows(rows: list[dict], platform: str, metric: str,
               at: str = "m48") -> list[dict[str, Any]]:
    out = []
    for kind in KINDS:
        if kind in ("other", "word") and metric != "views":
            continue
        pts = [{"v": _value(r, metric, at), "label": r["label"]} for r in rows
               if r["platform"] == platform and (("theme-short-cut" if r["cut"] else r["kind"])
                                                 == kind)]
        pts = [p for p in pts if p["v"] is not None]
        if pts:
            out.append({"kind": kind, "name": SHORT_KIND.get(kind, kind), "points": pts})
    return out


def _audit(rows: list[dict], attr: Callable[[dict], str | None], platforms: tuple[str, ...],
           order: list[str] | None, min_videos: int) -> list[dict[str, Any]]:
    """A table: one line per value of `attr`, per platform the count, the median views and the
    median share watched at 48 h."""
    values: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        if r["platform"] not in platforms or not r.get("m48"):
            continue
        a = attr(r)
        if a:
            values.setdefault(a, {}).setdefault(r["platform"], []).append(r)
    names = [v for v in (order or []) if v in values] + sorted(
        v for v in values if v not in (order or []))
    out = []
    for name in names:
        cells = {}
        for p in platforms:
            rs = values[name].get(p) or []
            cells[p] = {"n": len(rs), "few": len(rs) < min_videos,
                        "views": _median(_value(r, "views") for r in rs),
                        "watch": _median(_value(r, "watch_pct") for r in rs)}
        out.append({"name": name, "cells": cells,
                    "n": max((c["n"] for c in cells.values()), default=0)})
    return out


def _pick(rows: list[dict], platform: str, kinds: list[str], metric: str, lo: date,
          hi: date) -> list[float]:
    """The 48 h values of `metric` of the videos published in [lo, hi) on `platform`, of one of
    `kinds` (a kind or a group: « Reels »), any kind when empty."""
    return [v for r in rows if r["platform"] == platform
            and (not kinds or r["kind"] in kinds or r.get("group") in kinds)
            and lo <= date.fromisoformat(r["published"][:10]) < hi
            and (v := _value(r, metric)) is not None]


def _before_after(rows: list[dict], trials: list[dict], min_videos: int,
                  today: date) -> list[dict[str, Any]]:
    out = []
    for t in trials:
        try:
            since = date.fromisoformat(str(t.get("since", ""))[:10])
        except ValueError:
            continue
        platforms = [p for p in t.get("platforms") or [] if p in PLATFORMS]
        kinds = t.get("kinds") or []
        if not platforms:
            continue
        metric = t.get("metric") or "views"
        days = int(t.get("days") or 14)
        lines = []
        for p in platforms:
            before = _pick(rows, p, kinds, metric, since - timedelta(days=days), since)
            after = _pick(rows, p, kinds, metric, since,
                          min(today + timedelta(days=1), since + timedelta(days=days)))
            mb, ma = _median(before), _median(after)
            lines.append({"platform": p, "name": PLATFORM_NAMES[p],
                          "before": mb, "n_before": len(before),
                          "after": ma, "n_after": len(after),
                          "few": len(before) < min_videos or len(after) < min_videos})
        out.append({"what": t.get("what", ""), "since": since.isoformat(),
                    "metric": metric, "days": days, "lines": lines})
    return out


def _youtube(rows: list[dict], detail: dict | None) -> dict[str, Any] | None:
    if not detail:
        return None
    kind_of = {r["id"].split(":", 1)[1]: r["kind"] for r in rows if r["platform"] == "youtube"}
    sources: dict[str, dict[str, float]] = {}
    curves: dict[str, list[dict[float, float]]] = {}
    for v in detail.get("videos") or []:
        group = group_of(kind_of.get(v["id"], ""))
        if not group:
            continue
        agg = sources.setdefault(group, {})
        for s in v.get("sources") or []:
            name = SOURCES.get(s["insightTrafficSourceType"], OTHER_SOURCE)
            agg[name] = agg.get(name, 0) + (s.get("views") or 0)
        if v.get("retention"):
            curves.setdefault(group, []).append(
                {round(x, 2): y for x, y, *_ in v["retention"] if x})
    ch = detail.get("channel") or {}
    return {
        "read": detail.get("read", ""), "from": detail.get("from", ""), "to": detail.get("to", ""),
        "sources": [{"group": g, "views": sources[g]} for g in GROUPS if g in sources],
        "countries": [{"name": COUNTRIES.get(c["country"], c["country"]), "pct": c["pct"]}
                      for c in (ch.get("countries") or [])[:10]],
        "retention": [{"group": g, "n": len(curves[g]),
                       "points": _median_curve(curves[g], [round(i / 100, 2)
                                                           for i in range(1, 101)], 1)}
                      for g in GROUPS if g in curves],
        "search": [{"term": s["insightTrafficSourceDetail"], "views": s["views"]}
                   for s in (ch.get("search_terms") or [])[:10]],
        "errors": len(detail.get("errors") or [])}


def _median_curve(curves: list[dict[float, float]], xs: list[float],
                  min_n: int) -> list[list[float]]:
    """The median of the curves at each x reached by at least `min_n` of them, rounded."""
    out = []
    for x in xs:
        here = [c[x] for c in curves if x in c]
        if len(here) >= min_n:
            out.append([x, round(statistics.median(here), 3)])
    return out


def _facebook_retention(posts: dict[str, dict], keep: Callable[[dict], bool]) -> list[dict]:
    """Facebook's own curve (share still watching, second by second): a median per group."""
    curves: dict[str, list[dict[float, float]]] = {}
    for rec in posts.values():
        if rec.get("platform") != "facebook" or not rec.get("retention") or not keep(rec):
            continue
        group = group_of(rec.get("kind", ""))
        if group:
            curves.setdefault(group, []).append(
                {float(k): float(v) for k, v in rec["retention"].items() if float(k) <= 60})
    return [{"group": g, "n": len(curves[g]),
             "points": _median_curve(curves[g], [float(x) for x in range(61)], 2)}
            for g in GROUPS if g in curves]


def _missing(settings: dict, manual: list[dict]) -> list[dict[str, Any]]:
    """What the page still lacks, how it comes, and when it last came (config/insights.yaml)."""
    out = []
    for m in settings.get("missing") or []:
        look = m.get("look") or {}
        last = ""
        for e in manual:
            if look.get("platform") and e.get("platform") != look["platform"]:
                continue
            if look.get("metric") and (e.get("m") or {}).get(look["metric"]) is None:
                continue
            if look.get("source") and e.get("source") != look["source"]:
                continue
            last = max(last, str(e.get("seen") or ""))
        out.append({"what": m.get("what", ""), "how": m.get("how", ""),
                    "often": m.get("often", ""), "last": last if look else None})
    return out


def compute(rows: list[dict], insights: dict, settings: dict, detail: dict | None,
            keep: Callable[[dict], bool], tz: ZoneInfo, now: datetime) -> dict[str, Any]:
    compare = settings.get("compare") or {}
    min_videos = int(compare.get("min_videos", 3))
    today = now.astimezone(tz).date()
    measured = [r for r in rows if r["platform"] != "tiktok"]
    reels = [r for r in measured if r["group"] == "Reels"]
    lengths = [name for _, name in LENGTHS]
    audits = [
        {"title": "Par récitateur", "note": "Reels seulement. YouTube : toujours Tawfiq "
         "As-Sayegh depuis le 11 novembre, donc pas comparé ici.",
         "platforms": ["facebook", "instagram"],
         "rows": _audit(reels, lambda r: r["reciter"] or None, ("facebook", "instagram"), None,
                        min_videos)},
        {"title": "Par fond", "note": "Reels : le thème du fond (scène générée ou clip filmé). "
         "Le fond d'un reel ancien est recalculé : sûr pour ceux publiés depuis le 22 novembre.",
         "platforms": ["facebook", "instagram", "youtube"],
         "rows": _audit(reels, lambda r: (f"{r['background_theme']} · {r['background_kind']}"
                                          if r["background_theme"] else None),
                        ("facebook", "instagram", "youtube"), None, min_videos)},
        {"title": "Par durée", "note": "Toutes les vidéos (le type compte aussi : un film est "
         "long).", "platforms": ["facebook", "instagram", "youtube"],
         "rows": _audit(measured, lambda r: r["length"], ("facebook", "instagram", "youtube"),
                        lengths, min_videos)},
        {"title": "Par série", "note": "La série d'un reel (sa file) ou d'une vidéo thématique.",
         "platforms": ["facebook", "instagram", "youtube"],
         "rows": _audit(measured, lambda r: r["series_label"] or None,
                        ("facebook", "instagram", "youtube"), None, min_videos)},
        {"title": "Par jour de la semaine", "note": "Heure de Paris.",
         "platforms": ["facebook", "instagram", "youtube"],
         "rows": _audit(measured, lambda r: DAYS[r["weekday"]],
                        ("facebook", "instagram", "youtube"), list(DAYS), min_videos)},
        {"title": "Version courte contre short entier", "note": "Shorts thématiques, Facebook et "
         "Instagram (YouTube : la version publiée à la main est reconnue à sa durée).",
         "platforms": ["facebook", "instagram", "youtube"],
         "rows": _audit([r for r in measured if r["group"] == "Shorts thématiques"],
                        lambda r: "version courte" if r["cut"] else "short entier",
                        ("facebook", "instagram", "youtube"),
                        ["short entier", "version courte"], min_videos)},
    ]
    studio = [r for r in measured if r.get("studio")]
    ctr_rows = []
    for kind in KINDS:
        pts = [{"v": r["studio"].get("ctr"), "label": r["label"]} for r in studio
               if r["kind"] == kind and r["studio"].get("ctr") is not None]
        if pts:
            ctr_rows.append({"kind": kind, "name": SHORT_KIND.get(kind, kind), "points": pts})
    tiktok = sorted((r for r in rows if r["platform"] == "tiktok"),
                    key=lambda r: r.get("published") or "", reverse=True)
    return {
        "min_videos": min_videos, "min_points": int(compare.get("min_points", 12)),
        "followers": _followers(insights.get("accounts") or {}, today),
        "views": {p: _kind_rows(measured, p, "views") for p in ("facebook", "instagram",
                                                                  "youtube")},
        "watch": {p: _kind_rows(measured, p, "watch_pct") for p in ("facebook", "instagram",
                                                                      "youtube")},
        "engaged": _kind_rows(measured, "youtube", "engaged"),
        "ctr": {"rows": ctr_rows, "seen": max((r["studio"].get("seen") or "" for r in studio),
                                              default="")},
        "audits": audits,
        "trials": [{k: str(t.get(k, "")) for k in ("what", "since", "where", "judge")}
                   for t in settings.get("trials") or []],
        "before_after": _before_after(measured, settings.get("trials") or [], min_videos, today),
        "youtube": _youtube(measured, detail),
        "facebook_retention": _facebook_retention(insights.get("posts") or {}, keep),
        "tiktok": [{"label": r["label"], "kind": SHORT_KIND.get(r["kind"], r["kind"]),
                    "seen": (r.get("latest") or {}).get("seen", ""), "m": r.get("latest") or {}}
                   for r in tiktok],
        "missing": _missing(settings, insights.get("manual") or []),
    }


# ---------------------------------------------------------------- the figures

def figures(dash: dict[str, Any]) -> dict[str, Any]:
    """The SVG of each chart (catalog/charts.py), drawn when the page is written: data.json keeps
    the numbers only."""
    from quran_reels.catalog import charts

    colour = charts.PLATFORM_COLOURS
    out: dict[str, Any] = {}
    f = dash.get("followers") or {}
    out["followers"] = charts.line_chart(
        [(line["name"], colour[line["platform"]],
          [(d[8:] + "/" + d[5:7], v) for d, v in line["points"]]) for line in f.get("lines", [])],
        "abonnés, jour par jour")

    def rows(items: list[dict], c: str) -> list:
        return [(k["name"], c, [(p["v"], p["label"]) for p in k["points"]]) for k in items]

    out["views"] = {p: charts.strip(rows(dash["views"].get(p, []), colour[p]),
                                    f"{PLATFORM_NAMES[p]} : vues à 48 h")
                    for p in ("facebook", "instagram", "youtube")}
    out["watch"] = {p: charts.strip(rows(dash["watch"].get(p, []), colour[p]),
                                    f"{PLATFORM_NAMES[p]} : part regardée", log=False, d=1,
                                    suffix=" %", cap=300)
                    for p in ("facebook", "instagram", "youtube")}
    out["engaged"] = charts.strip(rows(dash.get("engaged") or [], colour["youtube"]),
                                  "YouTube : vues engagées à 48 h")
    out["ctr"] = charts.strip(rows((dash.get("ctr") or {}).get("rows") or [], colour["youtube"]),
                              "YouTube : taux de clics des miniatures", log=False, d=1,
                              suffix=" %")
    yt = dash.get("youtube")
    if yt:
        cats = [(name, charts.SERIES[i]) for i, name in enumerate(SOURCES.values())]
        cats.append((OTHER_SOURCE, charts.OTHER))
        out["sources_legend"] = charts.legend(cats)
        out["sources"] = charts.stack100([(s["group"], s["views"]) for s in yt["sources"]], cats,
                                         "YouTube : d'où viennent les vues")
        out["countries"] = charts.hbars([(c["name"], c["pct"]) for c in yt["countries"]],
                                        "YouTube : pays des spectateurs")
        out["yt_retention"] = charts.curves(
            [(f"{r['group']} ({r['n']})", charts.SERIES[GROUPS.index(r["group"])],
              [tuple(p) for p in r["points"]]) for r in yt["retention"]],
            "YouTube : part des spectateurs encore là", 1.0, lambda x: f"{x * 100:.0f} %",
            (0, 0.25, 0.5, 0.75, 1.0))
    fb = dash.get("facebook_retention") or []
    if fb:
        out["fb_retention"] = charts.curves(
            [(f"{r['group']} ({r['n']})", charts.SERIES[GROUPS.index(r["group"])],
              [tuple(p) for p in r["points"]]) for r in fb],
            "Facebook : part des spectateurs encore là, seconde par seconde", 60.0,
            lambda x: f"{x:.0f} s", (3, 10, 20, 30, 45, 60))
    return out
