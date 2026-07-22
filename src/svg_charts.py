"""
Minimal dependency-free SVG chart generation for the README stats section.

Mermaid renders simple charts but cannot draw a legend, a readable time axis, or
a pie, so the stats charts are emitted as small hand-built SVGs instead. Standard
library only, per the stats tooling's no-dependency rule.
"""
from typing import List, Tuple
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
Slice = Tuple[str, float, str]         # (label, value, color)


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


def _y(value: float, y_max: int) -> float:
    return M_TOP + PLOT_H * (1 - value / y_max)


def grouped_bar_chart(title: str, labels: List[str], series: List[Series], y_label: str = "") -> str:
    """A grouped (side-by-side) vertical bar chart with a legend, for comparing a
    few series across the same buckets (e.g. Wordle easy vs hard guess counts)."""
    all_values = [v for _, _, values in series for v in values]
    y_max = _nice_max(max(all_values) if all_values else 0)
    baseline = M_TOP + PLOT_H
    n = max(1, len(labels))
    k = max(1, len(series))
    slot = PLOT_W / n
    group_w = slot * 0.7
    bar_w = group_w / k

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{WIDTH / 2:.0f}" y="26" text-anchor="middle" font-size="16" font-weight="600" fill="#1a1a1a">{_escape(title)}</text>',
    ]

    for t in range(5):
        value = y_max * t / 4
        yy = _y(value, y_max)
        out.append(f'<line x1="{M_LEFT}" y1="{yy:.1f}" x2="{M_LEFT + PLOT_W}" y2="{yy:.1f}" stroke="#eaeaea"/>')
        out.append(f'<text x="{M_LEFT - 8}" y="{yy + 4:.1f}" text-anchor="end" fill="#888">{value:.0f}</text>')

    for i, label in enumerate(labels):
        group_x = M_LEFT + slot * i + (slot - group_w) / 2
        for j, (_, color, values) in enumerate(series):
            value = values[i]
            height = PLOT_H * value / y_max
            x = group_x + bar_w * j
            out.append(f'<rect x="{x:.1f}" y="{baseline - height:.1f}" width="{bar_w * 0.9:.1f}" height="{height:.1f}" rx="1.5" fill="{color}"/>')
        out.append(f'<text x="{M_LEFT + slot * i + slot / 2:.1f}" y="{baseline + 18:.1f}" text-anchor="middle" fill="#888">{_escape(label)}</text>')

    out.append(f'<line x1="{M_LEFT}" y1="{baseline}" x2="{M_LEFT + PLOT_W}" y2="{baseline}" stroke="#bbb"/>')
    out.append(f'<line x1="{M_LEFT}" y1="{M_TOP}" x2="{M_LEFT}" y2="{baseline}" stroke="#bbb"/>')
    if y_label:
        out.append(
            f'<text x="14" y="{M_TOP + PLOT_H / 2:.0f}" text-anchor="middle" fill="#888" '
            f'transform="rotate(-90 14 {M_TOP + PLOT_H / 2:.0f})">{_escape(y_label)}</text>'
        )

    lx, ly = M_LEFT + PLOT_W - 96, M_TOP + 8
    for j, (name, color, _) in enumerate(series):
        yy = ly + j * 18
        out.append(f'<rect x="{lx}" y="{yy - 9}" width="12" height="12" rx="2" fill="{color}"/>')
        out.append(f'<text x="{lx + 18}" y="{yy + 1}" fill="#333">{_escape(name)}</text>')

    out.append("</svg>")
    return "\n".join(out)


PIE_W = 560
PIE_H = 320
PIE_CX = 165
PIE_CY = 178
PIE_R = 118


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> Tuple[float, float]:
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def pie_chart(title: str, slices: List[Slice]) -> str:
    slices = [(label, value, color) for label, value, color in slices if value > 0]
    total = sum(value for _, value, _ in slices)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PIE_W}" height="{PIE_H}" '
        f'viewBox="0 0 {PIE_W} {PIE_H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">',
        f'<rect width="{PIE_W}" height="{PIE_H}" fill="#ffffff"/>',
        f'<text x="{PIE_W / 2:.0f}" y="26" text-anchor="middle" font-size="16" font-weight="600" fill="#1a1a1a">{_escape(title)}</text>',
    ]
    if total <= 0:
        return "\n".join(out + ["</svg>"])

    # a single non-empty bucket is a full circle (arc paths cannot draw 360 deg)
    if len(slices) == 1:
        label, value, color = slices[0]
        out.append(f'<circle cx="{PIE_CX}" cy="{PIE_CY}" r="{PIE_R}" fill="{color}"/>')
    else:
        angle = -90.0
        for _, value, color in slices:
            sweep = value / total * 360
            x1, y1 = _polar(PIE_CX, PIE_CY, PIE_R, angle)
            x2, y2 = _polar(PIE_CX, PIE_CY, PIE_R, angle + sweep)
            large = 1 if sweep > 180 else 0
            out.append(
                f'<path d="M {PIE_CX} {PIE_CY} L {x1:.1f} {y1:.1f} '
                f'A {PIE_R} {PIE_R} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}"/>'
            )
            angle += sweep

    legend_x, legend_y = 330, 96
    for k, (label, value, color) in enumerate(slices):
        yy = legend_y + k * 24
        pct = value / total * 100
        out.append(f'<rect x="{legend_x}" y="{yy - 11}" width="14" height="14" rx="2" fill="{color}"/>')
        out.append(f'<text x="{legend_x + 22}" y="{yy}" fill="#333">{_escape(label)}: {value:.0f} ({pct:.0f}%)</text>')

    out.append("</svg>")
    return "\n".join(out)
