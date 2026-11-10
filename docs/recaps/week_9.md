# Week 9 recap: S1 tracker

Official picks: 1 (1-0), +0.69 units. Written from the committed tracker files and nflverse. The split is descriptive: with this few picks it can suggest causes, not establish them, and nothing here changes rule S1.

How to read it: each result is compared with what the player usually does (usage baseline). 'Toward the pick' means the part moved the stat in the direction the pick needed (smaller for an under, larger for an over), in units of the stat. Efficiency (catch or completion rate) is the part closest to luck.

| Pick | Result | Actual vs line | Model | Usage baseline | Volume | Role | Efficiency | Largest part |
|---|---|---|---|---|---|---|---|---|
| George Kittle receptions under 6.5 | W | 4 vs 6.5 | 5.4 | 4.7 | +0.82 | -1.11 | +1.01 | role |

## Across the week

Average part per pick, relative to the line (toward-the-pick is +):

| Group | Picks | Volume | Role | Efficiency | Model minus baseline |
|---|---|---|---|---|---|
| Won | 1 | +0.13 | -0.17 | +0.16 | -0.10 |
| All | 1 | +0.13 | -0.17 | +0.16 | -0.10 |

Largest part by pick: role 1.
'Model minus baseline' is how far the model's projection sat from the usage baseline, toward the pick: a positive number means the model was leaning into the pick more than the player's own recent usage did.

## Picks

### George Kittle (): receptions under 6.5 at -145, W, actual 4

- Team pass attempts: usual 30.1, this week 25 (+0.82 toward the pick)
- Targets per team attempt: usual 0.218, this week 0.280 (-1.11)
- Catch rate: usual 0.72, this week 0.57 (+1.01)
- Line 6.5; model projected 5.4; usage baseline 4.7 (from 7 prior games); actual 4, -2.5 against the line
- Largest part: **role** (-1.11 toward the pick, in receptions)
- Game: 
- Next Gen Stats: separation 4.51 yds (weeks 1-3: 3.04); cushion 5.08 yds (weeks 1-3: 5.50)

## Limits

- Baseline is the player's own games this season before the week (in games he played; padded with 2025 games when fewer than 2). Catch and completion rates are shrunk toward the league rate. A different baseline would move the split.
- Coverage numbers come from a hand-transcribed weeks 1-4 table (`data/external/`), include this game, and omit some coverage types.
- Not measured: man or zone coverage faced by this player, routes run, personnel, and anything in the game's film.
