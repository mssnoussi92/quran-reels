"""data.json → index.html (Jinja2, autoescaped). The page works without JavaScript; the script
only plays the samples, the clip previews and the generated scenes."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, FileSystemLoader, Undefined, select_autoescape

from quran_reels.catalog import SITE

THEMES = {"mountains": "montagnes", "sea": "mer", "rivers": "rivières", "dawn": "aube",
          "rain": "pluie", "gardens": "jardins", "night": "nuit", "sky": "ciel",
          "default": "par défaut", "chosen": "choisi à la main"}
STATES = {"published": ("publié", "ok"), "partial": ("en partie", "warn"),
          "failed": ("échec", "bad"), "blocked": ("bloqué (droits)", "bad"),
          "claimed": ("revendiqué, retiré", "bad"), "": ("prévu", "plan")}


def theme(tag: str) -> str:
    base = tag.replace(" (fallback)", "")
    label = THEMES.get(base, base)
    return f"{label} (repli)" if tag.endswith("(fallback)") else label


def seconds(value: Any) -> str:
    if value is None:
        return ""
    s = round(float(value))
    return f"{s} s" if s < 90 else f"{s // 60} min {s % 60:02d} s"


def number(value: Any, unit: str = "") -> str:
    """A statistic as shown: — when Meta gave nothing (never 0), French decimals."""
    if value is None or isinstance(value, Undefined):
        return "—"
    v = float(value)
    text = f"{v:.0f}" if v == int(v) or abs(v) >= 100 else f"{v:.1f}".replace(".", ",")
    return f"{text}{unit}"


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(SITE), autoescape=select_autoescape(["html", "j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters |= {"theme": theme, "seconds": seconds, "number": number}
    env.globals |= {"STATES": STATES}
    return env


def render(data: dict[str, Any]) -> str:
    shaders = {b["id"]: b["shader"] for b in data["backgrounds"]["list"] if b.get("shader")}
    return _env().get_template("index.html.j2").render(d=data, shaders=shaders)


def render_stats(data: dict[str, Any]) -> str:
    return _env().get_template("stats.html.j2").render(d=data, s=data.get("stats") or {})
