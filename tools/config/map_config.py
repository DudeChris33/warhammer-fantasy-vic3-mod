"""Single source of the determinism knobs shared by every map generator.

This mod is ``multiplayer_synchronized: true`` (``.metadata/metadata.json``), so
every generated artifact must be byte-identical on every client. The map layer
is static data, which is MP-safe by construction, but *regeneration* must also
reproduce byte-identical output — otherwise a regenerated file could silently
diverge from the committed one and desync clients that regenerated locally.

Determinism rules baked into the toolchain (see ``.claude/rules/core.md``):

* Every generator seeds its RNG from :data:`SEED` and nothing else — never
  wall-clock, ``os.urandom``, PID, filesystem entropy, or any OS state.
* Iterate over **sorted** collections, never dict/set iteration order.
* Output is a pure function of the committed input geometry plus :data:`SEED`.

Nothing in ``tools/`` is read by Victoria 3; the shipped folders stay clean.
"""

# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

#: Committed master seed. Every generator derives its RNG from this value.
#: Change only with intent: regeneration reproduces byte-identical output only
#: for a fixed seed (and a fixed toolchain — see tools/requirements.txt).
SEED = 20260720

# ---------------------------------------------------------------------------
# Canvas dimensions (width, height), identical to vanilla and Exether
# ---------------------------------------------------------------------------

#: provinces.png canvas. RGB, one unique colour per province, pixel-exact.
PROVINCES_SIZE = (8192, 3616)

#: heightmap.png source canvas. 16-bit grayscale (packed by the map editor).
HEIGHTMAP_SIZE = (16384, 7232)

# ---------------------------------------------------------------------------
# State-region id bands
# ---------------------------------------------------------------------------

#: Land state regions count up from here.
LAND_ID_START = 1

#: Single-province sea zones use ids from here (vanilla reserves the 3000+ band).
SEA_ID_START = 3000

# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

#: The world wraps on the x axis (sailing west from Lustria reaches Cathay).
#: Every distance/adjacency computation in the toolchain is wrap-aware when set.
WRAP_X = True

# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

#: Marker stamped on generated localization entries that still hold a
#: prettified placeholder name, pending the P6 canon-naming pass. The P6 tooling
#: finds outstanding entries by this marker.
AUTOGEN_MARKER = "# AUTOGEN"
