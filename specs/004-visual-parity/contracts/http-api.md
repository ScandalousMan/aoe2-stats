# Contract: HTTP API delta

**Feature**: `004-visual-parity` | **Date**: 2026-08-30

The delta only. The base contracts are
[`specs/003-player-search-match-analysis/contracts/http-api.md`](../../003-player-search-match-analysis/contracts/http-api.md)
and 001's; everything not named here is unchanged.

**All changes are additive.** No field is removed, renamed or re-typed, and no existing field changes
meaning. `apps/web`'s hand-written `assert*Response` validators reject unknown _shapes_, not unknown
_keys_, so a client that has not been updated keeps working.

---

## `GET /api/players/{profile_id}`

```diff
  {
    "profile_id": 1807091,
    "alias": "…",
    "country": "fr",
+   "avatar_hash": "8f2a…c41" | null,
    "alias_observed_at": "…",
    "ratings": [ … ]
  }
```

| Field         | Type             | Notes                                                                                                                                                                                                                                                                                                      |
| ------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avatar_hash` | `string \| null` | The hash as aoe2companion reports it, from `aoe_profiles.avatar_hash`. **Never a URL** — the client builds `https://avatars.steamstatic.com/<hash>_full.jpg` (FR-008a). `null` is the ordinary case for a profile never seen in a companion response and renders as the neutral placeholder, not an error. |

**This route makes no provider call, and still makes none.** It reads `aoe_profiles` directly
(research.md D6). Putting a degradable third party in front of every profile render was the
alternative, and it was rejected.

`GET /api/profiles` (the caller's own linked profiles) gains `avatar_hash` identically.

---

## `GET /api/matches` and `GET /api/players/{profile_id}/matches`

Both are serialised by `match_row_json` (`apps/api/src/aoe2stats_api/routers/matches.py:426`), which
`routers/players.py:97` imports precisely so the two cannot drift — and
`apps/api/tests/test_players_history.py` asserts that identity. **That assertion is what makes this
widening safe, and it must keep passing.**

```diff
  {
    "game_id": 500615037,
    "map_name": "Arabia",
    "leaderboard_id": 3,
    "civilisation": 28,
    "civilisation_name": "Britons",
    "result": "win",
+   "rating": 922,
    "rating_diff": 16,
+   "team_id": 1,
+   "color_id": 4,
    "opponents": [ … ],
+   "participants": [ … ],
    …
  }
```

| Field          | Type          | Notes                                                                                                                                                                 |
| -------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rating`       | `int \| null` | The viewer's rating **after** the match. FR-005 renders `922 (+16)` and the list row carried no absolute rating at all; only match detail did.                        |
| `team_id`      | `int \| null` | Which side the viewer was on.                                                                                                                                         |
| `color_id`     | `int \| null` | 1..8. `null` whenever companion has not supplied one — the FR-010 degrade path, and a permanent resting state for a match companion does not know (data-model.md §6). |
| `participants` | `array`       | **All** participants, the viewer included.                                                                                                                            |

`opponents` is **unchanged and retained**. It excludes teammates by design — "the field is named
`opponents`" — and `participants` is a sibling, not a replacement, so nothing reading `opponents`
changes.

### `participants[]`

```json
{
  "profile_id": 264353,
  "alias": "Somero",
  "country": "cz",
  "team_id": 1,
  "civ_id": 28,
  "civ_name": "Britons",
  "color_id": 4,
  "result": "win",
  "rating": 1512,
  "rating_diff": -14
}
```

Identical in shape to match detail's participant entry, so `apps/web`'s
`features/matches/mappers.ts:77` (`toParticipantData`) serves both and the list and detail views
cannot disagree about a match.

| Field      | Notes                                                                                                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `civ_name` | Always present when `civ_id` is. Feature 002's mapping answers for every integer — a known name, or `Civilisation {id}` — so there is no unnamed state and the client never formats an id itself. |
| `result`   | `"win"`, `"loss"`, or `null`. `null` is FR-004's neutral state, **not** a loss.                                                                                                                   |
| `country`  | New on this shape. Feeds the opponent flag; `null` when unknown.                                                                                                                                  |

---

## `GET /api/matches/{game_id}`

Unchanged. It already serves `team_id`, `civ_id`, `civ_name`, `color_id`, `result`, `rating` and
`rating_diff` per participant — and `apps/web/src/features/matches/api.ts:232` already validates
`color_id` on the client. The reason detail looks complete today and the list does not is that both
read the same columns, and **the columns have never been written** (research.md D1). This contract's
real change is upstream of the serialisation: those columns start carrying values.

Detail's participants gain `country`, matching `participants[]` above.

---

## Field semantics that bind every route

These are the rules the client is entitled to rely on. Each corresponds to a spec edge case.

| Rule                                                                                          | Requirement                                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A `null` per-participant field means **not known**, never a zero, a default or a loss         | FR-004, FR-010                                                                                                                                                                                                |
| `rating_diff` is `null` when either rating is missing — never `0` as a stand-in               | FR-005                                                                                                                                                                                                        |
| `civ_name` is never absent when `civ_id` is present; the client never renders a bare `civ_id` | FR-001                                                                                                                                                                                                        |
| `map_name` is Relic's string, verbatim — there is no map id and none is invented              | FR-002                                                                                                                                                                                                        |
| `color_id` outside 1..8, or `null`, resolves to the neutral token, never to a broken swatch   | FR-003, FR-010                                                                                                                                                                                                |
| `avatar_hash` is a hash, never a URL; the CDN URL is built client-side                        | FR-008a, FR-015                                                                                                                                                                                               |
| No response carries a colour hex, an icon URL or a flag URL                                   | Constitution VI — colours are tokens, asset URLs are resolved from the pack by the client. A provider must not be able to set a product colour, and a URL on the wire would bypass the pack's coverage check. |

---

## Error and degradation behaviour

Unchanged, and deliberately so: **nothing in this feature introduces a new failure mode.**

- Companion degraded → `color_id` and `avatar_hash` are `null` on affected rows. The response is
  `200`, not partial, not flagged. Missing enrichment is a normal state (data-model.md §6), and the
  existing `degraded` flag stays scoped to search, where the user asked a question the service could
  not answer.
- A `civ_id`, `map_name` or `color_id` outside a pack → the API is unaffected; coverage is a client
  concern, resolved against the pack (contracts/asset-pack.md), and the API never learns what the
  client can draw.
- The profile route has no provider dependency, so no new error path exists on it at all.
