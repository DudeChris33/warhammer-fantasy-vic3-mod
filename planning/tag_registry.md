# Warhammer Fantasy — Worldwide Country-Tag Registry

**Single source of truth for country-tag uniqueness across the whole mod.** Not loaded by the
Victoria 3 engine — a grep-able authority every tag-authoring task checks *before* adding a code.
Filed by epic #3414 (child #3415).

> **Assembled region-by-region with per-region approval (Chris).** Codes were allocated *globally* in
> a whole-world draft (see `planning/.cache/tag_registry.draft.md`); regions are appended here only
> once approved. Approved codes are frozen (append-only) — later regions add new unique codes, never
> rename a shipped one. The honest-canon draft opened at 161; the final roster is **193 tags** — the
> Old World stayed at honest tabletop depth, while several distant regions (Badlands, Ogres, Cathay,
> Lustria) were expanded using Total War: Warhammer as an approved name source, and Ind/Khuresh/Nippon
> were deferred as too canon-thin to fill without inventing.

### Regions approved (Phase B walk)

- [x] 00 Norsca (9)
- [x] 01 Kislev (10)
- [x] 02 Empire (18)
- [x] 03 Bretonnia (17)
- [x] 04 Karaz Ankor (18)
- [x] 05 Southern Realms (14)
- [x] 06 Badlands (11)
- [x] 07 Nehekhara (11)
- [x] 10 Dark Lands (6)
- [x] 08 Araby (10)
- [x] 09 Southlands (8)
- [x] 11 Ogre Kingdoms (12)
- [x] 12 Eastern Steppes (4)
- [x] 13 Cathay (11)
- [~] 14 Ind — **DEFERRED** (0 tags; no canon supply in tabletop or Total War — Chris, 2026-08-30)
- [~] 15 Khuresh — **DEFERRED** (0 tags; near-zero canon, no Total War faction — Chris, 2026-08-30)
- [~] 16 Nippon — **DEFERRED** (0 tags; only medium-confidence secondary-source names, no Total War faction — Chris, 2026-08-30)
- [x] 17 Ulthuan (11)
- [x] 18 Naggaroth (7)
- [x] 19 Lustria (18)

**Total: 195 tags** (15 formables, 180 starts) — all 20 regions resolved (17 with tags; Ind, Khuresh,
Nippon deferred with 0). Content is **honest, well-attested Warhammer
Fantasy Battle canon** — Total War video-game inventions excluded unless explicitly folded into
Warhammer: The Old World (2023+) and confirmed by Chris.

- **No vanilla collision possible:** this total conversion **empties vanilla
  `common/country_definitions/`** (827 base-game tags), so no base-game tag loads at runtime. This is
  load-bearing — several codes here coincide with real vanilla tags and would be redefinition
  collisions if vanilla defs still loaded. Only this registry's own uniqueness matters.
- **Machine-verified within this file:** every code is exactly 3 uppercase ASCII letters, all are
  unique (zero collisions), roster⇔index parity holds, and every Old-World primary culture referenced
  exists in `common/cultures/*.txt` (#3404) — including `marienburger` and `sylvanian_vampire`,
  authored under the culture epic #3404 (the culture originally drafted as bare `vampire` was renamed
  to `sylvanian_vampire` to leave room for other future Old World vampire bloodlines).
- **Forward-referenced cultures pending authoring in epic #3404** (design decisions approved by Chris
  2026-08-30; culture *files* authored in the culture epic, so these ids are intentionally not yet live
  and are excluded from the culture-exists check):
  - `sartosan` — a melting-pot Tilean-pirate culture for Sartosa (modeled on vanilla's Maltese).
  - `lahmian_vampire` — the Lahmian vampire bloodline (Neferata's) for the tomb-city of Lahmia.
  - `savage_orc` — the Savage Orc subculture (Southlands heartland); see region 09.

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
AGF
AHK
ANT
AQU
ARB
ART
AVE
AVL
AXL
AZL
BAE
BAS
BCB
BEL
BGZ
BHA
BHZ
BIL
BJO
BKA
BLV
BNR
BOL
BOR
BPR
BRE
BRI
BRK
BRN
BSB
BTO
BVR
CAL
CAR
CHQ
CHR
CHU
CLK
CNT
COP
COT
COU
CRM
CTH
CXC
DGF
DOL
DRZ
EKR
ELK
ELL
EMP
ERE
EST
EYB
FSM
FUC
FUH
FYR
GBS
GGT
GHR
GIS
GLG
GOR
GRA
GUN
HAR
HAS
HEX
HGF
HGK
HHZ
HOC
HUA
HUN
ICL
IRN
ITZ
KAD
KAG
KAK
KAS
KAZ
KEP
KHI
KHM
KHN
KIS
KKR
KNO
KON
KRD
KSV
KUL
KUN
KUR
KVE
KVN
LAH
LAN
LOT
LSK
LUC
LUS
LYB
LYO
MAG
MAH
MAW
MID
MIR
MKY
MNF
MOO
MOR
MOU
MTK
MZN
NAG
NEH
NGA
NGD
NGY
NLD
NUM
ORG
OSM
OST
OYX
PAH
PAR
PAV
PRA
QTZ
QUA
QUE
RAS
RDV
RED
REI
REM
RFG
ROP
RSK
SAP
SAR
SHW
SHY
SKA
SKT
SKZ
SLV
SNK
SOL
SOM
SPZ
SRT
STI
SYL
TAL
THG
TIL
TIR
TLA
TLN
TLX
TOB
TON
TPK
TRA
TRO
ULT
UNG
UZK
VAR
VEM
VER
VLG
VOL
VSY
WAS
WEI
WIS
WSK
WWG
XAH
XHO
XLA
YVR
ZHA
ZHU
ZLA
ZND
```

## Deferred check (owned by epic #3414)

Whether the engine **hard-requires exactly 3 chars** or merely tolerates longer tags. Strong evidence
it is 3: all 827 vanilla tags are exactly 3 characters. The roster is drafted at 3 chars regardless.
(Colors, `country_type`/`tier`, real `capital = <state>` ids are separate parked decisions on the
epic, not tag-uniqueness concerns.)

## Roster

### 00 NORSCA (norscan) — 9 tags; no formable

7 core High Tribes are solid canon; Hastlings + Kvelligs are medium-confidence High Tribes. Honest
ceiling ~10–12 (deeper Norse "tribes" are fan/homebrew). Seed's Skjaelings/Sortsvinar dropped
(unverified — Chris's call, approved 2026-08-30). NSC unifier tag dropped on manual audit — the
High Tribes keep their own identity even after mass conquest; a unification journal entry may
represent this later instead of a formable country. All nine tribes are `grand_principality` tier,
`unrecognized` type (raiding tribes under a jarl, not part of any order the civilised south
recognises); a future country type may be added to represent tribal societies more precisely.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
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
| ERE | `01_kislev` | Erengrad | start | `gospodar`, `ungol` | Erengrad | western port city, gospodar-founded amid Ungol lands |
| PRA | `01_kislev` | Praag | start | `gospodar` | Praag | northern frontier city |
| UNG | `01_kislev` | Ungol Horse-Tribes | start | `ungol` | — | nomadic steppe Ungols |
| TRO | `01_kislev` | Troll Country | start | `ungol` | — | far-NW frontier oblast |
| BOL | `01_kislev` | Bolgasgrad | start | `gospodar` | Bolgasgrad | northern oblast town |
| VOL | `01_kislev` | Volksgrad | start | `gospodar` | Volksgrad | oblast town |
| DOL | `01_kislev` | Dolgan | start | `ungol` | — | old eastern horse-tribe |
| ROP | `01_kislev` | Roppsmenn | start | `ungol` | — | old northern tribe |

### 02 EMPIRE (per province culture) — 18 tags; EMP + VEM formable

10 Electoral provinces + Solland + The Moot + Sylvania + Marienburg (the seceded Wasteland). Sylvania
split into a human tag (`SYL`) and a Vampire tag (`VSY`, von Carstein) per Chris. Marienburg (`WAS`)
gets its own bespoke culture. Big density lever untaken: WFRP baronies/free-towns (Bergsburg,
Ubersreik, Bögenhafen…) could push this to 28–38, but they are RPG settlements, not well-attested
startable realms — held at honest depth. (Approved 2026-08-30.)

**`EMP` United Empire** carries all 12 human province cultures as its primary-culture set:
reiklander, middenlander, nordlander, hochlander, ostlander, ostermarker, talabeclander, stirlander,
averlander, wissenlander, sollander, sylvanian (human). **Excludes** halfling (the Moot),
sylvanian_vampire, and marienburger (Marienburg seceded — reintegration is a future journal event).

**`VEM` The Von Carstein Empire** (name is a placeholder — TODO, revisit for a better in-world
name) — a second, later-added formable (manual audit, 2026-09-03): VSY conquers the whole Empire
and seats itself on Altdorf instead of the human Electorates unifying. Purely `sylvanian_vampire`
in culture (a conquest tag, not a cultural unification like EMP), `empire` tier, `unrecognized`
type like its parent VSY. All ten Elector Counts plus Marienburg, Sylvania (human), and Solland are
`grand_principality`; the Moot is `principality` and `unrecognized` (not a recognized Electorate).

**`BRK` Brass Keep** — registry-only for now (manual audit, 2026-09-03), like the Eastern Steppes
Chaos tags: a Nurgle-held fortress in the Middle Mountains (Hochland/Middenland/Ostland border),
captured in the Great War against Chaos (2302 IC per *Warhammer: The Old World*/Lexicanum) and
never retaken; the Empire contains rather than besieges it via "the Picket." `PLACEHOLDER` culture
— no Chaos-marauder/cultist culture is authored anywhere in `common/cultures/` yet, so no
`common/country_definitions` entry exists until that's resolved (possibly a culture shared with
the Eastern Steppes marauders, a later decision).

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| EMP | `02_empire` | The Empire | formable | `reiklander`, `middenlander`, `nordlander`, `hochlander`, `ostlander`, `ostermarker`, `talabeclander`, `stirlander`, `averlander`, `wissenlander`, `sollander`, `sylvanian` | Altdorf | Karl Franz unifies the Electorates; excl. halfling / sylvanian_vampire / marienburger |
| REI | `02_empire` | Reikland | start | `reiklander` | Altdorf |  |
| MID | `02_empire` | Middenland | start | `middenlander` | Middenheim |  |
| NLD | `02_empire` | Nordland | start | `nordlander` | Salzenmund |  |
| HOC | `02_empire` | Hochland | start | `hochlander` | Hergig |  |
| OST | `02_empire` | Ostland | start | `ostlander` | Wolfenburg |  |
| OSM | `02_empire` | Ostermark | start | `ostermarker` | Bechafen |  |
| TAL | `02_empire` | Talabecland | start | `talabeclander` | Talabheim |  |
| STI | `02_empire` | Stirland | start | `stirlander` | Wurtbad |  |
| AVE | `02_empire` | Averland | start | `averlander` | Averheim |  |
| WIS | `02_empire` | Wissenland | start | `wissenlander` | Nuln |  |
| SOL | `02_empire` | Solland | start | `sollander` | Sudenburg | destroyed province claimant |
| MOO | `02_empire` | The Moot | start | `halfling` | Eicheschatten | halfling homeland |
| SYL | `02_empire` | Sylvania (human) | start | `sylvanian` | Drakenhof | the living population of Sylvania |
| VSY | `02_empire` | Sylvania (Vampire) | start | `sylvanian_vampire` | Drakenhof | von Carstein undead start |
| VEM | `02_empire` | The Von Carstein Empire | formable | `sylvanian_vampire` | Altdorf | VSY conquers the whole Empire; name TODO |
| WAS | `02_empire` | Marienburg (the Wasteland) | start | `marienburger` | Marienburg | seceded province Westerland; mercantile city-state |
| BRK | `02_empire` | Brass Keep | start | `PLACEHOLDER` | Brass Keep | Nurgle-held fortress, Middle Mountains; captured 2302 IC, never retaken; contained by the Empire's "the Picket" |

### 03 BRETTONIA (bretonnian, mousillon) — 17 tags; BRE formable

The 14 dukedoms are confirmed complete canon — no 15th, and Mousillon is one of the 14 (the cursed
dukedom, no ruling Duke). At honest ceiling (no density lever). BRE formable is `bretonnian` only —
Mousillon's cursed culture is excluded, parallel to EMP excluding the vampire culture. (Approved
2026-08-30.)

**`MOR` Massif Orcal** added on manual audit (2026-09-03) — not a dukedom, a remnant Orc & Goblin
holdout in the Bretonnian heartland above the Forest of Chalons, never fully cleared when the
kingdom was founded. Lives here rather than in `06_badlands` because `common/country_definitions/`
files are organized by geography, not culture (see that region's entry); its `orc`/`goblin`
culture ids are a cross-file reference to `common/cultures/greenskin.txt`, the mod's only
Greenskin cultures. Named by location rather than tribe — a flagged exception to this mod's
tribal-society naming convention — because no well-attested tribe/warlord name exists for it;
checked tabletop, *Warhammer: The Old World* Lexicanum, and Total War, and rejected a fan site's
"Evil Sunz Tribe" claim as unreliable (not in any GW/wiki source, and suspiciously duplicates a
40K Ork klan name). Revisit if a real name ever surfaces.

**`SKZ` Skullsmasherz** moved here from `06_badlands` on manual audit (2026-09-03) — Ugrok
Craktoof's orc tribe, holding the Grey Mountains on Bretonnia's southern flank. Reclassified as
Bretonnian geography (the border range itself, not Badlands territory beyond it), same
geography-not-culture filing principle as `MOR` above; `orc` culture id is a cross-file reference
to `common/cultures/greenskin.txt`.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| BRE | `03_brettonia` | Bretonnia | formable | `bretonnian` | Couronne | the King unites the dukedoms (excl. Mousillon) |
| COU | `03_brettonia` | Couronne | start | `bretonnian` | Couronne |  |
| LYO | `03_brettonia` | Lyonesse | start | `bretonnian` | Lyonesse |  |
| ART | `03_brettonia` | Artois | start | `bretonnian` | Artois |  |
| GIS | `03_brettonia` | Gisoreaux | start | `bretonnian` | Gisoreaux | spelling corrected from seed |
| MNF | `03_brettonia` | Montfort | start | `bretonnian` | Montfort |  |
| BAS | `03_brettonia` | Bastonne | start | `bretonnian` | Bastonne | birthplace of Gilles le Breton |
| AQU | `03_brettonia` | Aquitaine | start | `bretonnian` | Aquitaine |  |
| QUE | `03_brettonia` | Quenelles | start | `bretonnian` | Quenelles |  |
| CAR | `03_brettonia` | Carcassonne | start | `bretonnian` | Carcassonne |  |
| BRI | `03_brettonia` | Brionne | start | `bretonnian` | Brionne |  |
| BOR | `03_brettonia` | Bordeleaux | start | `bretonnian` | Bordeleaux |  |
| LAN | `03_brettonia` | L'Anguille | start | `bretonnian` | L'Anguille |  |
| PAR | `03_brettonia` | Parravon | start | `bretonnian` | Parravon |  |
| MOU | `03_brettonia` | Mousillon | start | `mousillon` | Mousillon | the cursed city / undead |
| MOR | `03_brettonia` | Massif Orcal | start | `orc`, `goblin` | Massif Orcal | remnant Greenskin holdout, Bretonnian heartland; named by location, no tribe attested — TODO revisit |
| SKZ | `03_brettonia` | Skullsmasherz | start | `orc` | — | Ugrok Craktoof; Grey Mtns, Bretonnia's southern flank |

### 04 KARAZ ANKOR (dawi, dawi_grey, dawi_norse, dawi_ancestral) — 18 tags; KAZ formable

10 active holds + Karak Angazbar (seed "Karak Azgaraz" corrected) + 7 ruined/fallen holds (all
sourced). **Ruined holds keep a dwarf tag even though they are occupied at game start** — they are
releasable "reclaim" realms (per Chris). Their current greenskin/Skaven occupiers are *separate* tags:
the greenskin occupiers (Red Eye Mountain, Black Crag, etc.) are added in 06 Badlands; Skaven have no
region yet (under-empire, a future epic). KAZ (the reunited Everlasting Realm) carries **all four**
dwarf cultures. (Approved 2026-08-30.)

**`dawi_badlands` renamed to `dawi_ancestral`** on manual audit (2026-09-03), reframed by age
rather than by which region they currently occupy. Per Dwarf founding-migration lore (Total
War/Fandom, consistent with tabletop): the Dawi founded their FIRST holds in the deep south (Karak
Zorn's kin — Karak Azul, Karak Eight Peaks, Karak Angazbar, Ekrund, Karak Drazh) and only
afterward pushed north into the World's Edge heartland (`dawi`, Karaz-a-Karak) where the High
King's throne and the greatest numbers ended up — then further north still, generations later, to
found the Norse holds (`dawi_norse`). So the real seniority order is `dawi_ancestral` (eldest) →
`dawi` (dominant but younger) → `dawi_norse` (youngest, most isolated). `dawi_ancestral`'s flavor
now centers on ancestor-pride and eldest-blood alongside its very real siege history, rather than
being defined by "the Badlands" — the hostile region its enemies, not its own people, gave the
name to. `dawi_grey` (Grey Mountains/Vaults, the trading holds) sits outside this age axis — a
lateral, not generational, distinction — and was left unchanged. See
`common/cultures/dwarven.txt` for the full writeup.

**All sixteen non-formable holds recognized** (manual audit, 2026-09-03) — every dwarf tag in this
region is now `country_type = recognized` (previously only KAZ and KAK were; every other hold was
`unrecognized`). KAZ's formation gate simplified back to a bare `is_country_type = recognized`,
matching EMP/BRE, now that the old mixed-type OR-pair workaround is no longer needed.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| KAZ | `04_karaz_ankor` | Karaz Ankor | formable | `dawi`, `dawi_grey`, `dawi_norse`, `dawi_ancestral` | Karaz-a-Karak | the Everlasting Realm reunited (all dwarf cultures) |
| KAK | `04_karaz_ankor` | Karaz-a-Karak | start | `dawi` | Karaz-a-Karak | the High King's hold (Everpeak) |
| ZHU | `04_karaz_ankor` | Zhufbar | start | `dawi` | Zhufbar |  |
| KAD | `04_karaz_ankor` | Karak Kadrin | start | `dawi` | Karak Kadrin | Slayer Keep |
| AZL | `04_karaz_ankor` | Karak Azul | start | `dawi_ancestral` | Karak Azul | southern hold |
| KEP | `04_karaz_ankor` | Karak Eight Peaks | start | `dawi_ancestral` | Karak Eight Peaks | contested / reclamation |
| BVR | `04_karaz_ankor` | Barak Varr | start | `dawi` | Barak Varr | the sea-hold |
| KNO | `04_karaz_ankor` | Karak Norn | start | `dawi_grey` | Karak Norn | Grey Mountains |
| KHI | `04_karaz_ankor` | Karak Hirn | start | `dawi_grey` | Karak Hirn | Vaults / Grey Mountains |
| KRD | `04_karaz_ankor` | Kraka Drak | start | `dawi_norse` | Kraka Drak | Norse dwarf hold |
| KAG | `04_karaz_ankor` | Karak Angazbar | start | `dawi_ancestral` | Karak Angazbar | Black Mountains ("Irongate"); seed name corrected |
| KUN | `04_karaz_ankor` | Karak Ungor | start | `dawi` | Karak Ungor | ruined (occupier "Red Eye Mountain" is a separate 06 tag) |
| KVN | `04_karaz_ankor` | Karak Varn | start | `dawi` | Karak Varn | ruined, flooded (Skaven/Night Goblin occupier separate) |
| EKR | `04_karaz_ankor` | Ekrund | start | `dawi_ancestral` | Ekrund | ruined, Black Gulf mines (Orc occupier separate) |
| GUN | `04_karaz_ankor` | Mount Gunbad | start | `dawi` | Mount Gunbad | ruined, brightstone mines (Night Goblin occupier separate) |
| DRZ | `04_karaz_ankor` | Karak Drazh | start | `dawi_ancestral` | Karak Drazh | ruined -469 IC (Orc occupier "Black Crag" is a separate 06 tag) |
| VLG | `04_karaz_ankor` | Karak Vlag | start | `dawi` | Karak Vlag | ruined, far north, destroyed by Chaos |
| SLV | `04_karaz_ankor` | Mount Silverspear | start | `dawi` | Mount Silverspear | ruined mine, Silver Road |

### 05 SOUTHERN REALMS (tilean, estalian, sartosan, border_princer) — 14 tags; TIL/EST formables

8 Tilean city-states + 3 Estalian kingdoms + one Border Princes tag. Tilea/Estalia held at their
well-known city-states (approved as-is by Chris — the deep Tilean/Estalian/Border-Prince supply lever
left untaken). **Sartosa (`SRT`) gets its own bespoke `sartosan` culture** — a melting-pot Tilean-
pirate people modeled on vanilla's Maltese (culture authored by #3419; the Total War "vampire-pirate
Sartosa" is not tabletop canon, so Sartosa stays a human pirate haven). **One Border Princes tag
(`BPR`)** — its canonical decentralization is intended to be represented by a government/law variant, a
later `common/` authoring task (out of scope for this docs-only registry). TIL (united Tilea) carries
both `tilean` and `sartosan`. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| TIL | `05_southern_realms` | Tilea | formable | `tilean`, `sartosan` | Miragliano | the city-states unite (incl. Sartosa) |
| MIR | `05_southern_realms` | Miragliano | start | `tilean` | Miragliano |  |
| LUC | `05_southern_realms` | Luccini | start | `tilean` | Luccini |  |
| REM | `05_southern_realms` | Remas | start | `tilean` | Remas |  |
| TOB | `05_southern_realms` | Tobaro | start | `tilean` | Tobaro |  |
| TRA | `05_southern_realms` | Trantio | start | `tilean` | Trantio |  |
| PAV | `05_southern_realms` | Pavona | start | `tilean` | Pavona |  |
| VER | `05_southern_realms` | Verezzo | start | `tilean` | Verezzo |  |
| SRT | `05_southern_realms` | Sartosa | start | `sartosan` | Sartosa | pirate haven; melting-pot culture |
| EST | `05_southern_realms` | Estalia | formable | `estalian` | Magritta | the kingdoms unite |
| BIL | `05_southern_realms` | Bilbali | start | `estalian` | Bilbali |  |
| MAG | `05_southern_realms` | Magritta | start | `estalian` | Magritta |  |
| CNT | `05_southern_realms` | Cantonia | start | `estalian` | Cantonia | minor Estalian kingdom |
| BPR | `05_southern_realms` | Border Princes | start | `border_princer` | — | loose principalities; decentralization → a later law/government-type variant |

### 06 BADLANDS (orc, goblin) — 11 tags; no formable

Greenskin tribes/strongholds of the Badlands / World's Edge. **Chris approved Total War: Warhammer as a
name source for this region** (in addition to tabletop), so names blend both. Deduplicated so no polity
is double-tagged by tribe *and* stronghold (Red Fangs = Black Crag; Ironclaw = Iron Rock; Crooked Moon =
Karak Eight Peaks; Grimgor's Red Eye = ex-Karak Ungor). **No WAAAGH! formable** (Chris dropped it).
Savage Orcs are handled in 09 Southlands (their canon heartland) with a new `savage_orc` culture — see
that region. (Approved 2026-08-30.)

**`common/country_definitions/` files are organized by geography, not by culture (Chris,
2026-09-03):** a tag's script entry lives in the file for the region it's physically located in,
even if its culture is defined elsewhere. Two Greenskin tags physically on/inside Bretonnia are
defined in `03_brettonia.txt` instead of here — Massif Orcal (`MOR`, the Bretonnian *heartland*
above the Forest of Chalons) from the start, and Skullsmasherz (`SKZ`, the Grey Mountains on
Bretonnia's southern flank) moved there on a later manual audit the same day, once Chris confirmed
the border range itself reads as Bretonnian rather than Badlands geography — see that region's
entry for both tags' full writeup. Both still use `orc`/`goblin` culture ids from
`common/cultures/greenskin.txt` (a cross-file culture reference; those are the mod's only
Greenskin cultures).

**Naming convention (Chris, 2026-09-03):** tribal societies — Norsca, Greenskins (this region and
Bretonnia's `MOR`/`SKZ`), Ogre Kingdoms — are named by tribe, not by location/stronghold; Skaven
(no region yet) will likewise be named by clan, not location, once authored. Audited against this
on 2026-09-03: Norsca and Ogre Kingdoms were already fully tribe-named; this region's own roster
was already tribe-named (`MOR`, the one location-named exception, lives in Bretonnia's file
instead).

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| RED | `06_badlands` | Red Eye | start | `orc` | Red Eye | Grimgor Ironhide's 'Ardboyz; ex-Karak Ungor |
| CRM | `06_badlands` | Crooked Moon | start | `goblin` | — | Skarsnik's Night Goblins; Karak Eight Peaks |
| BKA | `06_badlands` | Broken Axe | start | `goblin` | — | Grom the Paunch (Goblin); Misty Mountain |
| RFG | `06_badlands` | Red Fangs | start | `orc` | Black Crag | Gorfang Rotgut; holds Black Crag (ex-Karak Drazh) |
| ICL | `06_badlands` | Ironclaw | start | `orc` | Iron Rock | Gorbad Ironclaw; holds Iron Rock (N. Badlands) |
| BSB | `06_badlands` | Bloody Sunz | start | `orc` | — | Grumlok & Gazbag; Badlands orc tribe |
| BNR | `06_badlands` | Bonerattlaz | start | `orc` | — | Azhag the Slaughterer; N. World's Edge |
| BTO | `06_badlands` | Broken Tooth | start | `orc` | — | Crusher Zogoth; pre-Gorbad Iron Rock (historical) |
| BRN | `06_badlands` | Broken Nose | start | `goblin` | — | Goblin tribe of the Vaults |
| BLV | `06_badlands` | Black Venom | start | `goblin` | — | Forest Goblin tribe, S. of Black Fire Pass |
| RDV | `06_badlands` | Redvenom | start | `goblin` | — | Snagla Grobspit's Forest Goblins |

**Density reserve (not yet allocated — add later if Chris wants a denser Badlands).** Confirmed TW:W
Greenskins faction names, race/location wiki-unstated (would be representative orc/goblin tribes):
Bloody Spearz · Scabby Eye · Necksnappers · Deff Grindaz · Drippin Fangs · Dimmed Sunz · Moon Howlerz ·
Da Mad Howlerz · Creeping Death · Red Cloud · Blue Vipers · Teef Snatchaz · Da Cage Breakaz · Broken
Chainz (14 available). "Dark Land Orcs" belongs to 10 Dark Lands; Karak Varn's Skaven occupiers await a
future under-empire epic (no region yet).

### 07 NEHEKHARA (nehekharan, lahmian_vampire) — 11 tags; NEH formable

The tomb-cities of the Tomb Kings. **Lahmia (`LAH`) carries a bespoke `lahmian_vampire` culture** —
Neferata's bloodline, the cradle of vampires (culture authored by #3419). All other cities are
`nehekharan` (the ancient Tomb Kings civilization). NEH (Settra reunites the Land of the Dead) is
`nehekharan` only — the Lahmian vampires are Settra's enemies, not part of his realm. **Nagashizzar has
no tag** — reserved for a future Skaven clan (no Skaven region yet). (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| NEH | `07_nehekhara` | Nehekhara | formable | `nehekharan` | Khemri | Settra reunites the Land of the Dead |
| KHM | `07_nehekhara` | Khemri | start | `nehekharan` | Khemri | Settra's city (the capital) |
| ZND | `07_nehekhara` | Zandri | start | `nehekharan` | Zandri |  |
| NUM | `07_nehekhara` | Numas | start | `nehekharan` | Numas |  |
| LAH | `07_nehekhara` | Lahmia | start | `lahmian_vampire` | Lahmia | cradle of vampires (Neferata) |
| LYB | `07_nehekhara` | Lybaras | start | `nehekharan` | Lybaras | Queen Khalida |
| RAS | `07_nehekhara` | Rasetra | start | `nehekharan` | Rasetra |  |
| MAH | `07_nehekhara` | Mahrak | start | `nehekharan` | Mahrak | City of the Dead |
| QUA | `07_nehekhara` | Quatar | start | `nehekharan` | Quatar | City of the Springs of the Dead |
| BHA | `07_nehekhara` | Bhagar | start | `nehekharan` | Bhagar | the Dune-Sea oasis |
| KAS | `07_nehekhara` | Ka-Sabar | start | `nehekharan` | Ka-Sabar | City of Bronze |

### 10 DARK LANDS (dawi_zharr, hobgoblin) — 6 tags; ZHA + KHN formables

The Chaos Dwarfs (Dawi Zharr) and their hobgoblin vassals. Canon-thin beyond Zharr-Naggrund; held at 6
(Chris approved as-is). Two formables — Chaos Dwarfs and hobgoblins are distinct peoples with separate
unifiers. "Dark Land Orcs" (a TW:W Greenskins faction) could be added here later if a greenskin Dark
Lands tag is wanted. (Approved 2026-08-30. Closes the Old World tranche.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| ZHA | `10_dark_lands` | Dawi Zharr Empire | formable | `dawi_zharr` | Zharr-Naggrund | the Chaos Dwarf empire |
| MZN | `10_dark_lands` | Mingol Zharr-Naggrund | start | `dawi_zharr` | Zharr-Naggrund | the Tower of Zharr (capital) |
| GOR | `10_dark_lands` | Gorgoth | start | `dawi_zharr` | Gorgoth | Chaos Dwarf hold |
| UZK | `10_dark_lands` | Uzkulak | start | `dawi_zharr` | Uzkulak | Port of Zharr |
| KHN | `10_dark_lands` | Great Khanate | formable | `hobgoblin` | — | Hobgobla-Khan unites the hobgoblins |
| HGK | `10_dark_lands` | Hobgobla-Khan | start | `hobgoblin` | — | the great hobgoblin realm |

### 08 ARABY (PLACEHOLDER + bretonnian crusaders) — 10 tags; ARB formable

Arabyan city-states (culture `PLACEHOLDER` until a future epic) + two **Bretonnian crusader** holdings
from the Great Crusade Against Araby (both `bretonnian`, sourced tabletop canon). Both crusader colonies
historically *fell* (Fyrus to an Arabyan uprising; Antoch razed by Lizardmen), so they are reclaim /
crusader-revival starts. Fyrus itself is kept as a releasable **Arabyan** tag; the Knights of Origo
(the order that once held it) are a separate Bretonnian tag. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| ARB | `08_araby` | Sultanate of Araby | formable | `PLACEHOLDER` | Al-Haikk | the sultanates unite |
| AHK | `08_araby` | Al-Haikk | start | `PLACEHOLDER` | Al-Haikk | the Golden City (Jaffar's capital) |
| COP | `08_araby` | Copher | start | `PLACEHOLDER` | Copher | spice-port; crusader landing site |
| LSK | `08_araby` | Lashiek | start | `PLACEHOLDER` | Lashiek | City of Corsairs; besieged in the Crusades |
| MTK | `08_araby` | Martek | start | `PLACEHOLDER` | Martek | desert city |
| BEL | `08_araby` | Bel-Aliad | start | `PLACEHOLDER` | Bel-Aliad | ruined "City of Dust" (revive/ruin start) |
| ELK | `08_araby` | El-Kalabad | start | `PLACEHOLDER` | El-Kalabad | desert city |
| FYR | `08_araby` | Fyrus | start | `PLACEHOLDER` | Fyrus | Arabyan island (releasable; once held by the Knights of Origo) |
| ORG | `08_araby` | Knights of Origo | start | `bretonnian` | Fyrus | Bretonnian crusader order (Holy Order of Saint Origo) |
| ANT | `08_araby` | Antoch | start | `bretonnian` | Antoch | "the Crusader City", Gulf of Medes (razed by Lizardmen) |

### 09 SOUTHLANDS (PLACEHOLDER + savage_orc) — 8 tags; no formable

The Southlands are canon-thin for *human/native* realms (Zlatlan is the one named Lizardmen temple-city
here; the western coast has only unnamed Arabyan colonies). The real supply is the **Savage Orcs**,
whose canon heartland is the Southlands jungles — they get the new `savage_orc` culture (**pending
#3404**). No "Southlands" reserve formable (Chris — too vague to be worth one right now). The bulk of
Lizardmen live in Lustria (19). (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| ZLA | `09_southlands` | Zlatlan | start | `PLACEHOLDER` | Zlatlan | Lizardmen temple-city (Southlands) |
| TPK | `09_southlands` | Top-knotz | start | `savage_orc` | — | Savage Orcs, Black Gulf coast — **culture pending #3404** |
| BHZ | `09_southlands` | Bloody Handz | start | `savage_orc` | — | Wurrzag da Great Green Prophet (Dragonback foothills) |
| BCB | `09_southlands` | Boneclubs | start | `savage_orc` | — | Savage Orc jungle tribe |
| SNK | `09_southlands` | Snakeskinz | start | `savage_orc` | — | Savage Orc jungle tribe (Boneclubs' rivals) |
| HHZ | `09_southlands` | Headhuntaz | start | `savage_orc` | — | nomadic Savage Orcs |
| WWG | `09_southlands` | Waaagh-Waaagh | start | `savage_orc` | — | "the greatest" Savage Orc tribe, Southlands |
| WSK | `09_southlands` | White Skullz | start | `savage_orc` | — | Savage Orcs who raid Araby |

### 11 OGRE KINGDOMS (PLACEHOLDER) — 12 tags; no formable

Ogre tribes of the Mountains of Mourn. Names blend tabletop + Total War: Warhammer (Chris approved TW as
a source here, as with the greenskins). **No formable** (Chris dropped OGR). Ogres are semi-nomadic with
**no named capital** in canon (the Great Maw crater is the spiritual center) — placeholder capitals stay
blank. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| GGT | `11_ogre_kingdoms` | Goldtooth | start | `PLACEHOLDER` | — | Greasus Goldtooth (Overtyrant) |
| IRN | `11_ogre_kingdoms` | Ironskin | start | `PLACEHOLDER` | — | Ghark Ironskin |
| GLG | `11_ogre_kingdoms` | Golgfag's Maneaters | start | `PLACEHOLDER` | — | Golgfag Maneater (mercenaries) |
| MAW | `11_ogre_kingdoms` | Disciples of the Maw | start | `PLACEHOLDER` | — | Skrag the Slaughterer |
| BGZ | `11_ogre_kingdoms` | Blood Guzzlers | start | `PLACEHOLDER` | — | Bul Mallet-hands; Vale of Webs |
| EYB | `11_ogre_kingdoms` | Eyebiter | start | `PLACEHOLDER` | — | Malron Eyebiter |
| RSK | `11_ogre_kingdoms` | Rock Skulls | start | `PLACEHOLDER` | — | break boulders with their heads |
| CXC | `11_ogre_kingdoms` | Crossed Clubs | start | `PLACEHOLDER` | — | roaming braggart Maneaters |
| AGF | `11_ogre_kingdoms` | Angry Fist | start | `PLACEHOLDER` | — | most "advanced" tribe; assailed Karak Azorn |
| THG | `11_ogre_kingdoms` | Thunderguts | start | `PLACEHOLDER` | — | named tribe |
| FSM | `11_ogre_kingdoms` | Feastmaster | start | `PLACEHOLDER` | — | TW:W minor faction |
| SOM | `11_ogre_kingdoms` | Sons of the Mountain | start | `PLACEHOLDER` | — | TW:W minor faction |

**Density reserve (not yet allocated).** Confirmed TW:W Ogre Kingdoms faction names for a denser roster:
Bloodmaw · Fleshgreeders · Fulg · Lazarghs · Loose Tooth · Mountaineaters · Ogre Rebels · Sabreskin ·
Treehammers · Flamegullets · Sharktooth · Stoneshatter · The Famished · Rock Clubs (14 available).

### 12 EASTERN STEPPES (PLACEHOLDER) — 4 tags; no formable

The Chaos marauder confederations of the far eastern steppes (north/east of the Worlds Edge). Held at
the 4 confederations (Chris) — the many named Hung/Kurgan sub-tribes (Yin, Chi-An, Mung, Aghols…) are
generic marauder flavor and left as a reserve. **No formable** (no canon united-steppes polity). Their
loose confederation status is intended to be represented by a government/law variant (as with the
Border Princes) — a later `common/` authoring task, out of scope here. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| KUR | `12_eastern_steppes` | Kurgan | start | `PLACEHOLDER` | — | Chaos marauder confederation; decentralization → a later law/government-type variant |
| HUN | `12_eastern_steppes` | Hung | start | `PLACEHOLDER` | — | eastern Chaos marauder confederation |
| KUL | `12_eastern_steppes` | Kul | start | `PLACEHOLDER` | — | Asavar Kul's great host (Great War against Chaos) |
| TON | `12_eastern_steppes` | Tong | start | `PLACEHOLDER` | — | steppe tribe |

### 13 CATHAY (PLACEHOLDER) — 11 tags; CTH formable

Grand Cathay, sourced from Total War: Warhammer 3 / Warhammer: The Old World (2023+) — old tabletop had
no named Cathayan provinces (Chris approved the newer canon layer). The five Dragon-regent provinces +
the Imperial core are the divided starts; **CTH** (note: not `CAT`) is the reunified-empire formable.
Non-canon names dropped (Xicoatl = a Lizardmen site; "Turtle City" = the Turtle Gate; Longshan/Baxil/
Bei-Sang = unsourced). All PLACEHOLDER culture. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| CTH | `13_cathay` | Grand Cathay | formable | `PLACEHOLDER` | Wei-jin | the Celestial Empire reunified under the Dragon Emperor |
| WEI | `13_cathay` | Imperial Provinces (Wei-jin) | start | `PLACEHOLDER` | Wei-jin | the Dragon Emperor & Moon Empress; the Celestial City |
| NGA | `13_cathay` | Northern Provinces (Nan-Gau) | start | `PLACEHOLDER` | Nan-Gau | Miao Ying the Storm-Dragon; commands the Great Bastion |
| SHY | `13_cathay` | Western Provinces (Shang-Yang) | start | `PLACEHOLDER` | Shang-Yang | Zhao Ming the Iron-Dragon; Ivory Road |
| SHW | `13_cathay` | Central Provinces (Shang Wu) | start | `PLACEHOLDER` | Shang Wu | Yuan Bo the Jade-Dragon; Administrator of the Realm |
| FUC | `13_cathay` | Eastern Provinces (Fu-Chow) | start | `PLACEHOLDER` | Fu-Chow | Yin-Yin the Sea-Dragon; greatest port |
| FUH | `13_cathay` | Southern Provinces (Fu-Hung) | start | `PLACEHOLDER` | Fu-Hung | Li Dao the Fire-Dragon; "the Chanting City" |
| GBS | `13_cathay` | The Great Bastion | start | `PLACEHOLDER` | — | the Great Wall garrison (Dragon/Snake/Turtle Gates) |
| MKY | `13_cathay` | Mountains of Heaven | start | `PLACEHOLDER` | — | the Monkey King (autonomous usurper) |
| SKT | `13_cathay` | The Sky-Titans | start | `PLACEHOLDER` | — | ancient allied giants gifted gunpowder |
| DGF | `13_cathay` | The Grand Dragon Fleet | start | `PLACEHOLDER` | Fu-Chow | Cathay's imperial navy (the Jade Fleet) |

> **Regions 14 Ind, 15 Khuresh, 16 Nippon — DEFERRED (0 tags).** Ind and Khuresh have no named realms in
> either tabletop or Total War; Nippon has only medium-confidence secondary-source names. All three are
> left for a future epic rather than padded with invented or low-confidence tags. (Chris, 2026-08-30.)

### 17 ULTHUAN (High Elves, PLACEHOLDER) — 11 tags; ULT formable

The Ten Kingdoms of Ulthuan — confirmed complete canon (high confidence). ULT is the Phoenix King
reuniting them. Nagarythe is kept as a normal High Elf kingdom (Shadow Warriors era, post-Sundering).
All PLACEHOLDER culture (High Elf cultures are a future epic). (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| ULT | `17_ulthuan` | Ulthuan | formable | `PLACEHOLDER` | Lothern | the Phoenix King's realm united |
| LOT | `17_ulthuan` | Eataine (Lothern) | start | `PLACEHOLDER` | Lothern | realm of the Sea Lords; the capital |
| CAL | `17_ulthuan` | Caledor | start | `PLACEHOLDER` | Tor Caled | dragon princes |
| SAP | `17_ulthuan` | Saphery | start | `PLACEHOLDER` | Saphery | land of mages |
| NGY | `17_ulthuan` | Nagarythe | start | `PLACEHOLDER` | — | the Shadowlands (Shadow Warriors) |
| TIR | `17_ulthuan` | Tiranoc | start | `PLACEHOLDER` | Tor Anroc | the drowned kingdom / charioteers |
| CHR | `17_ulthuan` | Chrace | start | `PLACEHOLDER` | Tor Achare | home of the White Lions |
| AVL | `17_ulthuan` | Avelorn | start | `PLACEHOLDER` | — | the Everqueen's realm |
| YVR | `17_ulthuan` | Yvresse | start | `PLACEHOLDER` | Tor Yvresse | the misty realm |
| ELL | `17_ulthuan` | Ellyrion | start | `PLACEHOLDER` | Tor Elyr | horse-country |
| COT | `17_ulthuan` | Cothique | start | `PLACEHOLDER` | — | eastern coastal realm |

### 18 NAGGAROTH (Dark Elves, PLACEHOLDER) — 7 tags; NAG formable

The six Black Cities of Naggaroth + NAG formable (Malekith unites Naggaroth under the Witch King). All
PLACEHOLDER culture (Dark Elf cultures are a future epic). **Open question — Athel Toralien & elven
colonies:** Athel Toralien was dropped here; it and other Sundering-era/Old-World elf colonies (High &
Dark) are deferred to a future "elven colonies" pass, likely their own cross-region treatment rather
than one Naggaroth row. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| NAG | `18_naggaroth` | Naggaroth | formable | `PLACEHOLDER` | Naggarond | the Witch King's realm united |
| NGD | `18_naggaroth` | Naggarond | start | `PLACEHOLDER` | Naggarond | the Tower of Cold (Malekith's capital) |
| HAR | `18_naggaroth` | Har Ganeth | start | `PLACEHOLDER` | Har Ganeth | City of Executioners (cult of Khaine) |
| GHR | `18_naggaroth` | Ghrond | start | `PLACEHOLDER` | Ghrond | the North Tower (Morathi's Dark Convent) |
| CLK | `18_naggaroth` | Clar Karond | start | `PLACEHOLDER` | Clar Karond | Tower of Doom (Black Ark shipyards) |
| KKR | `18_naggaroth` | Karond Kar | start | `PLACEHOLDER` | Karond Kar | Slaver's Gate / Tower of Despair |
| HGF | `18_naggaroth` | Hag Graef | start | `PLACEHOLDER` | Hag Graef | the Dark Crag (second city) |

### 19 LUSTRIA (Lizardmen, PLACEHOLDER) — 18 tags; LUS formable

The temple-cities of the Lizardmen, at max density (Chris approved TW:W as a name source, as with the
greenskins/Cathay). LUS is the Slann reuniting the Old Ones' dominion. All rows are **Lustrian** —
Southlands Lizardmen (Zlatlan; the TW factions Kroq-Gar/Tiktaq'to) are excluded from this file per
Chris and live in 09 Southlands. Sourced corrections: "Spektotl"→Spektazuma; "Zaqua" unverified
(dropped); Tlanxla and "Tlanxa" are one city (TLN), Tlax is separate (TLA). Sentinels of Xeti and 8
lower-detail cities held as reserve. All PLACEHOLDER culture. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| LUS | `19_lustria` | Lustria | formable | `PLACEHOLDER` | Itza | the Old Ones' dominion united |
| ITZ | `19_lustria` | Itza | start | `PLACEHOLDER` | Itza | the First City (Lord Kroak / Gor-Rok) |
| HEX | `19_lustria` | Hexoatl | start | `PLACEHOLDER` | Hexoatl | City of the Sun (Mazdamundi) |
| XLA | `19_lustria` | Xlanhuapec | start | `PLACEHOLDER` | Xlanhuapec | City of Mists |
| TLX | `19_lustria` | Tlaxtlan | start | `PLACEHOLDER` | Tlaxtlan | City of the Moon |
| CHQ | `19_lustria` | Chaqua | start | `PLACEHOLDER` | Chaqua | City of Gold |
| PAH | `19_lustria` | Pahuax | start | `PLACEHOLDER` | Pahuax | Oxyotl's home (Ghosts of Pahuax) |
| XAH | `19_lustria` | Xahutec | start | `PLACEHOLDER` | Xahutec | City of Echoes (ruined by a Chaos portal) |
| QTZ | `19_lustria` | Quetza | start | `PLACEHOLDER` | Quetza | the Defiled (Clan Pestilens) |
| HUA | `19_lustria` | Huatl | start | `PLACEHOLDER` | Huatl | City of Reawakening (being re-founded) |
| OYX | `19_lustria` | Oyxl | start | `PLACEHOLDER` | Oyxl | the Eternal City (ruined by Daemons) |
| XHO | `19_lustria` | Xhotl | start | `PLACEHOLDER` | Xhotl | City of Fate (Kroq-Gar's stand) |
| AXL | `19_lustria` | Axlotl | start | `PLACEHOLDER` | Axlotl | the Star City |
| CHU | `19_lustria` | Chupayotl | start | `PLACEHOLDER` | Chupayotl | the Sunken City (SE Lustria) |
| KON | `19_lustria` | Konquata | start | `PLACEHOLDER` | Konquata | youngest temple-city (founded 2520 IC) |
| TLN | `19_lustria` | Tlanxla | start | `PLACEHOLDER` | Tlanxla | City of the Sky (destroyed in the Catastrophe) |
| SPZ | `19_lustria` | Spektazuma | start | `PLACEHOLDER` | Spektazuma | City of Lenses (ruined) |
| TLA | `19_lustria` | Tlax | start | `PLACEHOLDER` | Tlax | City of Ghosts (ruined) |
