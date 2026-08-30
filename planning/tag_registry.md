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
- [x] 02 Empire (16)
- [x] 03 Bretonnia (15)
- [x] 04 Karaz Ankor (18)
- [x] 05 Southern Realms (14)
- [x] 06 Badlands (12)
- [x] 07 Nehekhara (11)
- [x] 10 Dark Lands (6)
- [x] 08 Araby (10)
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

**Approved so far: 122 tags** (10 formables, 112 starts) — Old World tranche complete; distant tranche
in progress. Content is **honest, well-attested Warhammer
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
AHK
ANT
AQU
ARB
ART
AVE
AZL
BAE
BAS
BEL
BHA
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
BRN
BSB
BTO
BVR
CAR
CNT
COP
COU
CRM
DOL
DRZ
EKR
ELK
EMP
ERE
EST
FYR
GIS
GOR
GRA
GUN
HAS
HGK
HOC
ICL
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
KNO
KRD
KSV
KUN
KVE
KVN
LAH
LAN
LSK
LUC
LYB
LYO
MAG
MAH
MID
MIR
MNF
MOO
MOU
MTK
MZN
NEH
NLD
NSC
NUM
ORG
OSM
OST
PAR
PAV
PRA
QUA
QUE
RAS
RDV
RED
REI
REM
RFG
ROP
SAR
SKA
SKZ
SLV
SOL
SRT
STI
SYL
TAL
TIL
TOB
TRA
TRO
UNG
UZK
VAR
VER
VLG
VOL
VSY
WAS
WIS
ZHA
ZHU
ZND
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

### 02 EMPIRE (per province culture) — 16 tags; EMP formable

10 Electoral provinces + Solland + The Moot + Sylvania + Marienburg (the seceded Wasteland). Sylvania
split into a human tag (`SYL`) and a Vampire tag (`VSY`, von Carstein) per Chris. Marienburg (`WAS`)
gets its own bespoke culture. Big density lever untaken: WFRP baronies/free-towns (Bergsburg,
Ubersreik, Bögenhafen…) could push this to 28–38, but they are RPG settlements, not well-attested
startable realms — held at honest depth. (Approved 2026-08-30.)

**`EMP` United Empire** carries all 12 human province cultures as its primary-culture set:
reiklander, middenlander, nordlander, hochlander, ostlander, ostermarker, talabeclander, stirlander,
averlander, wissenlander, sollander, sylvanian (human). **Excludes** halfling (the Moot),
sylvanian_vampire, and marienburger (Marienburg seceded — reintegration is a future journal event).

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
| WAS | `02_empire` | Marienburg (the Wasteland) | start | `marienburger` | Marienburg | seceded province Westerland; mercantile city-state |

### 03 BRETTONIA (bretonnian, mousillon) — 15 tags; BRE formable

The 14 dukedoms are confirmed complete canon — no 15th, and Mousillon is one of the 14 (the cursed
dukedom, no ruling Duke). At honest ceiling (no density lever). BRE formable is `bretonnian` only —
Mousillon's cursed culture is excluded, parallel to EMP excluding the vampire culture. (Approved
2026-08-30.)

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

### 04 KARAZ ANKOR (dawi, dawi_grey, dawi_norse, dawi_badlands) — 18 tags; KAZ formable

10 active holds + Karak Angazbar (seed "Karak Azgaraz" corrected) + 7 ruined/fallen holds (all
sourced). **Ruined holds keep a dwarf tag even though they are occupied at game start** — they are
releasable "reclaim" realms (per Chris). Their current greenskin/Skaven occupiers are *separate* tags:
the greenskin occupiers (Red Eye Mountain, Black Crag, etc.) are added in 06 Badlands; Skaven have no
region yet (under-empire, a future epic). KAZ (the reunited Everlasting Realm) carries **all four**
dwarf cultures. (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| KAZ | `04_karaz_ankor` | Karaz Ankor | formable | `dawi`, `dawi_grey`, `dawi_norse`, `dawi_badlands` | Karaz-a-Karak | the Everlasting Realm reunited (all dwarf cultures) |
| KAK | `04_karaz_ankor` | Karaz-a-Karak | start | `dawi` | Karaz-a-Karak | the High King's hold (Everpeak) |
| ZHU | `04_karaz_ankor` | Zhufbar | start | `dawi` | Zhufbar |  |
| KAD | `04_karaz_ankor` | Karak Kadrin | start | `dawi` | Karak Kadrin | Slayer Keep |
| AZL | `04_karaz_ankor` | Karak Azul | start | `dawi_badlands` | Karak Azul | southern hold |
| KEP | `04_karaz_ankor` | Karak Eight Peaks | start | `dawi_badlands` | Karak Eight Peaks | contested / reclamation |
| BVR | `04_karaz_ankor` | Barak Varr | start | `dawi` | Barak Varr | the sea-hold |
| KNO | `04_karaz_ankor` | Karak Norn | start | `dawi_grey` | Karak Norn | Grey Mountains |
| KHI | `04_karaz_ankor` | Karak Hirn | start | `dawi_grey` | Karak Hirn | Vaults / Grey Mountains |
| KRD | `04_karaz_ankor` | Kraka Drak | start | `dawi_norse` | Kraka Drak | Norse dwarf hold |
| KAG | `04_karaz_ankor` | Karak Angazbar | start | `dawi_badlands` | Karak Angazbar | Black Mountains ("Irongate"); seed name corrected |
| KUN | `04_karaz_ankor` | Karak Ungor | start | `dawi` | Karak Ungor | ruined (occupier "Red Eye Mountain" is a separate 06 tag) |
| KVN | `04_karaz_ankor` | Karak Varn | start | `dawi` | Karak Varn | ruined, flooded (Skaven/Night Goblin occupier separate) |
| EKR | `04_karaz_ankor` | Ekrund | start | `dawi_badlands` | Ekrund | ruined, Black Gulf mines (Orc occupier separate) |
| GUN | `04_karaz_ankor` | Mount Gunbad | start | `dawi` | Mount Gunbad | ruined, brightstone mines (Night Goblin occupier separate) |
| DRZ | `04_karaz_ankor` | Karak Drazh | start | `dawi_badlands` | Karak Drazh | ruined -469 IC (Orc occupier "Black Crag" is a separate 06 tag) |
| VLG | `04_karaz_ankor` | Karak Vlag | start | `dawi` | Karak Vlag | ruined, far north, destroyed by Chaos |
| SLV | `04_karaz_ankor` | Mount Silverspear | start | `dawi` | Mount Silverspear | ruined mine, Silver Road |

### 05 SOUTHERN REALMS (tilean, estalian, sartosan, border_princer) — 14 tags; TIL/EST formables

8 Tilean city-states + 3 Estalian kingdoms + one Border Princes tag. Tilea/Estalia held at their
well-known city-states (approved as-is by Chris — the deep Tilean/Estalian/Border-Prince supply lever
left untaken). **Sartosa (`SRT`) gets its own bespoke `sartosan` culture** — a melting-pot Tilean-
pirate people modeled on vanilla's Maltese (culture **pending #3404**; the Total War "vampire-pirate
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
| SRT | `05_southern_realms` | Sartosa | start | `sartosan` | Sartosa | pirate haven; melting-pot culture — **pending #3404** |
| EST | `05_southern_realms` | Estalia | formable | `estalian` | Magritta | the kingdoms unite |
| BIL | `05_southern_realms` | Bilbali | start | `estalian` | Bilbali |  |
| MAG | `05_southern_realms` | Magritta | start | `estalian` | Magritta |  |
| CNT | `05_southern_realms` | Cantonia | start | `estalian` | Cantonia | minor Estalian kingdom |
| BPR | `05_southern_realms` | Border Princes | start | `border_princer` | — | loose principalities; decentralization → a later law/government-type variant |

### 06 BADLANDS (orc, goblin) — 12 tags; no formable

Greenskin tribes/strongholds of the Badlands / World's Edge. **Chris approved Total War: Warhammer as a
name source for this region** (in addition to tabletop), so names blend both. Deduplicated so no polity
is double-tagged by tribe *and* stronghold (Red Fangs = Black Crag; Ironclaw = Iron Rock; Crooked Moon =
Karak Eight Peaks; Grimgor's Red Eye = ex-Karak Ungor). **No WAAAGH! formable** (Chris dropped it).
Savage Orcs are handled in 09 Southlands (their canon heartland) with a new `savage_orc` culture — see
that region. (Approved 2026-08-30.)

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
| SKZ | `06_badlands` | Skullsmasherz | start | `orc` | — | Ugrok Craktoof; Grey Mtns / Bretonnia border |

**Density reserve (not yet allocated — add later if Chris wants a denser Badlands).** Confirmed TW:W
Greenskins faction names, race/location wiki-unstated (would be representative orc/goblin tribes):
Bloody Spearz · Scabby Eye · Necksnappers · Deff Grindaz · Drippin Fangs · Dimmed Sunz · Moon Howlerz ·
Da Mad Howlerz · Creeping Death · Red Cloud · Blue Vipers · Teef Snatchaz · Da Cage Breakaz · Broken
Chainz (14 available). "Dark Land Orcs" belongs to 10 Dark Lands; Karak Varn's Skaven occupiers await a
future under-empire epic (no region yet).

### 07 NEHEKHARA (nehekharan, lahmian_vampire) — 11 tags; NEH formable

The tomb-cities of the Tomb Kings. **Lahmia (`LAH`) carries a bespoke `lahmian_vampire` culture** —
Neferata's bloodline, the cradle of vampires (culture **pending #3404**). All other cities are
`nehekharan` (the ancient Tomb Kings civilization). NEH (Settra reunites the Land of the Dead) is
`nehekharan` only — the Lahmian vampires are Settra's enemies, not part of his realm. **Nagashizzar has
no tag** — reserved for a future Skaven clan (no Skaven region yet). (Approved 2026-08-30.)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| NEH | `07_nehekhara` | Nehekhara | formable | `nehekharan` | Khemri | Settra reunites the Land of the Dead |
| KHM | `07_nehekhara` | Khemri | start | `nehekharan` | Khemri | Settra's city (the capital) |
| ZND | `07_nehekhara` | Zandri | start | `nehekharan` | Zandri |  |
| NUM | `07_nehekhara` | Numas | start | `nehekharan` | Numas |  |
| LAH | `07_nehekhara` | Lahmia | start | `lahmian_vampire` | Lahmia | cradle of vampires (Neferata) — **culture pending #3404** |
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
