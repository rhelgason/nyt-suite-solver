"""
Minimal dependency-free SVG chart generation for the README stats section.

Mermaid renders well for simple bars but cannot draw a legend or a readable
multi-series line chart, so the cumulative-solves chart is emitted as a small
hand-built SVG instead. Standard library only, per the stats tooling's
no-dependency rule.
"""
from typing import List, Optional, Tuple
import math

WIDTH = 760
HEIGHT = 400
M_LEFT = 52
M_RIGHT = 20
M_TOP = 44
M_BOTTOM = 52

PLOT_W = WIDTH - M_LEFT - M_RIGHT
PLOT_H = HEIGHT - M_TOP - M_BOTTOM

Series = Tuple[str, str, List[float]]  # (name, color, values)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nice_max(value: float) -> int:
    if value <= 0:
        return 1
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if value <= step:
            return step
    magnitude = 10 ** (len(str(int(value))) - 1)
    return int(math.ceil(value / magnitude) * magnitude)


def _x(i: int, n: int) -> float:
    return M_LEFT if n <= 1 else M_LEFT + PLOT_W * i / (n - 1)


def _y(value: float, y_max: int) -> float:
    return M_TOP + PLOT_H * (1 - value / y_max)


def line_chart(title: str, x_labels: List[str], series: List[Series],
               y_label: str = "", max_x_ticks: int = 8) -> str:
    n = len(x_labels)
    y_max = _nice_max(max((max(vals) for _, _, vals in series if vals), default=0))
    baseline = M_TOP + PLOT_H

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{WIDTH / 2:.0f}" y="26" text-anchor="middle" font-size="16" font-weight="600" fill="#1a1a1a">{_escape(title)}</text>',
    ]

    # horizontal gridlines + y-axis tick labels
    y_ticks = 4
    for t in range(y_ticks + 1):
        value = y_max * t / y_ticks
        yy = _y(value, y_max)
        out.append(f'<line x1="{M_LEFT}" y1="{yy:.1f}" x2="{M_LEFT + PLOT_W}" y2="{yy:.1f}" stroke="#eaeaea"/>')
        out.append(f'<text x="{M_LEFT - 8}" y="{yy + 4:.1f}" text-anchor="end" fill="#888">{value:.0f}</text>')

    # x-axis tick labels, thinned to at most max_x_ticks
    step = max(1, math.ceil(n / max_x_ticks))
    for i in range(0, n, step):
        out.append(
            f'<text x="{_x(i, n):.1f}" y="{baseline + 18:.1f}" text-anchor="middle" fill="#888">{_escape(x_labels[i])}</text>'
        )

    # axes
    out.append(f'<line x1="{M_LEFT}" y1="{baseline}" x2="{M_LEFT + PLOT_W}" y2="{baseline}" stroke="#bbb"/>')
    out.append(f'<line x1="{M_LEFT}" y1="{M_TOP}" x2="{M_LEFT}" y2="{baseline}" stroke="#bbb"/>')
    if y_label:
        out.append(
            f'<text x="14" y="{M_TOP + PLOT_H / 2:.0f}" text-anchor="middle" fill="#888" '
            f'transform="rotate(-90 14 {M_TOP + PLOT_H / 2:.0f})">{_escape(y_label)}</text>'
        )

    # series polylines
    for _, color, vals in series:
        points = " ".join(f"{_x(i, n):.1f},{_y(v, y_max):.1f}" for i, v in enumerate(vals))
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{points}"/>')

    # legend, top-left inside the plot (empty there since cumulative lines rise rightward)
    lx, ly = M_LEFT + 12, M_TOP + 10
    for k, (name, color, _) in enumerate(series):
        yy = ly + k * 18
        out.append(f'<rect x="{lx}" y="{yy - 9}" width="12" height="12" rx="2" fill="{color}"/>')
        out.append(f'<text x="{lx + 18}" y="{yy + 1}" fill="#333">{_escape(name)}</text>')

    out.append("</svg>")
    return "\n".join(out)
