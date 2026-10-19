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

- [x] 00 Norsca (14)
- [x] 01 Kislev (10)
- [x] 02 Empire (24)
- [x] 03 Bretonnia (23)
- [x] 04 Karaz Ankor (28)
- [x] 05 Southern Realms (29)
- [x] 06 Badlands (11)
- [x] 07 Nehekhara (11)
- [x] 10 Dark Lands (7)
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
- [x] 19 Lustria (19)

**Total: 240 tags** (16 formables, 224 starts) — all 20 regions resolved (17 with tags; Ind, Khuresh,
Nippon deferred with 0), plus the `98_unclaimed` placeholder owner `UNO` (#6391). Content is **honest, well-attested Warhammer
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
  - `dark_lands_orc`, `badlands_orc`, `cathayan_orc`, `lustrian_orc` — orc subcultures, defined in `common/cultures/greenskin.txt` beside `mountain_orc` (the former `orc`); not yet assigned to any tag or state.

## Conventions

- **3 uppercase ASCII letters**, mnemonic per polity (Vic3 vanilla convention: `GBR`, `FRA`).
- **Formable = the iconic national code; start fragments = polity codes.** `EMP` is the formable
  *The Empire*; `REI` (Reikland) etc. are the start tags that form it.
- **One row per tag**, columns: `TAG | region file | polity | kind (formable/start) | primary culture
  | placeholder capital | notes`.
- **The placeholder-capital column is a human-readable seat note, not the authority.** The real
  `capital = STATE_*` of every tag is in `common/country_definitions/` (convention in
  `.claude/rules/peoples.md`); where the two differ, the definition wins.
- **Files mirror the culture epic** (#3404), same region numbers, stems matching the shipped culture
  filenames verbatim (including `03_brettonia`).
- **Old World rows** (00–07, 10) carry a real primary-culture id from `common/cultures/*.txt`. A
  deepened minor realm with no bespoke culture takes its region's dominant existing culture id (never
  invent, never `PLACEHOLDER` for Old World). **Distant rows** (08, 09, 11–19) carry the literal token
  `PLACEHOLDER` until a future epic authors those cultures.
- **`XS*` = Skaven placeholder tags** (board #6373, 2026-10-01). `XSA`–`XSD` and `XSG`–`XSL` (no
  `XSE`/`XSF`) are deliberately generic stand-ins for unnamed Skaven clans that own states on the
  painted start map — not real nations. Display names "Skaven Clan A–J (placeholder)" in code order,
  adjective "Skaven", `goblin` culture, greenskin house-style heraldry with no rat iconography. Their
  limits (greenskin pops, culture and arms) are deliberate until a Skaven culture exists. The codes are
  frozen once shipped like any other: real clans get **new** codes and supersede these tags, which are
  never renamed into a clan.
- **#6373 additions take the painted legend colour.** Tags defined for the start-ownership map take
  their colour exactly from `mapgen/config/state_ownership_legend.json`, not from their culture.
- **Wood elves (Asrai) have no region file of their own** (board #6373, 2026-10-01). Their realms
  carry the `wood_elf` culture (#6379) and are filed by the geography of their states, like any
  other tag: Athel Loren's five realms and the Oak of Prophecy (`ANM`, `ARG`, `TLS`, `TRG`, `WYD`,
  `OKP`) in `03_brettonia`, `GRW` and `LAU` in `02_empire`, `MGL` in `05_southern_realms`, `SOT` in
  `00_norsca`. All are `unrecognized`/`principality`. `GRW` (Gryphon Wood) and `MGL` (Miramar Glade)
  carry provisional names that Chris will redo; the codes stay frozen.
- **Ogre rows carry `ogre`.** The `ogre` culture now exists (#6379), so every 11 Ogre Kingdoms row
  takes it in place of `PLACEHOLDER`. The other distant regions keep `PLACEHOLDER`.
- **`UNO` = Unclaimed Lands, the decentralized placeholder owner** (board #6391, Chris 2026-10-02).
  It owns every state the start map gives no nation — the drawn Old World's `unowned` wilderness and
  every out-of-scope `placeholder` state — and is **generator-mapped, never painted** (no legend entry;
  `generate_state_history.py` maps those owner tokens to `c:UNO`). `decentralized`/`principality`,
  `goblin` as a disclosed one-culture stand-in (it does not describe the elves, lizardmen, Nippon or
  other peoples of the land it holds), no capital, and **no homelands** in its states (#6374). Filed in
  its own `98_unclaimed` files. Frozen like any shipped code: it is never renamed into a real polity.

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
ANM
ANT
AQL
AQU
ARB
ARG
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
CRB
CRM
CTH
CXC
DGF
DLO
DOL
DON
DRZ
DUN
EKR
ELK
ELL
EMP
ERE
ESS
EST
EYB
FSM
FUC
FUH
FYR
GAS
GBS
GDO
GGT
GHR
GIS
GLG
GOR
GRA
GRW
GUN
HAR
HAS
HEX
HGF
HGK
HHZ
HKN
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
KIZ
KKR
KNO
KON
KOR
KRD
KRV
KSV
KUL
KUN
KUR
KVE
KVN
KZF
LAH
LAN
LAU
LOT
LSK
LUC
LUS
LYB
LYO
MAG
MAH
MAR
MAW
MGL
MID
MIR
MKY
MNF
MON
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
OKP
ORG
ORT
OSM
OST
OYX
PAH
PAR
PAV
PON
PRA
QTZ
QUA
QUE
RAA
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
SKG
SKT
SKZ
SLV
SNA
SNK
SOL
SOM
SOR
SOT
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
TLS
TLX
TOB
TON
TPK
TRA
TRG
TRO
ULT
UNG
UNO
URS
USR
UVE
UZK
VAR
VEM
VER
VLG
VMP
VOL
VSY
WEI
WIS
WSK
WWG
WYD
XAH
XHO
XLA
XSA
XSB
XSC
XSD
XSG
XSH
XSI
XSJ
XSK
XSL
YVR
ZHA
ZHU
ZLA
ZND
```

## Deferred check (owned by epic #3414)

Whether the engine **hard-requires exactly 3 chars** or merely tolerates longer tags. Strong evidence
it is 3: all 827 vanilla tags are exactly 3 characters. The roster is drafted at 3 chars regardless.
(Colors, `country_type`/`tier` and real `capital = <state>` ids are separate decisions on the
epic, not tag-uniqueness concerns; capitals are now set in `common/country_definitions/` 00-07 and
10 per `.claude/rules/peoples.md`, with 11 still pending.)

## Roster

### 00 NORSCA (norscan, goblin, wood_elf) — 14 tags; no formable

7 core High Tribes are solid canon; Hastlings + Kvelligs are medium-confidence High Tribes. Seed's
Skjaelings/Sortsvinar were originally dropped as unverified (Chris's call, approved 2026-08-30), but
a later lore audit (2026-09-04) turned up a solid primary-source cite for Sortsvinaer — see below.
NSC unifier tag dropped on manual audit — the High Tribes keep their own identity even after mass
conquest; a unification journal entry may represent this later instead of a formable country. All
tribes are `grand_principality` tier, `unrecognized` type (raiding tribes under a jarl, not part of
any order the civilised south recognises); a future country type may be added to represent tribal
societies more precisely. **Exception:** the three lesser tribes added below (SNA/SOR/URS) are
`principality` tier, not `grand_principality` — smaller gatherings than the seven High Tribes and
Hastlings/Kvelligs, still `unrecognized` (Chris, 2026-09-04).

**Three lesser tribes added** on a lore-audit pass (2026-09-04, Chris): *Warhammer: The Old World*
Rulebook (pg. 82-83/224) names Snaegr, Sortsvinaer and Ursfjordings as the Norse's three known
"lesser tribes" — smaller gatherings bound by familial/martial/religious ties rather than the
seven great High Tribes. This directly re-supports Sortsvinaer, previously dropped as unverified.
Ursfjordings' hold of Ursfjord (Goromadny Mountains) is also home to Beorg Bearstruck's "Bearmen of
Urslo" mercenary warband — a sub-group of the tribe, not a separate tag. Other lore-audited
candidates (Fjaergard, Tribe of the Crow, Tribe of the Mighty Serpent — all solidly sourced) were
not added this pass; Iron Wolves was rejected as now culturally Kurgan, not Norscan (Eastern
Steppes material instead), and Skeggi was added to 19 Lustria instead of here (see that region).

**#6373 (2026-10-01):** SNA, SOR and URS now have country definitions. The ownership-review tag `GMD`
("Goromadny") duplicated URS for the same coast and was merged into it — URS took GMD's painted colour;
`GMD` never became a code. `XSD` (Hell Pit) is a Skaven placeholder (see *Conventions*), filed here by
the geography of its states. Spelling corrected to the map's "Goromadny" (was "Goromandy").
`SOT` Sisters of Twilight, the twin sisters' wood-elf realm, is filed here by the geography of its
state (the Forest of Sighs, in Norsca's state file); see the wood-elves convention (#6373 phase B).

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| SAR | `00_norsca` | Sarls | start | `norscan` | Sarl Encampment (Bay of Blades) | Wolf of the Sea |
| AES | `00_norsca` | Aeslings | start | `norscan` | Kraken Coast (non-canon) | Slaanesh-leaning tribe |
| BAE | `00_norsca` | Baersonlings | start | `norscan` | Strovengaard (non-canon) | reavers, on speaking terms w/ humanity |
| BJO | `00_norsca` | Bjornlings | start | `norscan` | Bjornling's Gathering | traders/fishers/sailors |
| SKA | `00_norsca` | Skaelings | start | `norscan` | Naglfari Coast (non-canon) | Khorne-leaning |
| GRA | `00_norsca` | Graelings | start | `norscan` | Graeling Moot (Norsveg Plain) | Tzeentch-leaning sea raiders |
| VAR | `00_norsca` | Varg | start | `norscan` | Varg Camp | northern Chaos-touched tribe |
| HAS | `00_norsca` | Hastlings | start | `norscan` | Trollheim Mountains (non-canon) | High Tribe near the Chaos Wastes |
| KVE | `00_norsca` | Kvelligs | start | `norscan` | Taldursfjord (non-canon) | High Tribe near the Chaos Wastes |
| SNA | `00_norsca` | Snaegr | start | `norscan` | Hall of Snaegr (Ulfwrenar Mountains) | `principality`/`unrecognized`; lesser tribe (*WH: The Old World* Rulebook) |
| SOR | `00_norsca` | Sortsvinaer | start | `norscan` | Sortsvinaer (Helspire Coast) | `principality`/`unrecognized`; lesser tribe (*WH: The Old World* Rulebook); re-supports the seed name dropped in the original draft |
| URS | `00_norsca` | Ursfjordings | start | `norscan` | Ursfjord (Frozen Coast) | `principality`/`unrecognized`; lesser tribe, Goromadny Mtns; home hold of Beorg Bearstruck's Bearmen of Urslo warband; absorbed review tag GMD (#6373) |
| XSD | `00_norsca` | Skaven Clan D (placeholder) | start | `goblin` | Hell Pit (Hell Pit Depths) | Skaven placeholder (Hell Pit); `principality`/`unrecognized`; see *Conventions* (#6373) |
| SOT | `00_norsca` | Sisters of Twilight | start | `wood_elf` | Forest of Sighs (West Helspire Mountains, SOT slice) | `principality`/`unrecognized`; Naestra and Arahan's wood-elf realm; filed by state geography (#6373) |

### 01 KISLEV (gospodar, ungol) — 10 tags; KIS formable

3 cities + Ungol/Gospodar peoples are solid; Troll Country, Dolgan, Roppsmenn, Bolgasgrad, Volksgrad
are medium-confidence (wiki-aggregated). Density lever: many more RPG-sourcebook villages exist if
oblast depth is wanted. United Kislev (KIS) carries both founding cultures. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| KIS | `01_kislev` | Kislev (Tzardom) | formable | `gospodar`, `ungol` | Kislev (The Dobryrion) | United Kislev — both founding peoples |
| KSV | `01_kislev` | Kislev | start | `gospodar` | Kislev | the capital oblast, Tzarina's seat |
| ERE | `01_kislev` | Erengrad | start | `gospodar`, `ungol` | Erengrad | western port city, gospodar-founded amid Ungol lands |
| PRA | `01_kislev` | Praag | start | `gospodar` | Praag | northern frontier city |
| UNG | `01_kislev` | Ungol Horse-Tribes | start | `ungol` | Ungol Steppes (non-canon) | nomadic steppe Ungols |
| TRO | `01_kislev` | Troll Country | start | `ungol` | Troll Country | far-NW frontier oblast |
| BOL | `01_kislev` | Bolgasgrad | start | `gospodar` | Bolgasgrad (Eastern Oblast, PRA-held) | northern oblast town |
| VOL | `01_kislev` | Volksgrad | start | `gospodar` | Volksgrad (Eastern Oblast, PRA-held) | oblast town |
| DOL | `01_kislev` | Dolgan | start | `ungol` | The Golinyi (non-canon) | old eastern horse-tribe |
| ROP | `01_kislev` | Roppsmenn | start | `ungol` | Kislev Foothills (non-canon) | old northern tribe |

### 02 EMPIRE (per province culture, wood_elf) — 24 tags; EMP + VEM formable

10 Electoral provinces + Solland + The Moot + Sylvania + Marienburg (the seceded Wasteland). Sylvania
split into a human tag (`SYL`) and a Vampire tag (`VSY`, von Carstein) per Chris. Marienburg (`MAR`)
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
type like its parent VSY. Reikland, Middenland and Wissenland are `grand_principality`; the other
seven Electors, Marienburg and Solland are `principality` (Chris, 2026-09-04); Sylvania (human) stays
`grand_principality`; Sylvania (Vampire) is `kingdom` (Chris, 2026-09-04); the Moot is `principality`
and `unrecognized` (not a recognized Electorate).

**`BRK` Brass Keep** — registry-only for now (manual audit, 2026-09-03), like the Eastern Steppes
Chaos tags: a Nurgle-held fortress in the Middle Mountains (Hochland/Middenland/Ostland border),
captured in the Great War against Chaos (2302 IC per *Warhammer: The Old World*/Lexicanum) and
never retaken; the Empire contains rather than besieges it via "the Picket." Defined by #6373
(2026-10-01, Chris) with **`norscan` as a disclosed stand-in culture** for its Chaos-worshipping
garrison — no Chaos-marauder/cultist culture is authored anywhere in `common/cultures/` yet (possibly
a culture shared with the Eastern Steppes marauders, a later decision); `unrecognized`/`principality`.

**#6373 additions (2026-10-01):** `CRB` Carroburg, the Middenland free city on the Reik
(`recognized`/`city_state`), and the Skaven placeholders `XSA`, `XSB`, `XSC` (see *Conventions*).
Phase B added two wood-elf realms filed here by the geography of their states: `GRW` Gryphon Wood
(provisional name) and `LAU` Laurelorn (see the wood-elves convention).

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
| VSY | `02_empire` | House von Carstein | start | `sylvanian_vampire` | Drakenhof | von Carstein undead start |
| VEM | `02_empire` | The Von Carstein Empire | formable | `sylvanian_vampire` | Altdorf | VSY conquers the whole Empire; name TODO |
| MAR | `02_empire` | Marienburg (the Wasteland) | start | `marienburger` | Marienburg | seceded province Westerland; mercantile city-state |
| BRK | `02_empire` | Brass Keep | start | `norscan` | Brass Keep | Nurgle-held fortress, Middle Mountains; captured 2302 IC, never retaken; contained by the Empire's "the Picket"; `norscan` is a disclosed stand-in culture (#6373) |
| CRB | `02_empire` | Carroburg | start | `middenlander` | Carroburg | `recognized`/`city_state`; Middenland free city on the Reik (#6373) |
| XSA | `02_empire` | Skaven Clan A (placeholder) | start | `goblin` | — | Skaven placeholder; see *Conventions* (#6373) |
| XSB | `02_empire` | Skaven Clan B (placeholder) | start | `goblin` | — | Skaven placeholder; see *Conventions* (#6373) |
| XSC | `02_empire` | Skaven Clan C (placeholder) | start | `goblin` | — | Skaven placeholder (West Talabecland); see *Conventions* (#6373) |
| GRW | `02_empire` | Gryphon Wood | start | `wood_elf` | Gryphon Wood | `principality`/`unrecognized`; wood-elf enclave; name provisional, Chris to redo (#6373) |
| LAU | `02_empire` | Laurelorn | start | `wood_elf` | Laurelorn | `principality`/`unrecognized`; elven enclave of the Laurelorn Forest (#6373) |

### 03 BRETTONIA (bretonnian, mousillon, wood_elf) — 23 tags; BRE formable

The 14 dukedoms are confirmed complete canon — no 15th, and Mousillon is one of the 14 (the cursed
dukedom, no ruling Duke). At honest ceiling (no density lever). BRE formable is `bretonnian` only —
Mousillon's cursed culture is excluded, parallel to EMP excluding the vampire culture. (Approved
2026-08-30.)

**`MOR` Massif Orcal** added on manual audit (2026-09-03) — not a dukedom, a remnant Orc & Goblin
holdout in the Bretonnian heartland above the Forest of Chalons, never fully cleared when the
kingdom was founded. Lives here rather than in `06_badlands` because `common/country_definitions/`
files are organized by geography, not culture (see that region's entry); its `mountain_orc`/`goblin`
culture ids are a cross-file reference to `common/cultures/greenskin.txt`, the mod's only
Greenskin cultures. Named by location rather than tribe — a flagged exception to this mod's
tribal-society naming convention — because no well-attested tribe/warlord name exists for it;
checked tabletop, *Warhammer: The Old World* Lexicanum, and Total War, and rejected a fan site's
"Evil Sunz Tribe" claim as unreliable (not in any GW/wiki source, and suspiciously duplicates a
40K Ork klan name). Revisit if a real name ever surfaces.

**`SKZ` Skullsmasherz** moved here from `06_badlands` on manual audit (2026-09-03) — Ugrok
Craktoof's orc tribe, holding the Grey Mountains on Bretonnia's southern flank. Reclassified as
Bretonnian geography (the border range itself, not Badlands territory beyond it), same
geography-not-culture filing principle as `MOR` above; `mountain_orc` culture id is a cross-file reference
to `common/cultures/greenskin.txt`.

**Athel Loren (#6373 phase B, 2026-10-01).** The wood-elf realms of Athel Loren — `ANM` Anmyr, `ARG`
Argwylon, `TLS` Talsyn, `TRG` Torgovann, `WYD` Wydrioth — and the `OKP` Oak of Prophecy glade are filed
here by the geography of their states (Athel Loren sits in Bretonnia's state file); the wood elves have
no region file of their own (see *Conventions*). All carry `wood_elf` and are
`unrecognized`/`principality`. Names approved by Chris (2026-10-01).

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
| MOR | `03_brettonia` | Massif Orcal | start | `mountain_orc`, `goblin` | Massif Orcal | remnant Greenskin holdout, Bretonnian heartland; named by location, no tribe attested — TODO revisit |
| SKZ | `03_brettonia` | Skullsmasherz | start | `mountain_orc` | Pale Sisters (non-canon) | Ugrok Craktoof; Grey Mtns, Bretonnia's southern flank |
| ANM | `03_brettonia` | Anmyr | start | `wood_elf` | Anmyr | `principality`/`unrecognized`; realm of Athel Loren (#6373) |
| ARG | `03_brettonia` | Argwylon | start | `wood_elf` | Argwylon | `principality`/`unrecognized`; realm of Athel Loren (Durthu's, TW:W) (#6373) |
| TLS | `03_brettonia` | Talsyn | start | `wood_elf` | Talsyn | `principality`/`unrecognized`; realm of Athel Loren (Orion's, TW:W) (#6373) |
| TRG | `03_brettonia` | Torgovann | start | `wood_elf` | Torgovann | `principality`/`unrecognized`; realm of Athel Loren (#6373) |
| WYD | `03_brettonia` | Wydrioth | start | `wood_elf` | Wydrioth | `principality`/`unrecognized`; realm of Athel Loren (#6373) |
| OKP | `03_brettonia` | Oak of Prophecy | start | `wood_elf` | Oak of Prophecy | `principality`/`unrecognized`; wood-elf glade beyond Athel Loren's eaves (#6373) |

### 04 KARAZ ANKOR (dawi, dawi_grey, dawi_norse, dawi_ancestral, sylvanian_vampire, goblin) — 28 tags; KAZ formable

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

**#6373 additions (2026-10-01)** — tags painted on the start-ownership map. Four holds, all
`recognized`/`principality`: `KIZ` Karak Izor (the Copper Mountain), `KZF` Karak Ziflin (above Axe Bite
Pass), and the Norse dwarf holds `KOR` Kraka Ornsmotek and `KRV` Kraka Ravnsvake (filed here on the
`KRD` precedent although their states sit in Norsca's state file). **`VMP` is Heinrich Kemmler the
Lichemaster** (Chris, 2026-10-01) — a human necromancer turned lich, not a vampire; "Kemmler's Host" is
a disclosed name choice (canon names no realm for him), and `sylvanian_vampire` is a disclosed stand-in
culture (the only one with undead heritage and the `cult_of_nagash` religion; it does not describe a
non-vampire, non-Sylvanian following). `unrecognized`/`principality`, filed here by the geography of
Eastern Irranas. Plus the Skaven placeholders `XSH`–`XSL` (see *Conventions*).

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
| DRZ | `04_karaz_ankor` | Karak Drazh | start | `dawi_ancestral` | Karak Drazh / Black Crag (West Death Pass) | ruined -469 IC (Orc occupier "Black Crag" is a separate 06 tag) |
| KIZ | `04_karaz_ankor` | Karak Izor | start | `dawi` | Karak Izor | the Copper Mountain (#6373) |
| KZF | `04_karaz_ankor` | Karak Ziflin | start | `dawi_grey` | Karak Ziflin | Grey Mountains, above Axe Bite Pass (#6373) |
| KOR | `04_karaz_ankor` | Kraka Ornsmotek | start | `dawi_norse` | Kraka Ornsmotek | Norse dwarf hold; state in Norsca, filed here on the KRD precedent (#6373) |
| KRV | `04_karaz_ankor` | Kraka Ravnsvake | start | `dawi_norse` | Kraka Ravnsvake | Norse dwarf hold; state in Norsca, filed here on the KRD precedent (#6373) |
| VMP | `04_karaz_ankor` | Kemmler's Host | start | `sylvanian_vampire` | Eastern Irranas (non-canon) | Heinrich Kemmler the Lichemaster (human lich); `unrecognized`; name and culture are disclosed stand-ins (#6373) |
| LHX | `04_karaz_ankor` | Lahmian Exiles | start | `lahmian_vampire` | New Lahmia | Lahmian vampire exiles in STATE_NEW_LAHMIA; `unrecognized`; new tag distinct from `LAH` (Chris, 2026-10-03) |
| XSH | `04_karaz_ankor` | Skaven Clan F (placeholder) | start | `goblin` | Shattered Teeth (non-canon) | Skaven placeholder; see *Conventions* (#6373) |
| XSI | `04_karaz_ankor` | Skaven Clan G (placeholder) | start | `goblin` | Kreutzhofen (non-canon) | Skaven placeholder; see *Conventions* (#6373) |
| XSJ | `04_karaz_ankor` | Skaven Clan H (placeholder) | start | `goblin` | Aquilena (non-canon) | Skaven placeholder; see *Conventions* (#6373) |
| XSK | `04_karaz_ankor` | Skaven Clan I (placeholder) | start | `goblin` | Dark Maiden Pass (non-canon) | Skaven placeholder (Dark Maiden Pass); see *Conventions* (#6373) |
| XSL | `04_karaz_ankor` | Skaven Clan J (placeholder) | start | `goblin` | Cripple Peak (non-canon) | Skaven placeholder (Cripple Peak); see *Conventions* (#6373) |
| VLG | `04_karaz_ankor` | Karak Vlag | start | `dawi` | Karak Vlag | ruined, far north, destroyed by Chaos |
| SLV | `04_karaz_ankor` | Mount Silverspear | start | `dawi` | Mount Silverspear | ruined mine, Silver Road |

### 05 SOUTHERN REALMS (tilean, estalian, sartosan, border_princer, gospodar, ungol, sylvanian_vampire, goblin, wood_elf) — 29 tags; TIL/EST/USR formables

8 Tilean city-states + 3 Estalian kingdoms + one Border Princes tag. Tilea/Estalia held at their
well-known city-states (approved as-is by Chris — the deep Tilean/Estalian/Border-Prince supply lever
left untaken). **Sartosa (`SRT`) gets its own bespoke `sartosan` culture** — a melting-pot Tilean-
pirate people modeled on vanilla's Maltese (culture authored by #3419; the Total War "vampire-pirate
Sartosa" is not tabletop canon, so Sartosa stays a human pirate haven). **One Border Princes tag
(`BPR`)** — its canonical decentralization is intended to be represented by a government/law variant, a
later `common/` authoring task (out of scope for this docs-only registry). TIL (united Tilea) carries
both `tilean` and `sartosan`. (Approved 2026-08-30.)

**`USR` United Southern Realms** added on manual audit (2026-09-04, Chris) — a third, region-wide
formable above TIL/EST, `empire` tier, `recognized`, carrying all four regional cultures
(`tilean`, `sartosan`, `estalian`, `border_princer`) so any of the region's peoples can lead the
unification. Same pass: BIL and MAG raised to `grand_principality`, CNT set to `principality`
(previously all three were `kingdom`, level with EST's own formable); BPR changed from
`decentralized`/`principality` to `recognized`/`kingdom`.

**Border Princes belt deepened — 11 named realms added** (2026-09-06, Chris) from
`sources/originals/old_world_z10.png`, which Chris approved as the name source for this
expansion — the registry's original single `BPR` tag deliberately left the Border-Prince
supply lever untaken, and this takes it. Each individually-shielded realm on that map is a
startable principality. Cultures are matched to heraldry, not forced uniform: eight ordinary
Border Princes carry `border_princer` (`recognized`/`principality` — a step below BPR's
belt-wide `kingdom`); `UVE` Uvetovsk carries the Kislevite `gospodar`/`ungol` (white-bear
heraldry, the canonical Kislevite-founded border state); `HKN` Harkon and `PON` Pontenne carry
`sylvanian_vampire` (`unrecognized`, parallel to `VSY` — blood-chalice heraldry). The three
outlier cultures are cross-file references (to `kislevite_humans.txt` and `vampire.txt`), the
same geography-not-culture filing `MOR`/`SKZ` use. No new formable — these are start fragments
under the existing `USR`/`TIL` unifiers.

**Donalba (`DON`) added** (2026-09-06, Chris) — an eighth `tilean`-culture city-state, read off the
same z10 map on a follow-up pass over the Tilean roster: the eastern Tilean frontier city on the
Lissa Road below Aegis Castle (gold-sun-on-purple arms). It was the only shielded Tilean realm the
map showed that wasn't already tagged — the map's other Tilean shields all matched existing tags
(the green Trantine-Hills shield is Trantio's own arms, `TRA`, not a separate realm). Its purple
color is deliberately off the Tilean ochre/terracotta/sea-green family, matching its own heraldry
(as `SRT` is off-palette). Two kite shields on the Black Peninsula (near Tor Anrok
and Monte Castello) were left untagged — High Elf colonies (Chris, 2026-09-06), deferred to the
future Ulthuan / elven-colonies pass (region 17), not Tilean city-states.

**`MGL` Miramar Glade** (#6373 phase B, 2026-10-01) — a wood-elf glade in the Miramar Hills, filed
here by the geography of its state; the name is provisional (Chris will redo it). See the wood-elves
convention.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| USR | `05_southern_realms` | United Southern Realms | formable | `tilean`, `sartosan`, `estalian`, `border_princer` | — | region-wide unification above TIL/EST |
| TIL | `05_southern_realms` | Tilea | formable | `tilean`, `sartosan` | Miragliano | the city-states unite (incl. Sartosa) |
| MIR | `05_southern_realms` | Miragliano | start | `tilean` | Miragliano |  |
| LUC | `05_southern_realms` | Luccini | start | `tilean` | Luccini |  |
| REM | `05_southern_realms` | Remas | start | `tilean` | Remas |  |
| TOB | `05_southern_realms` | Tobaro | start | `tilean` | Tobaro |  |
| TRA | `05_southern_realms` | Trantio | start | `tilean` | Trantio |  |
| PAV | `05_southern_realms` | Pavona | start | `tilean` | Pavona |  |
| VER | `05_southern_realms` | Verezzo | start | `tilean` | Verezzo |  |
| DON | `05_southern_realms` | Donalba | start | `tilean` | Donalba | Tilean frontier city-state on the Lissa Road, below Aegis Castle (z10 map) |
| SRT | `05_southern_realms` | Sartosa | start | `sartosan` | Sartosa | pirate haven; melting-pot culture |
| EST | `05_southern_realms` | Estalia | formable | `estalian` | Magritta | the kingdoms unite |
| BIL | `05_southern_realms` | Bilbali | start | `estalian` | Bilbali |  |
| MAG | `05_southern_realms` | Magritta | start | `estalian` | Magritta |  |
| CNT | `05_southern_realms` | Cantonia | start | `estalian` | Western Estalian Coast (non-canon) | minor Estalian kingdom |
| BPR | `05_southern_realms` | Border Princes | start | `border_princer` | Kharnos Forest (non-canon) | loose principalities; decentralization → a later law/government-type variant |
| ORT | `05_southern_realms` | Ortegeta | start | `border_princer` | Ortegeta | castled realm above Ghoulstone Keep (z10 map) |
| GAS | `05_southern_realms` | Gastonne | start | `border_princer` | Gastonne | griffon-banner realm on the Tara Dante |
| GDO | `05_southern_realms` | Gordorno | start | `border_princer` | Gordorno (Aquilena, AQL-held) | fleur-de-lis realm by the Citadel of Gazul |
| MON | `05_southern_realms` | Monteaux | start | `border_princer` | Monteaux (Gastonne, GAS-held) | towered realm on the Black Gulf coast |
| AQL | `05_southern_realms` | Aquilena | start | `border_princer` | Aquilena | serpent realm on the River Orco |
| DUN | `05_southern_realms` | Dunkelmund | start | `border_princer` | Dunkelmund (Varenka Hills, BVR-held) | double-eagle realm near High Spear |
| ESS | `05_southern_realms` | Esselhafen | start | `border_princer` | Esselhafen | chevron-banner realm on the River Stecnek |
| RAA | `05_southern_realms` | Raachwald | start | `border_princer` | Raachwald | serpent-and-diamond realm by Reavers Keep |
| UVE | `05_southern_realms` | Uvetovsk | start | `gospodar`, `ungol` | Uvetovsk | Kislevite-founded bear realm, Old Silk Road; cross-file culture ref |
| HKN | `05_southern_realms` | Harkon | start | `sylvanian_vampire` | — (Harkon has no hub; owns nothing) | `unrecognized`; undead chalice realm, Forest of Gloom; cross-file culture ref |
| PON | `05_southern_realms` | Pontenne | start | `sylvanian_vampire` | — (Pontenne has no hub; owns nothing) | `unrecognized`; undead chalice realm by the Chateau de Morsuil; cross-file culture ref |
| XSG | `05_southern_realms` | Skaven Clan E (placeholder) | start | `goblin` | Blighted Marshes (non-canon) | Skaven placeholder (Blighted Marshes); see *Conventions* (#6373) |
| MGL | `05_southern_realms` | Miramar Glade | start | `wood_elf` | Nuja (non-canon, MGL slice) | `principality`/`unrecognized`; wood-elf glade, Miramar Hills; name provisional, Chris to redo (#6373) |

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
entry for both tags' full writeup. Both still use `mountain_orc`/`goblin` culture ids from
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
| RED | `06_badlands` | Red Eye | start | `mountain_orc` | Red Eye | Grimgor Ironhide's 'Ardboyz; ex-Karak Ungor |
| CRM | `06_badlands` | Crooked Moon | start | `goblin` | Karak Eight Peaks | Skarsnik's Night Goblins; Karak Eight Peaks |
| BKA | `06_badlands` | Broken Axe | start | `goblin` | Misty Mountain (Sour Crags) | Grom the Paunch (Goblin); Misty Mountain |
| RFG | `06_badlands` | Red Fangs | start | `mountain_orc` | Black Crag | Gorfang Rotgut; holds Black Crag (ex-Karak Drazh) |
| ICL | `06_badlands` | Ironclaw | start | `mountain_orc` | Iron Rock | Gorbad Ironclaw; holds Iron Rock (N. Badlands) |
| BSB | `06_badlands` | Bloody Sunz | start | `mountain_orc` | Blightwater (non-canon) | Grumlok & Gazbag; Badlands orc tribe |
| BNR | `06_badlands` | Bonerattlaz | start | `mountain_orc` | Northern World's Edge (non-canon) | Azhag the Slaughterer; N. World's Edge |
| BTO | `06_badlands` | Broken Tooth | start | `mountain_orc` | The Cauldron (non-canon) | Crusher Zogoth; pre-Gorbad Iron Rock (historical) |
| BRN | `06_badlands` | Broken Nose | start | `goblin` | Novalone Pass (non-canon) | Goblin tribe of the Vaults |
| BLV | `06_badlands` | Black Venom | start | `goblin` | West Middenland (non-canon, BLV slice) | Forest Goblin tribe, S. of Black Fire Pass |
| RDV | `06_badlands` | Redvenom | start | `goblin` | Marshes of Madness (non-canon) | Snagla Grobspit's Forest Goblins |
| STR | `06_badlands` | Strigoi Remnants | start | `sylvanian_vampire` | Old Strygos | Strigoi remnant in STATE_OLD_STRYGOS; `unrecognized`; culture is a disclosed stand-in, no Strigoi culture authored (Chris, 2026-10-03) |

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

### 10 DARK LANDS (dawi_zharr, hobgoblin, orc) — 7 tags; ZHA + KHN formables

The Chaos Dwarfs (Dawi Zharr) and their hobgoblin vassals. Canon-thin beyond Zharr-Naggrund; held at 6
(Chris approved as-is). Two formables — Chaos Dwarfs and hobgoblins are distinct peoples with separate
unifiers. (Approved 2026-08-30. Closes the Old World tranche.) **`DLO` Dark Land Orcs** (a TW:W
Greenskins faction, reserved here at approval) was added by #6373 (2026-10-01) once the painted
start map gave it states: `mountain_orc` culture, `unrecognized`/`principality`.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| ZHA | `10_dark_lands` | Dawi Zharr Empire | formable | `dawi_zharr` | Zharr-Naggrund | the Chaos Dwarf empire |
| MZN | `10_dark_lands` | Mingol Zharr-Naggrund | start | `dawi_zharr` | Zharr-Naggrund | the Tower of Zharr (capital) |
| GOR | `10_dark_lands` | Gorgoth | start | `dawi_zharr` | Gorgoth | Chaos Dwarf hold |
| UZK | `10_dark_lands` | Uzkulak | start | `dawi_zharr` | Uzkulak | Port of Zharr |
| KHN | `10_dark_lands` | Great Khanate | formable | `hobgoblin` | — | Hobgobla-Khan unites the hobgoblins |
| HGK | `10_dark_lands` | Hobgobla-Khan | start | `hobgoblin` | — | the great hobgoblin realm |
| DLO | `10_dark_lands` | Dark Land Orcs | start | `mountain_orc` | Causeway of Zharr (non-canon) | greenskin tribes of the Dark Lands; TW:W faction (#6373) |

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

### 11 OGRE KINGDOMS (ogre) — 12 tags; no formable

Ogre tribes of the Mountains of Mourn. Names blend tabletop + Total War: Warhammer (Chris approved TW as
a source here, as with the greenskins). **No formable** (Chris dropped OGR). Ogres are semi-nomadic with
**no named capital** in canon (the Great Maw crater is the spiritual center) — placeholder capitals stay
blank. (Approved 2026-08-30.)

**#6373 phase B (2026-10-01):** every row now carries the `ogre` culture (#6379). `IRN`, `MAW`, `EYB`
and `THG` own states on the painted start map and are defined in `11_ogre_kingdoms`
(`unrecognized`/`principality`). They deliberately follow this region column, not the geography of
their states (IRN's sits in Karaz Ankor's state file, the other three in the Dark Lands'), as `KRD`
and the Norse dwarf holds do in `04_karaz_ankor`. The other eight rows stay loc-only until given
states.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| GGT | `11_ogre_kingdoms` | Goldtooth | start | `ogre` | — | Greasus Goldtooth (Overtyrant) |
| IRN | `11_ogre_kingdoms` | Ironskin | start | `ogre` | — | Ghark Ironskin |
| GLG | `11_ogre_kingdoms` | Golgfag's Maneaters | start | `ogre` | — | Golgfag Maneater (mercenaries) |
| MAW | `11_ogre_kingdoms` | Disciples of the Maw | start | `ogre` | — | Skrag the Slaughterer |
| BGZ | `11_ogre_kingdoms` | Blood Guzzlers | start | `ogre` | — | Bul Mallet-hands; Vale of Webs |
| EYB | `11_ogre_kingdoms` | Eyebiter | start | `ogre` | — | Malron Eyebiter |
| RSK | `11_ogre_kingdoms` | Rock Skulls | start | `ogre` | — | break boulders with their heads |
| CXC | `11_ogre_kingdoms` | Crossed Clubs | start | `ogre` | — | roaming braggart Maneaters |
| AGF | `11_ogre_kingdoms` | Angry Fist | start | `ogre` | — | most "advanced" tribe; assailed Karak Azorn |
| THG | `11_ogre_kingdoms` | Thunderguts | start | `ogre` | — | named tribe |
| FSM | `11_ogre_kingdoms` | Feastmaster | start | `ogre` | — | TW:W minor faction |
| SOM | `11_ogre_kingdoms` | Sons of the Mountain | start | `ogre` | — | TW:W minor faction |

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

### 19 LUSTRIA (Lizardmen, PLACEHOLDER + norscan) — 19 tags; LUS formable

The temple-cities of the Lizardmen, at max density (Chris approved TW:W as a name source, as with the
greenskins/Cathay). LUS is the Slann reuniting the Old Ones' dominion. All Lizardmen rows are
**Lustrian** — Southlands Lizardmen (Zlatlan; the TW factions Kroq-Gar/Tiktaq'to) are excluded from
this file per Chris and live in 09 Southlands. Sourced corrections: "Spektotl"→Spektazuma; "Zaqua"
unverified (dropped); Tlanxla and "Tlanxa" are one city (TLN), Tlax is separate (TLA). Sentinels of
Xeti and 8 lower-detail cities held as reserve. All Lizardmen rows PLACEHOLDER culture. (Approved
2026-08-30.)

**`SKG` Skeggi** added on a lore-audit pass (2026-09-04, Chris) — the Norscan colony in Lustria
founded 888 IC by Losteriksson of the Bjornlings, who named it for his daughter, the first child
born there (White Dwarf 309, "The Norse of Lustria"). Unlike the Lizardmen rows, it takes the real
`norscan` culture (already authored, #3404) rather than `PLACEHOLDER` — the same precedent as 08
Araby's Bretonnian crusader tags (`ORG`/`ANT`) carrying a real culture inside an otherwise-placeholder
region. `principality` tier, `unrecognized` type (a colony, not a recognized Lustrian power) —
matches the tier/type given to Norsca's own new lesser-tribe tags the same pass (Chris, 2026-09-04).

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| LUS | `19_lustria` | Lustria | formable | `PLACEHOLDER` | Itza | the Old Ones' dominion united |
| SKG | `19_lustria` | Skeggi | start | `norscan` | Skeggi | `principality`/`unrecognized`; Norscan colony, founded 888 IC by Losteriksson of the Bjornlings |
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

### 98 UNCLAIMED (goblin stand-in) — 1 tag; no formable

Not a region and not a nation: the placeholder owner of land nobody holds at the start date (see
*Conventions*, board #6391, Chris 2026-10-02). Generator-mapped from the `unowned` and `placeholder`
owner tokens of `mapgen/derived/state_ownership.json`, never painted.

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| UNO | `98_unclaimed` | Unclaimed Lands (placeholder) | start | `goblin` | — | `decentralized`/`principality`; owns every unowned and out-of-scope state; `goblin` is a disclosed stand-in that does not describe the peoples of the land; no capital, no homelands; never renamed into a real polity (#6391) |
