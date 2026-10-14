#!/usr/bin/env python3
"""Source manifest — SHA-256 guard + registration cross-checks for ingestion.

``sources/`` is gitignored (~40 MB of binaries). Committed in
its place:

  * ``mapgen/SOURCES.md``                — this manifest: filename, dims, bytes,
                                           SHA-256, origin, role, and whether the
                                           source has a registration record.
  * ``mapgen/registration/*.json``       — how each *registered* source maps onto
                                           the canvas (validated by ``schema.py``).
  * ``mapgen/config/source_layers.json`` — the ref table mapping each hand-painted
                                           canvas input to a ``<file>.ora#<layer>``
                                           or bare flat-filename reference.

This module is the loader the ingestion stage (S2/S3) reads sources through. It
verifies a source's SHA-256 against the committed manifest **before** the bytes
are used, so a swapped or edited ``sources/`` file can never silently change a
committed bitmap. Refreshing after an intentional source change is the explicit
``--update-manifest`` action — never a side effect of reading.

The machine-readable manifest is the Markdown table between the
``<!-- MANIFEST:BEGIN -->`` / ``<!-- MANIFEST:END -->`` markers in
``mapgen/SOURCES.md``; prose outside the markers is preserved across updates.

An .ora (OpenRaster) file is a zip: ``mimetype``, ``data/NNN.png`` per layer,
``mergedimage.png``, a thumbnail, and ``stack.xml`` listing each layer's
``name``/``src``/``x``/``y``. Layers are read by their ``stack.xml`` name — the
extracted PNG filenames are just numbered, but the names survive the export.

Usage::

    python mapgen/worldgen/sources.py --verify           # default — the offline S1 gate
    python mapgen/worldgen/sources.py --update-manifest   # refresh dims/bytes/SHA in place
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Run either as a script or as `worldgen.sources` — put mapgen/ on the path so the
# `config` and `worldgen` packages import the same way the other tools do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import canvas_frame  # noqa: E402
from worldgen import derive_crop, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLS_DIR.parent
SOURCES_DIR = REPO_ROOT / "sources"
MANIFEST_PATH = TOOLS_DIR / "SOURCES.md"
REGISTRATION_DIR = TOOLS_DIR / "registration"
SOURCE_LAYERS_PATH = TOOLS_DIR / "config" / "source_layers.json"

#: The folders under ``sources/`` that tools search, alongside the root itself:
#: raw references (``originals/``), the current canvas-scale GIMP masters and
#: their per-.xcf .ora exports (``oldworld-first/``), the two paired-anchor-
#: dot batches still in active use (``dots-triangles/``, ``dots-mega/``) and
#: Ulthuan's paired-anchor-dot sheets (``ulthuan/``).
#: ``archive/`` (retired sources, including the five-crop dot-marking sheets —
#: board #5403), ``WIP/`` (local scratch, not manifest-tracked) and
#: ``cr_oldworld_campaign/`` (its own dataset loader) are deliberately excluded
#: from both search and refresh.
SOURCE_SUBDIRS = ("originals", "oldworld-first", "dots-triangles", "dots-mega", "ulthuan", "geology")

MANIFEST_BEGIN = "<!-- MANIFEST:BEGIN -->"
MANIFEST_END = "<!-- MANIFEST:END -->"

_COLUMNS = ("File", "Dims", "Bytes", "SHA-256", "Origin", "Role", "Registered")
#: Placeholder written for a machine cell that ``--update-manifest`` must fill.
_TBD = "TBD"
#: Dims cell for a non-image source (e.g. the .paint editable master).
_NA_DIMS = "n/a"


class ManifestError(RuntimeError):
    """A source failed to verify against the committed manifest."""


class OraError(ManifestError):
    """An .ora (OpenRaster) file or a requested layer inside it is malformed,
    missing, ambiguous, or empty."""


@dataclass(frozen=True)
class ManifestRow:
    file: str
    dims: str
    bytes: str
    sha256: str
    origin: str
    role: str
    registered: str  # "yes" | "no"

    @property
    def is_registered(self) -> bool:
        return self.registered.strip().lower() in ("yes", "y", "true")


# ---------------------------------------------------------------------------
# Local-file measurement (deterministic)
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_ref(ref: str) -> tuple[str, str | None]:
    """Split a source reference on the **last** ``#``, but only when the part
    before it ends in ``.ora`` (case-insensitive) — otherwise ``ref`` is a bare
    filename (which may itself legally contain a literal ``#``) and this
    returns ``(ref, None)`` unchanged."""
    if "#" in ref:
        file_part, _, layer_part = ref.rpartition("#")
        if file_part.lower().endswith(".ora"):
            return file_part, layer_part
    return ref, None


def resolve_source_path(name: str, sources_dir: Path = SOURCES_DIR) -> Path:
    """Find a manifest filename (or a ``<file>.ora#<layer>`` reference — only
    the file part is resolved) under ``sources_dir``, checking the root first
    and then each of :data:`SOURCE_SUBDIRS`. Returns ``sources_dir / name``
    (whether or not it exists) when no match is found, so callers get the same
    "expected here" path in their missing-file errors as before subfolders
    existed."""
    file, _ = split_ref(name)
    direct = sources_dir / file
    if direct.is_file():
        return direct
    for sub in SOURCE_SUBDIRS:
        candidate = sources_dir / sub / file
        if candidate.is_file():
            return candidate
    return direct


def image_dims(path: Path) -> str:
    """``"WxH"`` for an image Pillow can open, else :data:`_NA_DIMS`. For an
    ``.ora``, reads ``stack.xml``'s own ``w``/``h`` instead (Pillow can't open
    the zip directly as an image)."""
    if path.suffix.lower() == ".ora":
        try:
            w, h, _ = _parse_ora_stack(path)
            return f"{w}x{h}"
        except Exception:
            return _NA_DIMS
    try:
        from PIL import Image

        with Image.open(path) as im:
            return f"{im.size[0]}x{im.size[1]}"
    except Exception:
        return _NA_DIMS


# ---------------------------------------------------------------------------
# .ora (OpenRaster) layer reader
# ---------------------------------------------------------------------------

def _snap_alpha_to_binary(alpha) -> None:
    """Snap an alpha array **in place** to exactly 0 or 255 per pixel,
    rounding to whichever is closer (the midpoint 127/128 rounds up, matching
    a plain round-half-up). A source mask is meant to be hard-edged paint; a
    stray partial-opacity brush stroke (e.g. a 98% stroke, alpha ~250) would
    otherwise ship as a genuine partial-transparency value no downstream tool
    expects, and no coordinate is recorded anywhere else to spot it by eye."""
    alpha[alpha < 128] = 0
    alpha[alpha >= 128] = 255

def _parse_ora_stack(path: Path) -> tuple[int, int, list[ET.Element]]:
    """Return ``(w, h, layer_elements)`` for ``path``'s ``stack.xml``, in
    document order. Raises :class:`OraError` on anything malformed: a missing
    or wrong ``mimetype``, an unparsable ``stack.xml``, a non-``<image>``
    root, missing/invalid ``w``/``h``, not exactly one child ``<stack>``, or a
    nested ``<stack>`` (layer groups are unsupported)."""
    with zipfile.ZipFile(path) as zf:
        try:
            mimetype = zf.read("mimetype")
        except KeyError as exc:
            raise OraError(f"{path}: missing 'mimetype' entry — not a valid .ora") from exc
        if mimetype != b"image/openraster":
            raise OraError(f"{path}: mimetype is {mimetype!r}, expected b'image/openraster'")
        try:
            xml_bytes = zf.read("stack.xml")
        except KeyError as exc:
            raise OraError(f"{path}: missing 'stack.xml' entry — not a valid .ora") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise OraError(f"{path}: malformed stack.xml ({exc})") from exc

    if root.tag != "image":
        raise OraError(f"{path}: stack.xml root is <{root.tag}>, expected <image>")
    try:
        w = int(root.attrib["w"])
        h = int(root.attrib["h"])
    except (KeyError, ValueError) as exc:
        raise OraError(f"{path}: stack.xml <image> has a missing or invalid w/h") from exc
    if w <= 0 or h <= 0:
        raise OraError(f"{path}: stack.xml <image> w/h must be positive, got {w}x{h}")

    stacks = [c for c in root if c.tag == "stack"]
    if len(stacks) != 1:
        raise OraError(
            f"{path}: stack.xml <image> must have exactly one child <stack>, found {len(stacks)}"
        )

    layers: list[ET.Element] = []
    for child in stacks[0]:
        if child.tag == "stack":
            raise OraError(f"{path}: nested <stack> (layer groups) are unsupported")
        if child.tag == "layer":
            layers.append(child)

    return w, h, layers


def ora_layer_names(path: Path) -> list[str]:
    """The layer names in ``path``'s ``stack.xml``, in document order."""
    _, _, layers = _parse_ora_stack(path)
    names: list[str] = []
    for layer in layers:
        name = layer.attrib.get("name")
        if name is None:
            raise OraError(f"{path}: a <layer> is missing 'name'")
        names.append(name)
    return names


def read_ora_layer(path: Path, name: str, *, allow_empty: bool = False):
    """Return the layer named ``name`` in the .ora at ``path`` as an
    ``(H, W, 4)`` uint8 RGBA array at the image's full ``w``x``h`` canvas,
    composited at the layer's ``x``/``y`` offset (clipped at the canvas
    edges — handles negative offsets and overhanging layers), with alpha
    snapped to exactly 0 or 255 (see :func:`_snap_alpha_to_binary`) and RGB
    zeroed wherever alpha is 0. Hidden and edit-locked layers are readable;
    ``opacity``/``visibility``/``composite-op``/``edit-locked`` are ignored —
    this returns the raw painted pixels.

    Reads the zip directly; never extracts it.

    Raises :class:`OraError` on a missing/malformed archive, a requested name
    matching zero or more than one layer (zero lists the available names), a
    layer missing ``name``/``src`` or a ``src`` absent from the archive, or an
    all-transparent layer (unless ``allow_empty=True``)."""
    import numpy as np
    from PIL import Image

    w, h, layers = _parse_ora_stack(path)

    names: list[str] = []
    matches: list[ET.Element] = []
    for layer in layers:
        layer_name = layer.attrib.get("name")
        if layer_name is None:
            raise OraError(f"{path}: a <layer> is missing 'name'")
        names.append(layer_name)
        if layer_name == name:
            matches.append(layer)

    if not matches:
        raise OraError(f"{path}: no layer named '{name}' — available: {', '.join(names)}")
    if len(matches) > 1:
        raise OraError(
            f"{path}: layer name '{name}' matches {len(matches)} layers, expected exactly one"
        )

    layer = matches[0]
    src = layer.attrib.get("src")
    if not src:
        raise OraError(f"{path}: layer '{name}' is missing 'src'")
    try:
        x = int(layer.attrib.get("x", 0))
        y = int(layer.attrib.get("y", 0))
    except ValueError as exc:
        raise OraError(f"{path}: layer '{name}' has a non-integer x/y") from exc

    with zipfile.ZipFile(path) as zf:
        if src not in zf.namelist():
            raise OraError(f"{path}: layer '{name}' src '{src}' not found in the archive")
        with Image.open(io.BytesIO(zf.read(src))) as im:
            layer_img = np.asarray(im.convert("RGBA"), dtype=np.uint8)

    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    lh, lw = layer_img.shape[:2]
    dst_x0, dst_y0 = max(x, 0), max(y, 0)
    dst_x1, dst_y1 = min(x + lw, w), min(y + lh, h)
    if dst_x1 > dst_x0 and dst_y1 > dst_y0:
        src_x0, src_y0 = dst_x0 - x, dst_y0 - y
        src_x1, src_y1 = src_x0 + (dst_x1 - dst_x0), src_y0 + (dst_y1 - dst_y0)
        canvas[dst_y0:dst_y1, dst_x0:dst_x1] = layer_img[src_y0:src_y1, src_x0:src_x1]

    _snap_alpha_to_binary(canvas[..., 3])
    canvas[canvas[..., 3] == 0, :3] = 0

    if not allow_empty and not bool((canvas[..., 3] > 0).any()):
        raise OraError(f"layer '{name}' in {path} is empty — re-export")

    return canvas


# ---------------------------------------------------------------------------
# mapgen/config/source_layers.json — the one ref table every consumer reads
# ---------------------------------------------------------------------------

def load_source_layers(path: Path = SOURCE_LAYERS_PATH) -> dict[str, str]:
    """Parse the hand-authored ref table: a JSON object of non-empty string
    values, each a ``<file>.ora#<layer>`` reference (must carry ``#layer``) or
    a bare flat filename (must carry no ``#`` at all). Raises
    :class:`ManifestError` on anything else."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path.name}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path.name}: must be a JSON object of key -> ref strings")

    table: dict[str, str] = {}
    for key, ref in data.items():
        if not isinstance(ref, str) or not ref.strip():
            raise ManifestError(f"{path.name}: '{key}' must be a non-empty string")
        file, layer = split_ref(ref)
        is_ora = file.lower().endswith(".ora")
        if is_ora and layer is None:
            raise ManifestError(
                f"{path.name}: '{key}' ({ref!r}) is an .ora reference with no '#layer'"
            )
        if not is_ora and "#" in ref:
            raise ManifestError(
                f"{path.name}: '{key}' ({ref!r}) is not an .ora file but carries a '#'"
            )
        table[key] = ref
    return table


def source_ref(key: str, path: Path = SOURCE_LAYERS_PATH) -> str:
    """The configured source reference for ``key`` in ``source_layers.json``."""
    table = load_source_layers(path)
    if key not in table:
        raise ManifestError(
            f"'{key}' is not a key in {path.name} — known keys: {', '.join(sorted(table))}"
        )
    return table[key]


# ---------------------------------------------------------------------------
# Manifest parse / render (the table between the MANIFEST markers)
# ---------------------------------------------------------------------------

def _split_row(line: str) -> list[str]:
    # "| a | b |" -> ["a", "b"]; interior cells never contain a literal '|'.
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_manifest(md_text: str) -> list[ManifestRow]:
    if MANIFEST_BEGIN not in md_text or MANIFEST_END not in md_text:
        raise ManifestError(
            f"{MANIFEST_PATH.name}: missing {MANIFEST_BEGIN} / {MANIFEST_END} markers"
        )
    block = md_text.split(MANIFEST_BEGIN, 1)[1].split(MANIFEST_END, 1)[0]
    rows: list[ManifestRow] = []
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = _split_row(s)
        if not cells or cells[0] in ("File", "") or set(cells[0]) <= set("-: "):
            continue  # header or separator row
        if len(cells) != len(_COLUMNS):
            raise ManifestError(
                f"{MANIFEST_PATH.name}: manifest row has {len(cells)} cells, "
                f"expected {len(_COLUMNS)}: {s}"
            )
        rows.append(ManifestRow(*cells))
    if not rows:
        raise ManifestError(f"{MANIFEST_PATH.name}: manifest table is empty")
    return rows


def render_table(rows: list[ManifestRow]) -> str:
    header = "| " + " | ".join(_COLUMNS) + " |"
    sep = "|" + "|".join("---" for _ in _COLUMNS) + "|"
    lines = [header, sep]
    for r in sorted(rows, key=lambda r: r.file):
        lines.append(
            "| " + " | ".join(
                (r.file, r.dims, r.bytes, r.sha256, r.origin, r.role, r.registered)
            ) + " |"
        )
    return "\n".join(lines)


def _splice_manifest(md_text: str, table: str) -> str:
    head = md_text.split(MANIFEST_BEGIN, 1)[0]
    tail = md_text.split(MANIFEST_END, 1)[1]
    return f"{head}{MANIFEST_BEGIN}\n{table}\n{MANIFEST_END}{tail}"


# ---------------------------------------------------------------------------
# Verification (the SHA-256 guard + dimensioned registration cross-checks)
# ---------------------------------------------------------------------------

def verify(
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
    registration_dir: Path = REGISTRATION_DIR,
    source_layers_path: Path = SOURCE_LAYERS_PATH,
) -> list[str]:
    """Return a flat list of error strings (empty == clean)."""
    errors: list[str] = []

    rows = parse_manifest(manifest_path.read_text(encoding="utf-8"))
    by_file = {r.file: r for r in rows}

    # 1. Every manifest row's local file exists and matches its committed hash.
    for r in rows:
        path = resolve_source_path(r.file, sources_dir)
        if not path.is_file():
            errors.append(f"manifest lists '{r.file}' but sources/{r.file} is missing locally")
            continue
        actual = sha256_of(path)
        if actual != r.sha256:
            errors.append(
                f"{r.file}: SHA-256 mismatch — manifest {r.sha256[:12]}… local {actual[:12]}… "
                f"(run --update-manifest only if the change is intentional)"
            )
        if r.sha256 == _TBD:
            errors.append(f"{r.file}: SHA-256 still '{_TBD}' — run --update-manifest")
        expect_dims = image_dims(path)
        if r.dims not in (expect_dims, _NA_DIMS) and expect_dims != _NA_DIMS:
            errors.append(f"{r.file}: dims mismatch — manifest {r.dims} local {expect_dims}")

    # 2. Registration records: schema-valid, and every registered source is in
    #    the manifest (and vice versa).
    try:
        regs = schema.load_registrations(registration_dir)
    except schema.SchemaError as exc:
        errors.append(f"registration schema error: {exc}")
        regs = []
    reg_by_source = {r.source: r for r in regs}

    for reg in regs:
        if reg.source in by_file:
            continue
        seed = _derived_seed(reg.source)
        if seed is None:
            errors.append(f"registration '{reg.source}' has no row in {manifest_path.name}")
        elif seed["dots_source"] not in by_file:
            errors.append(
                f"registration '{reg.source}' derives from '{seed['dots_source']}' "
                f"which has no row in {manifest_path.name}"
            )

    # 2b. Frame aliases: the parent must be a real registration, and must not
    #     itself be an alias. Both are structural facts the per-file schema pass
    #     cannot see, and either one silently breaks the borrowed placement — an
    #     alias of a missing parent has no warp at all, and a chain of aliases
    #     would mean a control-point correction reaches some siblings and not
    #     others, which is precisely what the alias mechanism exists to prevent.
    for reg in regs:
        if not reg.is_alias:
            continue
        parent = reg_by_source.get(reg.frame_alias.of)
        if parent is None:
            errors.append(
                f"{reg.source}: frame_alias.of '{reg.frame_alias.of}' has no registration record"
            )
        elif parent.is_alias:
            errors.append(
                f"{reg.source}: frame_alias.of '{reg.frame_alias.of}' is itself an alias — "
                f"aliases must point at a source that carries real control points"
            )

    for r in rows:
        if r.is_registered and r.file not in reg_by_source:
            errors.append(f"manifest marks '{r.file}' Registered=yes but no registration record exists")
        if (not r.is_registered) and r.file in reg_by_source:
            errors.append(f"'{r.file}' has a registration record but manifest Registered={r.registered}")

    # 3. Dimensioned checks the structural schema cannot do (needs canvas + source
    #    dims): control points inside the source image, footprint inside the canvas.
    w_canvas, h_canvas = canvas_frame.WIDTH, canvas_frame.HEIGHT
    for reg in regs:
        seed = _derived_seed(reg.source)
        if seed is not None:
            mh, mw = seed["master_shape"]
            sw, sh = int(mw), int(mh)
        else:
            sw = sh = None
            path = resolve_source_path(reg.source, sources_dir)
            if path.is_file():
                dims = image_dims(path)
                if dims != _NA_DIMS:
                    sw, sh = (int(v) for v in dims.split("x"))

        x0, y0, x1, y1 = reg.footprint
        if not (0 <= x0 < x1 <= w_canvas and 0 <= y0 < y1 <= h_canvas):
            errors.append(f"{reg.source}: footprint {reg.footprint} is not within the canvas {w_canvas}x{h_canvas}")

        if reg.crop is not None and sw is not None:
            cx0, cy0, cx1, cy1 = reg.crop
            if not (0 <= cx0 < cx1 <= sw and 0 <= cy0 < cy1 <= sh):
                errors.append(f"{reg.source}: crop {reg.crop} is not within the source image {sw}x{sh}")

        for i, cp in enumerate(reg.control_points):
            sx, sy = cp.source
            if sw is not None and not (0 <= sx <= sw and 0 <= sy <= sh):
                errors.append(f"{reg.source}: control_points[{i}].source ({sx}, {sy}) outside the source {sw}x{sh}")
            cxx, cyy = cp.canvas
            if not (0 <= cxx <= w_canvas and 0 <= cyy <= h_canvas):
                errors.append(f"{reg.source}: control_points[{i}].canvas ({cxx}, {cyy}) outside the canvas {w_canvas}x{h_canvas}")

    # 4. Configured source refs (mapgen/config/source_layers.json): every entry's
    #    container file resolves, has a manifest row, and — for an .ora — names
    #    a layer that exists exactly once in stack.xml. Emptiness is not checked
    #    here; the consumer decides whether an empty layer is acceptable.
    try:
        table = load_source_layers(source_layers_path)
    except FileNotFoundError:
        # No ref table at this path — nothing configured to check (used by the
        # ingest/boundary fixture harnesses, which pass a deliberately absent
        # path since their synthetic sources_dir has no bearing on the real
        # committed mapgen/config/source_layers.json).
        table = {}
    except ManifestError as exc:
        errors.append(str(exc))
        table = {}
    for key, ref in table.items():
        file, layer = split_ref(ref)
        path = resolve_source_path(file, sources_dir)
        if not path.is_file():
            errors.append(f"{key}: {file} not found under sources/ or its searched subfolders")
            continue
        if file not in by_file:
            errors.append(f"{key}: {file} has no row in {manifest_path.name}")
            continue
        if layer is not None:
            try:
                names = ora_layer_names(path)
            except OraError as exc:
                errors.append(f"{key}: {exc}")
                continue
            count = names.count(layer)
            if count == 0:
                errors.append(f"{key}: layer '{layer}' not found in {file} — available: {', '.join(names)}")
            elif count > 1:
                errors.append(
                    f"{key}: layer '{layer}' matches {count} layers in {file}, expected exactly one"
                )

    return errors


# ---------------------------------------------------------------------------
# Verified image loader — the entry point the ingestion stage reads through
# ---------------------------------------------------------------------------

def _verified_path(ref: str, sources_dir: Path, manifest_path: Path) -> Path:
    """Resolve the container file of ``ref`` (a bare filename or a
    ``<file>.ora#<layer>`` reference) against ``manifest_path``, confirming
    its SHA-256. Raises :class:`ManifestError` on a missing row/file or a
    hash mismatch — never returns a path to unverified bytes."""
    file, _ = split_ref(ref)
    rows = {r.file: r for r in parse_manifest(manifest_path.read_text(encoding="utf-8"))}
    if file not in rows:
        raise ManifestError(f"'{file}' is not in {manifest_path.name}")
    path = resolve_source_path(file, sources_dir)
    if not path.is_file():
        raise ManifestError(f"sources/{file} is missing locally")
    actual = sha256_of(path)
    if actual != rows[file].sha256:
        raise ManifestError(
            f"{file}: SHA-256 mismatch (manifest {rows[file].sha256[:12]}… "
            f"local {actual[:12]}…) — refusing to read an unverified source"
        )
    return path


def load_source_image(
    ref: str,
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
):
    """Return the source as an ``(H, W, 3)`` uint8 RGB array, **after** confirming
    its container file's SHA-256 matches the committed manifest. ``ref`` is
    either a bare manifest filename or a ``<file>.ora#<layer>`` reference, in
    which case the named layer is composited and its RGB channels returned.
    Raises :class:`ManifestError` on a missing/altered file, or
    :class:`OraError` on a malformed/missing/ambiguous/empty layer — never
    returns unverified bytes."""
    import numpy as np
    from PIL import Image

    path = _verified_path(ref, sources_dir, manifest_path)
    _, layer = split_ref(ref)
    if layer is not None:
        return read_ora_layer(path, layer)[..., :3]
    if path.suffix.lower() == ".ora":
        raise OraError(f"{ref}: an .ora reference needs a '#layer' suffix")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def load_source_image_rgba(
    ref: str,
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
):
    """Like :func:`load_source_image`, but returns ``(rgb, alpha)``.

    ``rgb`` is an ``(H, W, 3)`` uint8 array exactly as :func:`load_source_image`
    would return. ``alpha``, when returned, is snapped to exactly 0 or 255 per
    pixel first (see :func:`_snap_alpha_to_binary` — a stray partial-opacity
    brush stroke must not ship as a genuine partial-transparency value), and is
    an ``(H, W)`` uint8 array **only** when the source carries a genuine
    transparency mask after snapping (some pixel below 255); it is ``None`` for
    a fully-opaque source or one with no alpha channel at all. This is the single
    authority for a crop's real footprint: the paired-anchor-dot region crops carry
    an intentional binary alpha mask (transparent = excluded regions), and
    ``.convert("RGB")`` silently drops it — so a boundary source that must honour
    that mask reads it here rather than inferring it from the lattice-bbox
    footprint, which includes the transparent corners.
    """
    import numpy as np
    from PIL import Image

    path = _verified_path(ref, sources_dir, manifest_path)
    _, layer = split_ref(ref)
    if layer is not None:
        rgba = read_ora_layer(path, layer)
        rgb, alpha = rgba[..., :3], rgba[..., 3]
        if int(alpha.min()) < 255:
            return rgb, alpha
        return rgb, None
    if path.suffix.lower() == ".ora":
        raise OraError(f"{ref}: an .ora reference needs a '#layer' suffix")
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
            alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3].copy()
            _snap_alpha_to_binary(alpha)
            if int(alpha.min()) < 255:
                return rgb, alpha
        return rgb, None


def read_source_rgba(
    ref: str,
    sources_dir: Path = SOURCES_DIR,
    *,
    allow_empty: bool = False,
):
    """Unverified loader for the dev renders and other reads that don't need
    (or can't afford) the manifest SHA-256 guard. Resolves ``ref`` (a bare
    flat filename or a ``<file>.ora#<layer>`` reference) under
    ``sources_dir``, returning ``None`` when the container file is absent and
    otherwise an ``(H, W, 4)`` uint8 RGBA array with alpha snapped to exactly 0
    or 255 (see :func:`_snap_alpha_to_binary`) and RGB zeroed under alpha 0 —
    for a layer ref and a flat file alike, since the tools detect exact paint
    colours and a fully-transparent pixel's stored RGB is meaningless."""
    import numpy as np
    from PIL import Image

    file, layer = split_ref(ref)
    path = resolve_source_path(file, sources_dir)
    if not path.is_file():
        return None
    if layer is not None:
        return read_ora_layer(path, layer, allow_empty=allow_empty)
    if path.suffix.lower() == ".ora":
        raise OraError(f"{ref}: an .ora reference needs a '#layer' suffix")
    with Image.open(path) as im:
        arr = np.array(im.convert("RGBA"), dtype=np.uint8)
    _snap_alpha_to_binary(arr[..., 3])
    arr[arr[..., 3] == 0, :3] = 0
    return arr


def _derived_seed(source: str) -> dict | None:
    """The parsed seed dict for `source` if its registration seed declares
    a dots_source (this source is derived on demand rather than
    manifest-tracked on its own), else None."""
    seed_path = REGISTRATION_DIR / "seeds" / f"{Path(source).stem}.json"
    if not seed_path.is_file():
        return None
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    return seed if "dots_source" in seed else None


def load_or_derive_image_rgba(
    filename: str,
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
):
    """Like :func:`load_source_image_rgba`, but derives on demand when the
    source's registration seed names a ``dots_source`` instead of reading
    ``filename`` as its own manifest-tracked file (board #3570)."""
    seed = _derived_seed(filename)
    if seed is not None:
        rgb, alpha = load_source_image_rgba(seed["dots_source"], sources_dir, manifest_path)
        return derive_crop.derive_clean_source(rgb, alpha, seed)
    return load_source_image_rgba(filename, sources_dir, manifest_path)


# ---------------------------------------------------------------------------
# Manifest refresh (the only sanctioned way the committed hashes change)
# ---------------------------------------------------------------------------

def update_manifest(
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
    registration_dir: Path = REGISTRATION_DIR,
) -> list[str]:
    """Recompute dims/bytes/SHA-256 for every file in ``sources/`` and rewrite the
    manifest table in place, preserving each row's hand-authored Origin/Role.
    Returns a list of human-readable notes about what changed / needs attention."""
    md_text = manifest_path.read_text(encoding="utf-8")
    existing = {r.file: r for r in parse_manifest(md_text)} if MANIFEST_BEGIN in md_text else {}

    # A malformed registration record must not silently flip every 'Registered'
    # cell to 'no'. Surface it loudly and leave the column untouched (carry each
    # row's prior value forward) so a bad hand-edit can't quietly rewrite the
    # manifest's registration state — refresh dims/bytes/SHA regardless.
    notes: list[str] = []
    reg_load_error: schema.SchemaError | None = None
    try:
        reg_sources = {r.source for r in schema.load_registrations(registration_dir)}
    except schema.SchemaError as exc:
        reg_sources = set()
        reg_load_error = exc
        notes.append(
            f"WARNING: registration records failed to load ({exc}); 'Registered' "
            f"column left unchanged — fix the record, then re-run --update-manifest"
        )

    discovered: dict[str, Path] = {}
    dupes: list[str] = []
    search_dirs = [sources_dir] + [sources_dir / sub for sub in SOURCE_SUBDIRS]
    for d in search_dirs:
        if not d.is_dir():
            continue
        for path in d.iterdir():
            if not path.is_file():
                continue
            if path.name in discovered:
                dupes.append(path.name)
                continue
            discovered[path.name] = path
    if dupes:
        raise ManifestError(
            "duplicate source filename(s) across sources/ and its subfolders — "
            f"rename one of each: {', '.join(sorted(set(dupes)))}"
        )

    rows: list[ManifestRow] = []
    for name in sorted(discovered):
        path = discovered[name]
        prev = existing.get(path.name)
        dims = image_dims(path)
        sha = sha256_of(path)
        size = f"{path.stat().st_size:,}"
        origin = prev.origin if prev and prev.origin != _TBD else _TBD
        role = prev.role if prev and prev.role != _TBD else _TBD
        if reg_load_error is not None:
            registered = prev.registered if prev else "no"
        else:
            registered = "yes" if path.name in reg_sources else "no"
        if prev is None:
            notes.append(f"NEW source '{path.name}' — fill in Origin/Role in SOURCES.md")
        elif prev.sha256 != sha and prev.sha256 != _TBD:
            notes.append(f"CHANGED '{path.name}': SHA {prev.sha256[:12]}… -> {sha[:12]}…")
        if origin == _TBD or role == _TBD:
            notes.append(f"'{path.name}': Origin/Role still {_TBD} — needs a human edit")
        rows.append(ManifestRow(path.name, dims, size, sha, origin, role, registered))

    manifest_path.write_text(_splice_manifest(md_text, render_table(rows)), encoding="utf-8")
    return notes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--verify", action="store_true", help="verify local sources against the manifest (default)")
    g.add_argument("--update-manifest", action="store_true", help="refresh dims/bytes/SHA-256 in place")
    args = p.parse_args(argv)

    if args.update_manifest:
        notes = update_manifest()
        print(f"manifest refreshed: {MANIFEST_PATH}")
        for n in notes:
            print(f"  - {n}")
        return 0

    errors = verify()
    if errors:
        print(f"sources: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("sources: manifest SHA-256 + registration cross-checks all passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
