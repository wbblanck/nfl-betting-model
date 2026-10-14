> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Understanding Outcome IDs

> How outcomes are organized and identified in the Novig API

## Overview

When working with the Novig API, it's important to understand how outcomes are organized. The order of outcomes in an array does **not** determine their meaning—the `index` field does.

## The Index Field

Each outcome object contains an `index` field that identifies which side of the market it represents:

| Index | Meaning |
| - | - |
| `0` | **Home** / **Yes** side |
| `1` | **Away** / **No** side |

<Warning>
  Do not rely on array position to determine outcome meaning. Always use the `index` field.
</Warning>

## Example

Consider this response from the API:

```json theme={"dark"}
{
  "outcomeIds": [
    "14e8323b-b635-41ff-b7f6-f81477ee4153",
    "c84fa737-1ed7-4ed5-af47-39379c175fdd"
  ],
  "outcomes": [
    {
      "id": "14e8323b-b635-41ff-b7f6-f81477ee4153",
      "status": "TBD",
      "index": 1
    },
    {
      "id": "c84fa737-1ed7-4ed5-af47-39379c175fdd",
      "status": "TBD",
      "index": 0
    }
  ]
}
```

In this example:

* The **first** item in the `outcomes` array (`14e8323b-...`) has `index: 1`, making it the **Away/No** side
* The **second** item in the `outcomes` array (`c84fa737-...`) has `index: 0`, making it the **Home/Yes** side

<Tip>
  Always filter or find outcomes by their `index` field rather than assuming array order.
</Tip>

## Market Type Mapping

The meaning of `index: 0` depends on the market type:

| Market Type | Index 0 | Index 1 |
| - | - | - |
| `MONEY` | Home | Away |
| `SPREAD` | Home | Away |
| `TOTAL` | Over | Under |
| `TEAM_TOTAL` | Over | Under |
| `MONEYLINE_3_WAY_WIN` | Yes | No |
| `MONEYLINE_3_WAY_DRAW` | Yes | No |

<Note>
  For game-level markets (MONEY, SPREAD), index 0 always corresponds to the home team. For totals and player props, index 0 corresponds to the Over or Yes side.
</Note>

## Three-Way Moneylines

Some competitions that can end in a draw (e.g. soccer / the FIFA World Cup) use **`MONEYLINE_3_WAY_WIN`** markets. Unlike a standard two-sided moneyline, a three-way moneyline is **not** a single Home/Away market. Instead, each possible result is its own independent **Yes / No** market:

| Market Type | Question |
| - | - |
| `MONEYLINE_3_WAY_WIN` (home team) | Does the home team win? |
| `MONEYLINE_3_WAY_WIN` (away team) | Does the away team win? |
| `MONEYLINE_3_WAY_DRAW` | Is the match a draw? |

Within **each** of these markets the index follows the Yes/No convention:

| Index | Meaning |
| - | - |
| `0` | **Yes** — this result happens |
| `1` | **No** — this result does *not* happen |

<Warning>
  Do **not** treat the `No` side of a three-way moneyline as the "Away" team. Because a match can end in a draw, `No` means *any other outcome* (the other team winning **or** a draw), not a specific opponent. Each result is a separate Yes/No market — always resolve sidedness with the `index` field.
</Warning>

<Note>
  In some responses the outcome `type` field for these markets may surface as `Over` / `Under` rather than `Yes` / `No`. This is the same Yes/No semantics described above — `index: 0` is always the **Yes** side. Rely on `index`, not on `type`, to determine the side.
</Note>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.