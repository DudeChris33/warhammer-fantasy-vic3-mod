# Testing Rules

There is no compiler and no automated test suite for Clausewitz script — validation happens by loading the mod in Victoria 3 itself.

## Validation procedure

1. Launch Victoria 3 with this mod enabled.
2. Load into a game (main menu script parsing alone won't catch every error — get to a session if the change touches `events/` or `history/`).
3. Check `logs/error.log`, located one level above the game's `mod/` folder — i.e. `Documents/Paradox Interactive/Victoria 3/logs/error.log` (this mod folder is `Documents/Paradox Interactive/Victoria 3/mod/warhammer-fantasy/`).
4. Any new line referencing a file in this mod is a failure. Fix the **script**, not the log.

## Regression rule

When fixing a bug confirmed via `logs/error.log` or in-game behavior, first reproduce it (capture the exact error line or observed behavior) before changing script, so the fix can be verified against the same reproduction step afterward.

## Rules

- Never claim a change is "tested" without having loaded the mod in-game and checked `logs/error.log`.
- Never edit `logs/error.log` or any game-owned file to make an error disappear — fix the source in this mod.
