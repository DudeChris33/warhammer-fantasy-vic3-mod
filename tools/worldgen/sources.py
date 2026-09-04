#!/usr/bin/env python3
"""Source manifest — SHA-256 guard + registration cross-checks for ingestion.

``sources/`` is gitignored (third-party IP + ~40 MB of binaries). Committed in
its place:

  * ``tools/SOURCES.md``          — this manifest: filename, dims, bytes, SHA-256,
                                     origin, role, and whether the source has a
                                     registration record.
  * ``tools/registration/*.json`` — how each *registered* source maps onto the
                                     canvas (validated by ``schema.py``).

This module is the loader the ingestion stage (S2/S3) reads sources through. It
verifies a source's SHA-256 against the committed manifest **before** the bytes
are used, so a swapped or edited ``sources/`` file can never silently change a
committed bitmap. Refreshing after an intentional source change is the explicit
``--update-manifest`` action — never a side effect of reading.

The machine-readable manifest is the Markdown table between the
``<!-- MANIFEST:BEGIN -->`` / ``<!-- MANIFEST:END -->`` markers in
``tools/SOURCES.md``; prose outside the markers is preserved across updates.

Usage::

    python tools/worldgen/sources.py --verify           # default — the offline S1 gate
    python tools/worldgen/sources.py --update-manifest   # refresh dims/bytes/SHA in place
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

# Run either as a script or as `worldgen.sources` — put tools/ on the path so the
# `config` and `worldgen` packages import the same way the other tools do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import canvas_frame  # noqa: E402
from worldgen import schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLS_DIR.parent
SOURCES_DIR = REPO_ROOT / "sources"
MANIFEST_PATH = TOOLS_DIR / "SOURCES.md"
REGISTRATION_DIR = TOOLS_DIR / "registration"

#: ``sources/`` is organized into subfolders by role (raw references in
#: ``originals/``, GIMP editable masters in ``gimp/``, GIMP-exported PNGs in
#: ``gimp_exports/``, the paired-anchor-dot workflow's crops/examples in
#: ``dots/``) — a file may live directly under ``sources/`` or in one of
#: these. ``WIP/`` holds local scratch not tracked in the manifest, so it is
#: deliberately excluded from both search and refresh.
SOURCE_SUBDIRS = ("originals", "gimp", "gimp_exports", "dots")

MANIFEST_BEGIN = "<!-- MANIFEST:BEGIN -->"
MANIFEST_END = "<!-- MANIFEST:END -->"

_COLUMNS = ("File", "Dims", "Bytes", "SHA-256", "Origin", "Role", "Registered")
#: Placeholder written for a machine cell that ``--update-manifest`` must fill.
_TBD = "TBD"
#: Dims cell for a non-image source (e.g. the .paint editable master).
_NA_DIMS = "n/a"


class ManifestError(RuntimeError):
    """A source failed to verify against the committed manifest."""


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


def resolve_source_path(name: str, sources_dir: Path = SOURCES_DIR) -> Path:
    """Find a manifest filename under ``sources_dir``, checking the root first
    and then each of :data:`SOURCE_SUBDIRS`. Returns ``sources_dir / name``
    (whether or not it exists) when no match is found, so callers get the same
    "expected here" path in their missing-file errors as before subfolders
    existed."""
    direct = sources_dir / name
    if direct.is_file():
        return direct
    for sub in SOURCE_SUBDIRS:
        candidate = sources_dir / sub / name
        if candidate.is_file():
            return candidate
    return direct


def image_dims(path: Path) -> str:
    """``"WxH"`` for an image Pillow can open, else :data:`_NA_DIMS`."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return f"{im.size[0]}x{im.size[1]}"
    except Exception:
        return _NA_DIMS


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
        if reg.source not in by_file:
            errors.append(f"registration '{reg.source}' has no row in {manifest_path.name}")

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
        path = resolve_source_path(reg.source, sources_dir)
        sw = sh = None
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

    return errors


# ---------------------------------------------------------------------------
# Verified image loader — the entry point the ingestion stage reads through
# ---------------------------------------------------------------------------

def load_source_image(
    filename: str,
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
):
    """Return the source as an ``(H, W, 3)`` uint8 RGB array, **after** confirming
    its SHA-256 matches the committed manifest. Raises :class:`ManifestError` on a
    missing/altered file — never returns unverified bytes."""
    import numpy as np
    from PIL import Image

    rows = {r.file: r for r in parse_manifest(manifest_path.read_text(encoding="utf-8"))}
    if filename not in rows:
        raise ManifestError(f"'{filename}' is not in {manifest_path.name}")
    path = resolve_source_path(filename, sources_dir)
    if not path.is_file():
        raise ManifestError(f"sources/{filename} is missing locally")
    actual = sha256_of(path)
    if actual != rows[filename].sha256:
        raise ManifestError(
            f"{filename}: SHA-256 mismatch (manifest {rows[filename].sha256[:12]}… "
            f"local {actual[:12]}…) — refusing to read an unverified source"
        )
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def load_source_image_rgba(
    filename: str,
    sources_dir: Path = SOURCES_DIR,
    manifest_path: Path = MANIFEST_PATH,
):
    """Return ``(rgb, alpha)`` for a source, after the same SHA-256 guard as
    :func:`load_source_image`.

    ``rgb`` is an ``(H, W, 3)`` uint8 array exactly as :func:`load_source_image`
    would return. ``alpha`` is an ``(H, W)`` uint8 array **only** when the source
    carries a genuine transparency mask (some pixel below 255); it is ``None`` for
    a fully-opaque source or one with no alpha channel at all. This is the single
    authority for a crop's real footprint: the paired-anchor-dot region crops carry
    an intentional binary alpha mask (transparent = excluded regions), and
    ``.convert("RGB")`` silently drops it — so a boundary source that must honour
    that mask reads it here rather than inferring it from the lattice-bbox
    footprint, which includes the transparent corners.
    """
    import numpy as np
    from PIL import Image

    rows = {r.file: r for r in parse_manifest(manifest_path.read_text(encoding="utf-8"))}
    if filename not in rows:
        raise ManifestError(f"'{filename}' is not in {manifest_path.name}")
    path = resolve_source_path(filename, sources_dir)
    if not path.is_file():
        raise ManifestError(f"sources/{filename} is missing locally")
    actual = sha256_of(path)
    if actual != rows[filename].sha256:
        raise ManifestError(
            f"{filename}: SHA-256 mismatch (manifest {rows[filename].sha256[:12]}… "
            f"local {actual[:12]}…) — refusing to read an unverified source"
        )
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
            alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
            if int(alpha.min()) < 255:
                return rgb, alpha
        return rgb, None


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
