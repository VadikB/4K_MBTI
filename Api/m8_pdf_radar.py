"""Technical SVG geometry for the saved 0–3 Skill radar projection."""
from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape


def _point(index: int, value: float, count: int, radius: float = 102) -> tuple[float, float]:
    angle = -math.pi / 2 + index * 2 * math.pi / count
    return 130 + math.cos(angle) * radius * value / 3, 130 + math.sin(angle) * radius * value / 3


def _runs(values: list[float | None]) -> list[tuple[list[int], bool]]:
    if not values or all(value is None for value in values):
        return []
    if all(value is not None for value in values):
        return [(list(range(len(values))), True)]
    gap = values.index(None)
    runs: list[tuple[list[int], bool]] = []
    current: list[int] = []
    for step in range(1, len(values) + 1):
        index = (gap + step) % len(values)
        if values[index] is None:
            if current:
                runs.append((current, False)); current = []
        else:
            current.append(index)
    if current:
        runs.append((current, False))
    return runs


def _series(values: list[float | None], color: str, *, partial: list[bool] | None = None,
            previous: bool = False) -> list[str]:
    result = []
    for indexes, closed in _runs(values):
        points = [_point(index, values[index], len(values)) for index in indexes]
        if closed and len(points) > 2:
            points.append(points[0])
        coords = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
        if len(points) > 1 and sum(value is not None for value in values) >= 3:
            result.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3"' +
                          (' stroke-dasharray="5 4"' if previous or not closed else '') + '/>')
    for index, value in enumerate(values):
        if value is None:
            continue
        x, y = _point(index, value, len(values))
        dash = ' stroke-dasharray="2 2"' if partial and partial[index] else ''
        fill = 'white' if partial and partial[index] else color
        if previous:
            result.append(f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="{fill}" stroke="{color}" stroke-width="3"{dash}/>')
        else:
            result.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{fill}" stroke="{color}" stroke-width="3"{dash}/>')
    return result


def write_radars(radars: list[dict], directory: Path) -> None:
    for number, radar in enumerate(radars):
        axes = radar["axes"]
        for axis in axes:
            for key in ("current", "previous"):
                value = axis.get(key)
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 3):
                    raise ValueError("Radar values must be finite scores on the saved 0–3 scale")
        if not axes or not any(axis.get("current") is not None for axis in axes):
            continue
        count = len(axes)
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 260" width="260" height="260">',
                 '<rect width="260" height="260" fill="white"/>']
        for level in (1, 2, 3):
            if count < 3:
                parts.append(f'<circle cx="130" cy="130" r="{102 * level / 3:.1f}" fill="none" stroke="#ccd8dc" stroke-width="1"/>')
            else:
                points = ' '.join(f'{x:.1f},{y:.1f}' for x, y in (_point(i, level, count) for i in range(count)))
                parts.append(f'<polygon points="{points}" fill="none" stroke="#ccd8dc" stroke-width="1"/>')
        for i in range(count):
            x, y = _point(i, 3, count)
            parts.append(f'<line x1="130" y1="130" x2="{x:.1f}" y2="{y:.1f}" stroke="#ccd8dc"/>')
            lx, ly = _point(i, 3.35, count)
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="12" font-family="sans-serif" fill="#29363c">{escape(str(i + 1))}</text>')
        parts.append('<text x="134" y="126" font-size="10" fill="#526168">0</text>')
        parts += _series([axis.get("current") for axis in axes], "#18b8c6",
                         partial=[bool(axis.get("partial")) for axis in axes])
        if any(axis.get("previous") is not None for axis in axes):
            parts += _series([axis.get("previous") for axis in axes], "#64748b", previous=True,
                             partial=[bool(axis.get("previous_partial")) for axis in axes])
        parts.append('</svg>')
        (directory / f"radar-{number}.svg").write_text(''.join(parts), encoding="utf-8")
