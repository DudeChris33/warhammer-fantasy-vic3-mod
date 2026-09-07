"""Stable province colour + id assignment across map regens (board #3705).

A province's identity in Victoria 3 **is** its ``provinces.png`` hex colour
(``xRRGGBB``) — there is no ``definition.csv``; ``state_regions/*.txt``,
``adjacencies.csv`` and every hub key reference that colour. The committed
``map_data/provinces.png`` + ``tools/derived/provinces_index.json`` already ARE
the persisted colour ↔ id ↔ geometry authority. This module makes a regenerated
province cut **honour** them, so a regen that touches only a few provinces leaves
the colour (and the tooling id) of every province whose *geometry* is unchanged
identical — instead of the old scheme, where colour was bound to flood-fill /
cut **order** (``id == label``) and adding/removing/reshaping any one province
reshuffled the colour → geometry mapping of every province after it in raster
order (silently breaking ``adjacencies.csv`` straits and any external colour
reference).

Design A1 (see board #3705). :func:`assign` overlap-matches each new geometry
label to the committed province of the **same kind** it most overlaps:

- **Matched** (best-overlap, greedy-bijective) new label → the committed colour
  and committed id. An unchanged province overlaps its committed twin 100%, so it
  matches trivially and keeps both.
- **Unmatched** new label (genuinely new geometry) → a **fresh colour** allocated
  with *all* committed colours reserved (so it can never collide with a retained
  or a just-retired colour) + a **fresh id** from a global monotonic high-water.
- **Retired** committed colour (no new label matched it — e.g. a dropped speck)
  simply does not appear in the new index; its colour/id are gap-tolerantly
  retired and never reused this run.

The match is applied uniformly to **land, sea and lake** — this is what kills the
sea/lake-colour ripple: the old single ``ColorAllocator`` walked land→sea→lake in
one sequence, so a change to the land count shifted every sea and lake colour;
matching sea↔sea and lake↔lake keeps a byte-identical water province its committed
colour regardless of the new land count (stabilising the colour-keyed
``99_seas.txt``, ``default.map`` ``sea_starts``/``lakes`` and
``province_terrains.txt``).

**Bootstrap / reassign.** With no committed bitmap (the very first generation and
every fixture), or with ``reassign=True``, :func:`assign` allocates fresh in
label order exactly as the pre-#3705 generator did (colour by label ordinal,
``id == label``) — a deliberate escape hatch to re-allocate colours on purpose
after a wholesale source overhaul.

Pure and deterministic: :func:`assign` is a function of ``(labels,
kind_of_label, committed bitmap, committed index cells, seed)`` with no RNG and a
fully-specified greedy order (overlap desc, then new label asc, then committed id
asc) and fresh colours issued strictly in ascending-new-label order — no dict /
set iteration leaks into a colour choice, so two dev machines produce
byte-identical output. Reading the committed ``provinces.png`` as a generator
*input* does not threaten multiplayer sync (which is about the committed *output*
being identical across clients, not the dev-side generation process).
"""
from __future__ import annotations

import numpy as np

from . import raster


def pack_rgb(rgb: np.ndarray) -> np.ndarray:
    """``(H, W, 3)`` uint8 → ``(H, W)`` int64 24-bit colour keys."""
    return ((rgb[..., 0].astype(np.int64) << 16)
            | (rgb[..., 1].astype(np.int64) << 8)
            | rgb[..., 2].astype(np.int64))


def _pack_color(color) -> int:
    r, g, b = color
    return (int(r) << 16) | (int(g) << 8) | int(b)


def assign(
    labels: np.ndarray,
    kind_of_label,
    committed_rgb: np.ndarray | None,
    committed_cells: list[dict] | None,
    seed: int,
    *,
    reassign: bool = False,
    committed_high_water: int | None = None,
):
    """Assign a stable ``(palette, ids, high_water)`` for a geometry label layer.

    ``labels``: the assembled ``(H, W)`` label layer, ``1..total`` (0 = the
    ``(0, 0, 0)`` border sentinel), land band first, then sea, then lake — exactly
    the layer the generator already builds.

    ``kind_of_label``: a sequence indexable by label giving each label's kind
    (``"land"`` / ``"sea"`` / ``"lake"``); index 0 is unused.

    ``committed_rgb`` / ``committed_cells``: the committed ``provinces.png`` as an
    ``(H, W, 3)`` uint8 array and the committed index ``cells`` (each with
    ``color`` / ``id`` / ``kind``). Both ``None`` (or ``reassign=True``) selects
    the fresh label-order branch. When present they MUST share ``labels``' canvas
    dimensions — the caller guards that.

    ``committed_high_water``: the committed index's ``id_high_water`` if it carries
    one (older indices do not). Fresh ids start above both this and every committed
    id, so a retired id is never resurrected across runs.

    Returns ``palette`` (``(total + 1, 3)`` uint8, row 0 the sentinel), ``ids``
    (``(total + 1,)`` int64, index 0 the sentinel 0) and ``high_water`` (the next
    unused id — the value to persist as the index's ``id_high_water``).
    """
    total = int(labels.max())
    palette = np.zeros((total + 1, 3), dtype=np.uint8)   # row 0 = (0,0,0) sentinel
    ids = np.zeros(total + 1, dtype=np.int64)            # index 0 = 0 sentinel

    # --- Bootstrap / reassign: fresh allocation in label order (pre-#3705) ---
    if reassign or committed_rgb is None or committed_cells is None:
        alloc = raster.ColorAllocator(seed)
        for lab in range(1, total + 1):
            palette[lab] = alloc.allocate()
            ids[lab] = lab
        return palette, ids, total + 1

    # --- The committed authority: colour → (compact cell index) → (id, kind) ---
    committed_colors: list[tuple] = []
    committed_id_of_cell: list[int] = []
    committed_kind_of_cell: list[str] = []
    key_to_cell: dict[int, int] = {}
    for cell in committed_cells:
        color = tuple(int(v) for v in cell["color"])
        k = _pack_color(color)
        if k in key_to_cell:
            # The committed index is already checked colour-unique by the validator;
            # guard anyway so a malformed input fails loudly, not silently.
            raise ValueError(f"committed index colour {raster.color_to_hex(color)} is not unique")
        key_to_cell[k] = len(committed_colors)
        committed_colors.append(color)
        committed_id_of_cell.append(int(cell["id"]))
        committed_kind_of_cell.append(str(cell["kind"]))
    n_committed = len(committed_colors)

    # --- Overlap tally: (new_label, committed_cell) → pixel count, one pass ---
    new_flat = labels.ravel().astype(np.int64)
    com_flat = pack_rgb(committed_rgb).ravel()
    uniq, inv = np.unique(com_flat, return_inverse=True)
    lut = np.array([key_to_cell.get(int(k), -1) for k in uniq.tolist()], dtype=np.int64)
    cidx_flat = lut[inv]                                  # committed cell index, or -1
    valid = (new_flat > 0) & (cidx_flat >= 0)
    # Encode each co-occurring (label, cell) pair as one integer and count them.
    combined = new_flat[valid] * n_committed + cidx_flat[valid]
    ucomb, counts = np.unique(combined, return_counts=True)
    lab_arr = (ucomb // n_committed).tolist()
    cell_arr = (ucomb % n_committed).tolist()

    # Candidate matches, same-kind only: (overlap, new_label, committed_id, cell).
    candidates: list[tuple[int, int, int, int]] = []
    for lab, ci, cnt in zip(lab_arr, cell_arr, counts.tolist()):
        if kind_of_label[lab] == committed_kind_of_cell[ci]:
            candidates.append((cnt, lab, committed_id_of_cell[ci], ci))
    # Greedy bijective assignment: overlap desc, then a fully-specified tie order
    # (new label asc, committed id asc) — a strict total order, no set/dict leak.
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    label_to_cell: dict[int, int] = {}
    cell_taken = [False] * n_committed
    for _cnt, lab, _cid, ci in candidates:
        if lab in label_to_cell or cell_taken[ci]:
            continue
        label_to_cell[lab] = ci
        cell_taken[ci] = True

    # --- Emit: matched keep committed colour+id; the rest get fresh, reserved ---
    alloc = raster.ColorAllocator(seed, reserved=set(committed_colors))
    next_id = max(committed_id_of_cell) + 1 if committed_id_of_cell else 1
    if committed_high_water is not None:
        next_id = max(next_id, int(committed_high_water))
    for lab in range(1, total + 1):
        ci = label_to_cell.get(lab)
        if ci is not None:
            palette[lab] = committed_colors[ci]
            ids[lab] = committed_id_of_cell[ci]
        else:
            palette[lab] = alloc.allocate()
            ids[lab] = next_id
            next_id += 1
    return palette, ids, next_id
