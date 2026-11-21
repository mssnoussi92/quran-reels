"""The charts of the « Statistiques » page: inline SVG drawn here, no chart library, for a phone
first (viewBox 440 wide, scaled to the card).

Thin marks, a recessive grid, a direct label on each line, a median tick on each row of dots;
every mark carries `data-tip`, which the page's script shows on hover or tap (a hit target larger
than the mark). Colours: the reference categorical palette of the dataviz method, stepped for a
dark surface and checked against the card colour (#161d42) with its validator on 2026-11-21: blue,
orange, aqua, yellow, violet, in that order, never cycled; a neutral for « other ». Text is in
ink colours, never in a series colour.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from html import escape

PLATFORM_COLOURS = {"facebook": "#3987e5", "instagram": "#d95926", "youtube": "#199e70",
                    "tiktok": "#c98500"}
SERIES = ("#3987e5", "#d95926", "#199e70", "#c98500", "#9085e9")
OTHER = "#7d84a8"
INK, INK2, MUTED = "#eef0fa", "#c9cde6", "#aab0cf"
GRID, AXIS, SURFACE = "rgba(255,255,255,.09)", "rgba(255,255,255,.22)", "#161d42"
WIDTH = 440

Point = tuple[float | None, str]


def fmt(v: float | None, d: int = 0, suffix: str = "") -> str:
    """French: a narrow space between thousands, a decimal comma; « — » for nothing."""
    if v is None:
        return "—"
    text = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return text + suffix


def _tip(text: str) -> str:
    return f'data-tip="{escape(text)}"'


def _svg(h: float, label: str, body: list[str], w: int = WIDTH) -> str:
    return (f'<svg class="chart" viewBox="0 0 {w} {h:.0f}" role="img" aria-label="{escape(label)}">'
            + "".join(body) + "</svg>")


def legend(items: Sequence[tuple[str, str]]) -> str:
    """HTML: a dot of each colour and its name (identity is never colour alone)."""
    return '<p class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{escape(n)}</span>' for n, c in items) + "</p>"


def _ticks(top: float) -> list[float]:
    """About four round steps up to `top`."""
    if top <= 0:
        return [0.0]
    raw = top / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    return [step * i for i in range(int(top / step) + 1)]


def line_chart(series: Sequence[tuple[str, str, Sequence[tuple[str, float | None]]]],
               label: str, h: int = 210) -> str:
    """Lines over the same days: [(name, colour, [(day label, value)])]. A column per day is the
    hover target and lists every line's value; each line is named at its last point."""
    xs = [x for x, _ in series[0][2]] if series else []
    ys = [y for _, _, pts in series for _, y in pts if y is not None]
    if len(xs) < 2 or not ys:
        return '<p class="muted">Pas encore assez de jours.</p>'
    top = max(ys) * 1.15 or 1
    ticks = _ticks(top)
    top = max(top, ticks[-1])
    left, right, t, b = 38, 104, 12, 26
    pw, ph = WIDTH - left - right, h - t - b

    def x_of(i: int) -> float:
        return left + pw * i / (len(xs) - 1)

    def y_of(v: float) -> float:
        return t + ph * (1 - v / top)

    g = []
    for v in ticks:
        g.append(f'<line x1="{left}" x2="{left + pw}" y1="{y_of(v):.1f}" y2="{y_of(v):.1f}" '
                 f'stroke="{GRID}"/><text x="{left - 6}" y="{y_of(v) + 4:.1f}" text-anchor="end" '
                 f'class="tick">{fmt(v)}</text>')
    every = max(1, len(xs) // 6)
    for i, x in enumerate(xs):
        if i % every == 0 or i == len(xs) - 1:
            g.append(f'<text x="{x_of(i):.1f}" y="{h - 8}" text-anchor="middle" class="tick">'
                     f'{escape(x)}</text>')
    placed: list[float] = []
    for name, colour, pts in series:
        d = " ".join(f"{'M' if not k else 'L'}{x_of(i):.1f},{y_of(y):.1f}"
                     for k, (i, y) in enumerate((i, y) for i, (_, y) in enumerate(pts)
                                                if y is not None))
        g.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
        last = max((i for i, (_, y) in enumerate(pts) if y is not None), default=None)
        if last is None:
            continue
        y = pts[last][1]
        ly = y_of(y) + 4
        while any(abs(ly - q) < 14 for q in placed):
            ly += 14
        placed.append(ly)
        g.append(f'<circle cx="{x_of(last):.1f}" cy="{y_of(y):.1f}" r="4" fill="{colour}" '
                 f'stroke="{SURFACE}" stroke-width="2"/><text x="{x_of(last) + 8:.1f}" '
                 f'y="{ly:.1f}" class="lab">{escape(name)} {fmt(y)}</text>')
    half = pw / (len(xs) - 1) / 2
    for i, x in enumerate(xs):
        values = " · ".join(f"{n} {fmt(pts[i][1])}" for n, _, pts in series)
        g.append(f'<rect class="hit" x="{x_of(i) - half:.1f}" y="{t}" width="{2 * half:.1f}" '
                 f'height="{ph}" {_tip(f"{x} — {values}")}/>')
    return _svg(h, label, g)


def strip(rows: Sequence[tuple[str, str, Sequence[Point]]], label: str, log: bool = True,
          d: int = 0, suffix: str = "", cap: float | None = None) -> str:
    """One dot per video on a row per group, a white tick at the median, the group's count after
    its name. Views on a log scale (from a few to thousands); a share on a linear one, `cap`
    showing larger values at the edge with their number."""
    rows = [(n, c, [p for p in pts if p[0] is not None]) for n, c, pts in rows]
    rows = [r for r in rows if r[2]]
    vals = [v for _, _, pts in rows for v, _ in pts if v is not None and (v > 0 or not log)]
    if not vals:
        return '<p class="muted">Pas encore de vidéo à cet âge.</p>'
    left, right, rowh = 150, 18, 30
    h = rowh * len(rows) + 34
    pw = WIDTH - left - right
    if log:
        lo, hi = max(1.0, min(vals) * 0.8), max(vals) * 1.25
        hi = max(hi, lo * 10)
        ticks = [x for x in (1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000)
                 if lo <= x <= hi]

        def x_of(v: float) -> float:
            return left + pw * (math.log10(max(v, lo)) - math.log10(lo)) / (
                math.log10(hi) - math.log10(lo))
    else:
        lo, hi = 0.0, max(vals) * 1.1
        if cap:
            hi = min(hi, cap)
        ticks = _ticks(hi)
        hi = max(hi, ticks[-1])

        def x_of(v: float) -> float:
            return left + pw * (min(v, hi) - lo) / (hi - lo)
    g = []
    for x in ticks:
        g.append(f'<line x1="{x_of(x):.1f}" x2="{x_of(x):.1f}" y1="4" y2="{h - 26}" '
                 f'stroke="{GRID}"/><text x="{x_of(x):.1f}" y="{h - 10}" text-anchor="middle" '
                 f'class="tick">{fmt(x, 0)}{suffix}</text>')
    for i, (name, colour, pts) in enumerate(rows):
        y = 18 + i * rowh
        g.append(f'<text x="{left - 10}" y="{y + 4}" text-anchor="end" class="lab2">'
                 f'{escape(name)} <tspan class="tick">({len(pts)})</tspan></text>')
        for j, (v, title) in enumerate(pts):
            jit = ((j * 37) % 9 - 4) * 1.6
            over = cap is not None and not log and v > hi
            cx = x_of(v)
            g.append(f'<g {_tip(f"{title} : {fmt(v, d, suffix)}")}><circle class="hit" '
                     f'cx="{cx:.1f}" cy="{y + jit:.1f}" r="10"/><circle cx="{cx:.1f}" '
                     f'cy="{y + jit:.1f}" r="4.5" fill="{colour}" fill-opacity=".8" '
                     f'stroke="{SURFACE}" stroke-width="1.5"/></g>')
            if over:
                g.append(f'<text x="{cx - 6:.1f}" y="{y - 8:.1f}" text-anchor="end" '
                         f'class="tick">{fmt(v, d, suffix)} ›</text>')
        mid = statistics.median(v for v, _ in pts)
        g.append(f'<g {_tip(f"{name} : médiane {fmt(mid, d, suffix)} ({len(pts)} vidéos)")}>'
                 f'<line x1="{x_of(mid):.1f}" x2="{x_of(mid):.1f}" y1="{y - 11}" y2="{y + 11}" '
                 f'stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/></g>')
    return _svg(h, label, g)


def hbars(items: Sequence[tuple[str, float]], label: str, colour: str = SERIES[2],
          suffix: str = " %", d: int = 1) -> str:
    """Horizontal bars, largest first, each with its value."""
    if not items:
        return '<p class="muted">Pas encore de données.</p>'
    left, right, rowh = 118, 54, 24
    h = rowh * len(items) + 6
    top = max(v for _, v in items) or 1
    pw = WIDTH - left - right
    g = []
    for i, (name, v) in enumerate(items):
        y = 4 + i * rowh
        bw = max(2.0, pw * v / top)
        g.append(f'<g {_tip(f"{name} : {fmt(v, d, suffix)}")}><rect class="hit" x="0" y="{y}" '
                 f'width="{WIDTH}" height="{rowh}"/><text x="{left - 8}" y="{y + 15}" '
                 f'text-anchor="end" class="lab2">{escape(name)}</text><rect x="{left}" '
                 f'y="{y + 4}" width="{bw:.1f}" height="15" rx="4" fill="{colour}"/>'
                 f'<text x="{left + bw + 6:.1f}" y="{y + 16}" class="lab">{fmt(v, d, suffix)}'
                 f'</text></g>')
    return _svg(h, label, g)


def stack100(rows: Sequence[tuple[str, dict[str, float]]], cats: Sequence[tuple[str, str]],
             label: str) -> str:
    """A 100 % bar per row, the categories in a fixed order, a 2 px gap between segments, the
    share written inside the wide ones."""
    rows = [(n, v) for n, v in rows if sum(v.values())]
    if not rows:
        return '<p class="muted">Pas encore de données.</p>'
    left, right, rowh = 150, 6, 30
    h = rowh * len(rows) + 8
    pw = WIDTH - left - right
    g = []
    for i, (name, vals) in enumerate(rows):
        y = 6 + i * rowh
        total = sum(vals.values())
        x = float(left)
        g.append(f'<text x="{left - 8}" y="{y + 14}" text-anchor="end" class="lab2">'
                 f'{escape(name)}</text>')
        for cat, colour in cats:
            v = vals.get(cat, 0)
            bw = pw * v / total
            if bw < 0.5:
                continue
            share = 100 * v / total
            ink = "#0d1330" if colour == SERIES[3] else "#ffffff"
            g.append(f'<g {_tip(f"{name} · {cat} : {fmt(share, 0)} % ({fmt(v)} vues)")}>'
                     f'<rect x="{x:.1f}" y="{y}" width="{max(0.5, bw - 2):.1f}" height="18" rx="3" '
                     f'fill="{colour}"/>'
                     + (f'<text x="{x + bw / 2 - 1:.1f}" y="{y + 13}" text-anchor="middle" '
                        f'class="in" fill="{ink}">{share:.0f} %</text>' if bw > 34 else "")
                     + "</g>")
            x += bw
    return _svg(h, label, g)


def curves(series: Sequence[tuple[str, str, Sequence[tuple[float, float]]]], label: str,
           x_max: float, x_label: Callable[[float], str], x_ticks: Sequence[float],
           h: int = 220) -> str:
    """Retention: [(name, colour, [(x, share of the starters)])] on one scale; the share may pass
    100 % (a Short watched again). Each curve named at its end; a column per tick shows them all."""
    ys = [y for _, _, pts in series for _, y in pts]
    if not ys:
        return '<p class="muted">Pas encore de courbe.</p>'
    top = min(2.0, max(1.0, max(ys) * 1.05))
    left, right, t, b = 42, 150, 12, 28
    pw, ph = WIDTH - left - right, h - t - b

    def x_of(x: float) -> float:
        return left + pw * min(x, x_max) / x_max

    def y_of(v: float) -> float:
        return t + ph * (1 - min(v, top) / top)

    g = []
    for v in (0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        if v <= top:
            g.append(f'<line x1="{left}" x2="{left + pw}" y1="{y_of(v):.1f}" y2="{y_of(v):.1f}" '
                     f'stroke="{AXIS if v == 1.0 else GRID}"/><text x="{left - 6}" '
                     f'y="{y_of(v) + 4:.1f}" text-anchor="end" class="tick">{v * 100:.0f} %</text>')
    for x in x_ticks:
        g.append(f'<text x="{x_of(x):.1f}" y="{h - 9}" text-anchor="middle" class="tick">'
                 f'{escape(x_label(x))}</text>')
    ends = []
    for name, colour, pts in series:
        if not pts:
            continue
        d = " ".join(f"{'M' if not i else 'L'}{x_of(x):.1f},{y_of(y):.1f}"
                     for i, (x, y) in enumerate(pts))
        g.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                 f'stroke-linejoin="round"/>')
        ends.append((y_of(pts[-1][1]) + 4, name, colour))
    # Each curve named in the right margin, level with its last point, from the bottom up 14 px
    # apart and never below the plot (the x ticks are there): a short dash of its colour first.
    floor = t + ph + 4
    for ly, name, colour in sorted(ends, reverse=True):
        ly = min(ly, floor)
        floor = ly - 14
        g.append(f'<line x1="{left + pw + 8}" x2="{left + pw + 18}" y1="{ly - 4:.1f}" '
                 f'y2="{ly - 4:.1f}" stroke="{colour}" stroke-width="2"/><text '
                 f'x="{left + pw + 22:.1f}" y="{ly:.1f}" class="lab">{escape(name)}</text>')
    for k, x in enumerate(x_ticks):
        values = []
        for name, _, pts in series:
            near = min(pts, key=lambda p: abs(p[0] - x), default=None)
            if near and abs(near[0] - x) <= x_max / 20:
                values.append(f"{name} {near[1] * 100:.0f} %")
        if not values:
            continue
        lo = x_of(x_ticks[k - 1]) if k else left
        hi = x_of(x_ticks[k + 1]) if k + 1 < len(x_ticks) else left + pw
        x0, x1 = (lo + x_of(x)) / 2, (x_of(x) + hi) / 2
        g.append(f'<rect class="hit" x="{x0:.1f}" y="{t}" width="{max(1.0, x1 - x0):.1f}" '
                 f'height="{ph}" {_tip(f"{x_label(x)} : " + " · ".join(values))}/>')
    return _svg(h, label, g)

