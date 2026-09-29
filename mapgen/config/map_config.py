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

``mapgen/`` holds offline tooling only and is never loaded by the game as content; it is
named ``mapgen`` (not ``tools``) so it cannot be mistaken for a game-reserved folder name.
"""

# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

#: Committed master seed. Every generator derives its RNG from this value.
#: Change only with intent: regeneration reproduces byte-identical output only
#: for a fixed seed (and a fixed toolchain — see mapgen/requirements.txt).
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
# heightmap.png encoding (16-bit grayscale)
# ---------------------------------------------------------------------------
#
# Vic3 stores terrain height as a raw uint16 with no scale declared anywhere in
# script, so the mapping from metres to stored value has to match vanilla's or
# the relief reads at the wrong vertical scale. Both constants below were
# *measured* from the shipped 1.13.8 ``game/map_data/heightmap.png`` by splitting
# its pixels on the real land/sea mask (provinces.png cross-referenced against
# default.map's sea_starts + lakes):
#
#   * land  p1=4738  p5=4886  median=5936  p95=16742  max=53469
#   * sea   median=0  p95=1246  p99=4162   (61.3% of the canvas is exactly 0)
#
# Land's 5th percentile (4886) and its modal shoreline value (4884) put sea level
# at 4884. Scaling at 5.5 units/m then places Everest (8848 m) at 53548 against
# vanilla's observed maximum of 53469 — i.e. vanilla is drawn to this exact
# scale, so we inherit it rather than invent one.
#
# Anything below the sea floor clamps to 0, which is why vanilla's deep ocean is
# a flat 0: -888 m already reaches the bottom of the range.

#: Stored uint16 value representing 0 m (the shoreline).
HEIGHT_SEA_LEVEL = 4884

#: Stored uint16 units per metre of real elevation.
HEIGHT_UNITS_PER_METRE = 5.5

#: Land pixels are forced to at least this far above :data:`HEIGHT_SEA_LEVEL`,
#: and sea pixels at least this far below, so the heightmap's shoreline can never
#: contradict the committed land/sea mask that provinces.png is built from.
HEIGHT_SHORE_MARGIN = 16

# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

#: Marker stamped on generated localization entries that still hold a
#: prettified placeholder name, pending the P6 canon-naming pass. The P6 tooling
#: finds outstanding entries by this marker.
AUTOGEN_MARKER = "# AUTOGEN"
