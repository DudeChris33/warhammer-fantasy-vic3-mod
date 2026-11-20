# Farmland lore dossiers (epic #3675)

Research for the per-state farmland rows of the arable epic, written 2026-11-19/20 by nine research
sub-agents of the `/maestro-run 3675` session, one per realm state file. **These are proposals with their
evidence, not accepted values.** Nothing here is read by a generator.

- `NN_<stem>.md` — one dossier per `map_data/state_regions/NN_<stem>.txt` as it stood on 2026-11-20
  (before the #10454 regen): the realm's canon farmland picture, the real-world analogue around 1800–1850,
  vanilla's analogue states, an entry per state, the proposed rows, disagreements with the climate layer
  and with the October drafts, open questions for Chris, and every page read.
- `all_rows.csv` — the 321 proposed rows of the nine dossiers in one table.

Row vocabulary: `lore_class` is one of #3676's eleven climate classes; `fertility_step` is −2..+2 against
typical land of that class (+1 = ×1.5, +2 = ×2.25, −1 = ×0.67, −2 = ×0.45); `tier` is A (canon text about
that place's land use), B (canon at province or realm level), R (real-world analogue only) or C (the
state's identity is itself inferred).

Citations: `fandom:<Title>` is the Fandom Warhammer Wiki (local dump in git-ignored `sources/wiki/`, or
read live), `lex:<Page>` is Lexicanum, each with the Games Workshop publication the wiki footnote names;
`rw:` is a real-world source; `vanilla:STATE_X` is the unmodded game's own state. Both wikis are fan
sources: the GW publication is the claim's real authority, and no primary book was opened.

Checked by the orchestrator: every state key has exactly one well-formed row with legal class and
building ids (key match for 02, 03 and 10 was checked before the last rows were added, format after),
and two to four load-bearing citations per dossier were re-read in the dump, on live Fandom or on
Lexicanum; all held. Each dossier lists the claims that rest on one wiki only.

The state files do not match the realm names: `01_kislev` holds thirteen northern Empire states,
`02_empire` two Bretonnian states and a dwarf pass, `03_brettonia` Athel Loren and Albion, `04_karaz_ankor`
the Lahmia coast and Nagashizzar, `06_badlands` the Border Princes.
