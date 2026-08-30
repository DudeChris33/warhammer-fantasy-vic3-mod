# Warhammer Fantasy — Worldwide Country-Tag Registry

**Single source of truth for country-tag uniqueness across the whole mod.** Not loaded by the
Victoria 3 engine — a grep-able authority every tag-authoring task checks *before* adding a code.
Filed by epic #3414 (child #3415).

> **Assembled region-by-region with per-region approval (Chris).** Codes were allocated *globally* in
> a whole-world draft (see `planning/.cache/tag_registry.draft.md`); regions are appended here only
> once approved. Approved codes are frozen (append-only) — later regions add new unique codes, never
> rename a shipped one. The whole-world honest-canon draft totals 161 tags; this file grows to that as
> regions are approved.

### Regions approved (Phase B walk)

- [x] 00 Norsca (10)
- [x] 01 Kislev (10)
- [ ] 02 Empire
- [ ] 03 Bretonnia
- [ ] 04 Karaz Ankor
- [ ] 05 Southern Realms
- [ ] 06 Badlands
- [ ] 07 Nehekhara
- [ ] 10 Dark Lands
- [ ] 08 Araby
- [ ] 09 Southlands
- [ ] 11 Ogre Kingdoms
- [ ] 12 Eastern Steppes
- [ ] 13 Cathay
- [ ] 14 Ind
- [ ] 15 Khuresh
- [ ] 16 Nippon
- [ ] 17 Ulthuan
- [ ] 18 Naggaroth
- [ ] 19 Lustria

**Approved so far: 20 tags** (2 formables, 18 starts). Content is **honest, well-attested Warhammer
Fantasy Battle canon** — Total War video-game inventions excluded unless explicitly folded into
Warhammer: The Old World (2023+) and confirmed by Chris.

- **No vanilla collision possible:** this total conversion **empties vanilla
  `common/country_definitions/`** (827 base-game tags), so no base-game tag loads at runtime. This is
  load-bearing — several codes here coincide with real vanilla tags and would be redefinition
  collisions if vanilla defs still loaded. Only this registry's own uniqueness matters.
- **Machine-verified within this file:** every code is exactly 3 uppercase ASCII letters, all are
  unique (zero collisions), roster⇔index parity holds, and every Old-World primary culture referenced
  exists in `common/cultures/*.txt` (#3404).

## Conventions

- **3 uppercase ASCII letters**, mnemonic per polity (Vic3 vanilla convention: `GBR`, `FRA`).
- **Formable = the iconic national code; start fragments = polity codes.** `EMP` is the formable
  *The Empire*; `REI` (Reikland) etc. are the start tags that form it.
- **One row per tag**, columns: `TAG | region file | polity | kind (formable/start) | primary culture
  | placeholder capital | notes`.
- **Files mirror the culture epic** (#3404), same region numbers, stems matching the shipped culture
  filenames verbatim (including `03_brettonia`).
- **Old World rows** (00–07, 10) carry a real primary-culture id from `common/cultures/*.txt`. A
  deepened minor realm with no bespoke culture takes its region's dominant existing culture id (never
  invent, never `PLACEHOLDER` for Old World). **Distant rows** (08, 09, 11–19) carry the literal token
  `PLACEHOLDER` until a future epic authors those cultures.

## How to use

Before allocating a new tag, check whether the code is taken — **use an anchored grep, not a bare
substring search** (bare `grep EMP` also matches all-caps region headers like `### 02 EMPIRE`, and
`grep AND` false-positives on `BADLANDS`). Either grep the one-per-line index, or anchor to a row:

    grep -xE '<CODE>' planning/tag_registry.md        # against the one-code-per-line Code index
    grep -E '^\| <CODE> \|' planning/tag_registry.md  # against a roster row

A hit means the code is taken. When you add a tag, add its roster row **and** its index line, keeping
both sorted. Never reuse a shipped tag — tags are referenced by history, diplomacy, formables, events
and loc, and are painful to rename later.

## Code index (flat, ONE CODE PER LINE, sorted — the safe grep target; keep in sync with the roster)

```
AES
BAE
BJO
BOL
DOL
ERE
GRA
HAS
KIS
KSV
KVE
NSC
PRA
ROP
SAR
SKA
TRO
UNG
VAR
VOL
```

## Deferred check (owned by epic #3414)

Whether the engine **hard-requires exactly 3 chars** or merely tolerates longer tags. Strong evidence
it is 3: all 827 vanilla tags are exactly 3 characters. The roster is drafted at 3 chars regardless.
(Colors, `country_type`/`tier`, real `capital = <state>` ids are separate parked decisions on the
epic, not tag-uniqueness concerns.)

## Roster

### 00 NORSCA (norscan) — 10 tags; NSC formable

7 core High Tribes are solid canon; Hastlings + Kvelligs are medium-confidence High Tribes. Honest
ceiling ~10–12 (deeper Norse "tribes" are fan/homebrew). Seed's Skjaelings/Sortsvinar dropped
(unverified — Chris's call, approved 2026-08-30).

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| NSC | `00_norsca` | Norsca (united Norsii) | formable | `norscan` | — | unifier of the tribes |
| SAR | `00_norsca` | Sarls | start | `norscan` | Sortsvinar coast | Wolf of the Sea |
| AES | `00_norsca` | Aeslings | start | `norscan` | — | Slaanesh-leaning tribe |
| BAE | `00_norsca` | Baersonlings | start | `norscan` | — | reavers, on speaking terms w/ humanity |
| BJO | `00_norsca` | Bjornlings | start | `norscan` | — | traders/fishers/sailors |
| SKA | `00_norsca` | Skaelings | start | `norscan` | — | Khorne-leaning |
| GRA | `00_norsca` | Graelings | start | `norscan` | — | Tzeentch-leaning sea raiders |
| VAR | `00_norsca` | Varg | start | `norscan` | — | northern Chaos-touched tribe |
| HAS | `00_norsca` | Hastlings | start | `norscan` | — | High Tribe near the Chaos Wastes |
| KVE | `00_norsca` | Kvelligs | start | `norscan` | — | High Tribe near the Chaos Wastes |

### 01 KISLEV (gospodar, ungol) — 10 tags; KIS formable

3 cities + Ungol/Gospodar peoples are solid; Troll Country, Dolgan, Roppsmenn, Bolgasgrad, Volksgrad
are medium-confidence (wiki-aggregated). Density lever: many more RPG-sourcebook villages exist if
oblast depth is wanted. United Kislev (KIS) carries both founding cultures. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| KIS | `01_kislev` | Kislev (Tzardom) | formable | `gospodar`, `ungol` | — | United Kislev — both founding peoples |
| KSV | `01_kislev` | Kislev | start | `gospodar` | Kislev | the capital oblast, Tzarina's seat |
| ERE | `01_kislev` | Erengrad | start | `ungol` | Erengrad | western Ungol-leaning port |
| PRA | `01_kislev` | Praag | start | `gospodar` | Praag | northern frontier city |
| UNG | `01_kislev` | Ungol Horse-Tribes | start | `ungol` | — | nomadic steppe Ungols |
| TRO | `01_kislev` | Troll Country | start | `ungol` | — | far-NW frontier oblast |
| BOL | `01_kislev` | Bolgasgrad | start | `gospodar` | Bolgasgrad | northern oblast town |
| VOL | `01_kislev` | Volksgrad | start | `gospodar` | Volksgrad | oblast town |
| DOL | `01_kislev` | Dolgan | start | `ungol` | — | old eastern horse-tribe |
| ROP | `01_kislev` | Roppsmenn | start | `ungol` | — | old northern tribe |
