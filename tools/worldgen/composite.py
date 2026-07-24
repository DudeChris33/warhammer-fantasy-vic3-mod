"""Precedence mosaic — merge overlapping registered sources onto one canvas.

There is no single high-resolution, already-rectangular whole-world reference
(see the request's Context), so the canvas is assembled from layers of differing
resolution and coverage. The rule, committed per source as ``precedence`` in its
registration record, is: **inside its own footprint the higher-precedence source
wins; the rest is filled by whatever is underneath.**

That gives a strict, auditable ordering — a hi-res regional map overrides the
whole-world layer where it has coverage, and nothing silently blends two sources
into a coastline that exists in neither. Ties are impossible: ``add`` rejects two
layers claiming the same precedence, because a tie would make the result depend
on insertion order, which is exactly the kind of ordering dependency the
determinism rules forbid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class CompositeError(RuntimeError):
    """Layers cannot be composited as declared."""


@dataclass
class Layer:
    """One registered source's contribution.

    ``data`` is a full-canvas array; ``valid`` marks where this layer actually
    has something to say (inside its footprint, inside its crop, and — for a
    partial source — wherever its own coverage test passed).
    """

    name: str
    precedence: int
    data: np.ndarray
    valid: np.ndarray

    def __post_init__(self) -> None:
        if self.data.shape[:2] != self.valid.shape[:2]:
            raise CompositeError(
                f"{self.name}: data {self.data.shape} and valid {self.valid.shape} disagree"
            )


class Mosaic:
    """Accumulates layers and resolves them by precedence."""

    def __init__(self, shape: tuple[int, int]) -> None:
        self.shape = shape
        self._layers: list[Layer] = []

    def add(self, layer: Layer) -> "Mosaic":
        if layer.data.shape[:2] != self.shape:
            raise CompositeError(
                f"{layer.name}: shape {layer.data.shape[:2]} != canvas {self.shape}"
            )
        for existing in self._layers:
            if existing.precedence == layer.precedence:
                raise CompositeError(
                    f"{layer.name} and {existing.name} both claim precedence "
                    f"{layer.precedence} — the winner would depend on insertion order"
                )
        self._layers.append(layer)
        return self

    @property
    def layers(self) -> list[Layer]:
        """Layers lowest-precedence first (i.e. painting order)."""
        return sorted(self._layers, key=lambda l: l.precedence)

    def resolve(self, base: np.ndarray | None = None):
        """Paint layers in ascending precedence. Returns ``(result, covered)``.

        ``covered`` is False wherever no layer claimed the pixel, so a caller can
        tell "this is genuinely ocean" apart from "nothing covered this".
        """
        if not self._layers:
            raise CompositeError("mosaic has no layers")
        first = self._layers[0].data
        out = (np.zeros(self.shape + first.shape[2:], dtype=first.dtype)
               if base is None else np.array(base, copy=True))
        covered = np.zeros(self.shape, dtype=bool)
        for layer in self.layers:
            sel = layer.valid
            if out.ndim > 2:
                np.copyto(out, layer.data, where=sel[..., None])
            else:
                np.copyto(out, layer.data, where=sel)
            covered |= sel
        return out, covered

    def coverage_report(self) -> list[str]:
        lines = []
        total = self.shape[0] * self.shape[1]
        claimed = np.zeros(self.shape, dtype=bool)
        # Walk highest-first so each line reports the area a layer actually wins,
        # not merely the area it offers.
        for layer in reversed(self.layers):
            wins = layer.valid & ~claimed
            claimed |= layer.valid
            lines.append(
                f"  precedence {layer.precedence:>3}  {layer.name:<32} "
                f"offers {100.0 * layer.valid.mean():6.2f}%  wins {100.0 * wins.sum() / total:6.2f}%"
            )
        lines.append(f"  uncovered: {100.0 * (~claimed).sum() / total:6.2f}%")
        return lines
