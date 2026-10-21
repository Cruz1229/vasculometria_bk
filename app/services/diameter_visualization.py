from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
import numpy as np
from PIL import Image


def _point(value: Any, width: int, height: int) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        row, col = float(value[0]), float(value[1])
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if not np.isfinite(row) or not np.isfinite(col):
        return None
    if not (0 <= row < height and 0 <= col < width):
        return None
    return col, row


def save_diameter_image(
    image: Image.Image,
    measurements: Sequence[Mapping[str, Any]] | None,
    output_path: Path,
    *,
    segmentation_roi: np.ndarray,
    zones_ABC: np.ndarray,
) -> bool:
    if not measurements:
        return False
    width, height = image.size
    if np.shape(segmentation_roi) != (height, width):
        raise ValueError('segmentation_roi has incompatible dimensions')
    if np.shape(zones_ABC) != (height, width, 4):
        raise ValueError('zones_ABC has incompatible dimensions')

    combined = np.zeros((height, width, 4), dtype=np.float32)
    valid = []
    for item in measurements:
        plot = item.get('plot')
        if plot is None:
            continue
        data = np.asarray(plot)
        if data.shape != combined.shape:
            continue
        rgba = np.clip(np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0), 0, 1)
        if not np.any(rgba[..., 3] > 0):
            continue
        np.maximum(combined, rgba, out=combined)
        valid.append(item)
    if not valid:
        return False

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(width / 100, height / 100), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(image.convert('RGB'), interpolation='nearest')
    ax.imshow(segmentation_roi, alpha=0.3, interpolation='nearest')
    ax.imshow(np.clip(np.asarray(zones_ABC, dtype=np.float32) / 255, 0, 1),
              alpha=0.5, interpolation='nearest')
    ax.imshow(combined, interpolation='nearest')
    starts = [_point(m.get('start'), width, height) for m in valid]
    starts = [p for p in starts if p is not None]
    if starts:
        ax.scatter([p[0] for p in starts], [p[1] for p in starts],
                   s=25, c='white', edgecolors='none', zorder=5)
    for item in valid:
        end = _point(item.get('end'), width, height)
        if end is None:
            continue
        try:
            diameter = float(item['Median diameter'])
        except (ValueError, TypeError, KeyError):
            continue
        if not np.isfinite(diameter):
            continue
        ax.annotate(f'{diameter:.2f}', xy=end, xytext=(3, -3),
                    textcoords='offset points', fontsize=14, color='white',
                    ha='left', va='center', zorder=6)
    ax.set_xlim(-0.5, width - 0.5)
    ax.set_ylim(height - 0.5, -0.5)
    ax.set_axis_off()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        canvas.print_png(str(output_path))
    finally:
        fig.clear()
    return True
