"""Pure shape assertions behind `contract_sources.py`'s live checks (T385a).

Split out for exactly the reason `publication_delay.py`'s own docstring gives: every
`@check`-decorated function in `contract_sources.py` fires a live network call the moment it is
*defined* (the decorator calls `fn()` immediately), and the module also parses `sys.argv` for
`--capture-fixtures` at import time. Neither belongs anywhere near a unit test — importing
`contract_sources` under `uv run pytest` would run the whole nightly suite against
`tests/conftest.py`'s network-blocking socket guard (constitution III) and then hit that module's
own `sys.exit(1)` when every one of those calls failed. Everything below is pure: given an already
`.json()`-parsed body, it either returns silently or raises `AssertionError` naming exactly which
part of the shape drifted. No network, no argv, no import-time side effect at all.

`assert_companion_search_shape` mirrors the exact two-level distinction
`packages/providers/src/aoe2stats_providers/companion/provider.py`'s `_parse_search_page` /
`_parse_search_result` already draw in production, so a fixture that fails here is a fixture that
would also degrade `PlayerSearchProvider.search_players` silently (`degraded: false, results: []`,
T377's finding) rather than an assertion this module invented on its own:

- **BL-1 (envelope).** `body` is not a JSON object, or carries no `profiles` list at all. This is
  never true for a genuine zero-match answer — `{"profiles": []}` is a real, parseable page, not a
  drift.
- **BL-5 (record).** `profiles` is a real, non-empty list, but not one entry in it carries both
  `profileId` and `name` — a rename of either field, applied uniformly by the source the way a
  schema change would be. One bad record among otherwise-good ones is not this: `_parse_search_page`
  drops a single malformed entry and still returns the rest, so this function only raises when
  *every* entry fails, matching that boundary exactly.

`docs/data-sources.md` §3's "Profile search behaviour" table is the measured record this checks
against (`profileId`, `name`, `country`, `games`, `drops`, `clan`, `avatarhash`, `verified`,
`platform`, and six sparse `social*` fields — no hidden-profile field, T301a) — this function only
ever asserts the two fields production code actually reads (`_parse_search_result`, FR-004b); the
rest of that table is enrichment `PlayerSearchResult` keeps or drops, not shape this check owns.
"""

from __future__ import annotations

from typing import Any


def assert_companion_search_shape(body: Any) -> None:
    """Raise `AssertionError` the moment a parsed `GET /api/profiles?search=` body no longer
    parses into the contracted `{"profiles": [{"profileId": ..., "name": ..., ...}]}` shape.

    Returns silently for a genuine zero-match page (`{"profiles": []}`) — see the module
    docstring's BL-1/BL-5 split. Callers that know their probe query is expected to match
    something (a well-known active profile's name) are the ones that should additionally assert
    non-emptiness; this function's job stops at whether the shape itself survived.
    """
    assert isinstance(body, dict), "search response body is not a JSON object"

    profiles = body.get("profiles")
    assert isinstance(profiles, list), "search response body carries no `profiles` list"

    if not profiles:
        return

    survives = any(
        isinstance(profile, dict) and "profileId" in profile and "name" in profile
        for profile in profiles
    )
    assert survives, (
        "profiles is non-empty but no record carries both `profileId` and `name` "
        "(a record-level rename — companion/provider.py's BL-5)"
    )
