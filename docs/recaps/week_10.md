# Week 10 recap: S1 tracker

Official picks: 1 (0-1), -1.00 units. Written from the committed tracker files and nflverse. The split is descriptive: with this few picks it can suggest causes, not establish them, and nothing here changes rule S1.

How to read it: each result is compared with what the player usually does (usage baseline). 'Toward the pick' means the part moved the stat in the direction the pick needed (smaller for an under, larger for an over), in units of the stat. Efficiency (catch or completion rate) is the part closest to luck.

| Pick | Result | Actual vs line | Model | Usage baseline | Volume | Role | Efficiency | Largest part |
|---|---|---|---|---|---|---|---|---|
| Xavier Hutchinson receptions under 3.5 | L | 4 vs 3.5 | 2.8 | 3.2 | -0.24 | -1.48 | +0.96 | role |

## Across the week

Average part per pick, relative to the line (toward-the-pick is +):

| Group | Picks | Volume | Role | Efficiency | Model minus baseline |
|---|---|---|---|---|---|
| Lost | 1 | -0.07 | -0.42 | +0.27 | +0.14 |
| All | 1 | -0.07 | -0.42 | +0.27 | +0.14 |

Largest part by pick: role 1.
'Model minus baseline' is how far the model's projection sat from the usage baseline, toward the pick: a positive number means the model was leaning into the pick more than the player's own recent usage did.

## Picks

### Xavier Hutchinson (): receptions under 3.5 at -166, L, actual 4

- Team pass attempts: usual 35.6, this week 38 (-0.24 toward the pick)
- Targets per team attempt: usual 0.158, this week 0.237 (-1.48)
- Catch rate: usual 0.58, this week 0.44 (+0.96)
- Line 3.5; model projected 2.8; usage baseline 3.2 (from 8 prior games); actual 4, +0.5 against the line
- Largest part: **role** (-1.48 toward the pick, in receptions) · decided by half a count or less
- Game: 
- Next Gen Stats: separation 2.73 yds (weeks 1-3: 2.57); cushion 5.37 yds (weeks 1-3: 5.85)

## Limits

- Baseline is the player's own games this season before the week (in games he played; padded with 2025 games when fewer than 2). Catch and completion rates are shrunk toward the league rate. A different baseline would move the split.
- Coverage numbers come from the newest hand-transcribed season-to-date table (`data/external/`), which includes this game when it runs through this week, and omit some coverage types.
- Not measured: man or zone coverage faced by this player, routes run, personnel, and anything in the game's film.
