"""Response-header tests for FR-010 (T308): every route this feature *adds* answers
`X-Robots-Tag: noindex, nofollow` and `Cache-Control: private`
(`contracts/http-api.md`, "Response headers on every route above"), and every route 001 already
owns is unaffected by whatever T309 does to answer that.

**Scope, split with `test_no_public_directory.py` (T310).** `GET /api/matches/{game_id}` is this
feature's one *widened* route, not an added one — it already exists, registered by 001 (T070) —
and T310's own docstring claims its header assertion as that file's property 2
(`xfail(..., reason="T327 not implemented yet")`), stating explicitly that this route "falls
outside `test_no_index_headers.py`'s (T308/T309) own parametrisation over 'every route this
feature adds' — the header on the widening is [T310's] property to prove, not [this file's]".
Testing it again here would duplicate that assertion under the wrong reason (`T309` is the
middleware; `T327` is the widening that removes the route's ownership scope) and risk the two
files disagreeing about who answers for it. This file therefore covers the genuinely new surface:
`players.py` — registered now (T319), exposing `GET /api/players/search`, `GET
/api/players/{profile_id}` and `GET /api/players/{profile_id}/ratings` — plus `favourites.py`, the
per-participant replay-download route, and the published-analysis route, none of which is
registered yet; Phase 3 onward adds them.

**Deriving "the routes this feature adds".** `_FEATURE_ROUTE_TABLE` below transcribes
`contracts/http-api.md`'s own route tables ("Players", "Favourites", "Recorded games, per point of
view", "Analysis"), one entry per row, each comment citing its section. `POST /api/analyze` is
deliberately absent: the contract states, in its own words, that it "is the one route in this
contract that `api/index.py` does not serve" — a separate Vercel function (`api/analyze.py`),
never part of `create_app()`, so no assertion built on `TestClient` could ever exercise it here.

A hand-written table alone is exactly the list this task's own instructions warn against: a route
added later to `players.py` or `favourites.py` that nobody adds here would ship unheadered and
untested. `_feature_route_cases` closes that gap by *union-ing* the table with whatever
`create_app().openapi()` — FastAPI's own reflection of its registered route table, kept stable
across releases, rather than this Starlette version's private `_IncludedRouter`/`original_router`
routing internals — reports for the same path *patterns* at test-collection time. Today the union
still equals the table verbatim: `players.py` is registered now (T319), but the three routes it
adds — `GET /api/players/search`, `GET /api/players/{profile_id}`, `GET
/api/players/{profile_id}/ratings` — are already named in `_FEATURE_ROUTE_TABLE`, and
`favourites.py` and the two new `matches.py` sub-routes still do not exist —
`test_feature_route_table_cannot_silently_shrink_to_nothing` below asserts the counts directly
(`len(_FEATURE_ROUTE_CASES) >= len(_FEATURE_ROUTE_TABLE) > 0`), so a future edit that narrows the
patterns and drops coverage fails loudly instead of `@pytest.mark.parametrize` over an emptied list
quietly collecting zero test items, the specific degenerate case this task's instructions call out
by name. Once Phase 3 onward registers the remaining routers, any route added to them —
anticipated by the table or not — is picked up here automatically, with no further edit to this
file.

**The "unchanged" half is the mirror image, and needs no hand-written table at all.**
`_non_feature_api_routes` walks the entire `/api/*` surface `create_app().openapi()` reports and
keeps only what does not match this feature's path patterns and is not the widened match-detail
route — 001's routes today, and whatever is added to them later. Never carrying either header is
not a "T309 not implemented yet" case: it is true before this task, after T309, and after every
later one, so it is asserted directly rather than through `xfail` — an `xfail(strict=True)` here
would itself fail the moment it started passing, which today it already does.

**This file's guarantee is prefix-scoped, not universal.** `_FEATURE_ROUTE_PATH_PATTERNS` names
four path patterns — the same four `app.py`'s `_NoIndexHeaderMiddleware` matches against — and
every assertion below is built from them: `test_feature_route_answers_no_index_headers` proves the
header exists for every route registered under one of those four; `test_non_feature_route_headers_
are_unchanged` proves it is absent everywhere else *that this app registers today*. Neither test
can say anything about a route this feature, or a later one, adds under a path nobody has named in
`_FEATURE_ROUTE_PATH_PATTERNS`: such a route falls outside `_is_feature_path`, so
`_non_feature_api_routes` claims it as "unchanged" and this file then asserts it must *not* carry
the header — the opposite of what a route exposing a third party's data ought to get, and silently
so, since the same four patterns are what the middleware itself matches against. The guarantee this
file proves is "every route under one of these four prefixes is headered correctly (or is
correctly not)", not "every route this project will ever register is". Widening that coverage —
parametrising the middleware and this file over something other than a hand-maintained prefix list
— is a design change tracked separately; this docstring only states the limit as it stands today.

**No request below signs in, and every one carries `follow_redirects=False`**
(`test_auth_flow.py`'s own convention: `GET /api/auth/steam/start` answers a real redirect to
Steam, and `TestClient`'s default `follow_redirects=True` would otherwise try to follow it — a
real network call `PYTEST_DISABLE_NETWORK=1`, constitution III, forbids). The header this file
asserts belongs to the response regardless of the auth outcome — a crawler or a shared cache that
reaches one of these paths without a session must not index or retain the 401 or 404 it gets back
either — and every route below answers today's real status, whichever that is: `/api/players/*`
(T319) a genuine 401 or 200 now that its router is registered, and `/api/favourites/*`, the replay
route and the analysis route still a plain, unmatched-route-shaped 404, since their routers do not
exist yet — the full range `test_feature_route_answers_no_index_headers` below checks the header
against.

**`client` is `conftest.py`'s own fixture — the real throwaway database, not a fake session.**
A first attempt here built a `_FakeSession`-backed client the way `test_health.py` does, since no
test below needs seeded data; it does not work, because several routes in the "unchanged" set do
more than `execute()` on the way to whatever status they answer with — `GET /api/auth/steam/start`
calls `db_session.add(...)` to track its CSRF `state` (T028b), which `_FakeSession` has never
supported and was never meant to (`conftest.py`'s own docstring: it "stands in for `AsyncSession`:
every route this harness fakes a session for only calls `execute`"). This file requests routes
`_FakeSession` was never built for, so it asks `conftest.py` for the one fixture that behaves like
a real `AsyncSession` for every route, whatever that route needs from it.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aoe2stats_api.app import create_app

pytestmark = pytest.mark.usefixtures("environment")

_PATH_PARAM = re.compile(r"\{[^{}]+\}")


def _concrete_path(path_template: str) -> str:
    """Fill every path parameter with a syntactically valid placeholder. The value never
    matters — every route below answers an error status without it, registered or not — only the
    response headers are asserted here."""
    return _PATH_PARAM.sub("999999", path_template)


# The route table this feature adds (contracts/http-api.md). See the module docstring for why
# `GET /api/matches/{game_id}` — widened, not added — is deliberately absent, and why
# `POST /api/analyze` is absent too.
_FEATURE_ROUTE_TABLE: tuple[tuple[str, str], ...] = (
    ("get", "/api/players/search"),  # "Players"
    ("get", "/api/players/{profile_id}"),  # "Players"
    ("get", "/api/players/{profile_id}/matches"),  # "Players"
    ("get", "/api/players/{profile_id}/ratings"),  # "Players"
    ("get", "/api/favourites"),  # "Favourites"
    ("put", "/api/favourites/{profile_id}"),  # "Favourites"
    ("delete", "/api/favourites/{profile_id}"),  # "Favourites"
    ("get", "/api/matches/{game_id}/replay/{profile_id}"),  # "Recorded games, per point of view"
    ("get", "/api/matches/{game_id}/analysis"),  # "Analysis"
)

# The same table's routers, as path *patterns* rather than concrete templates, so a route
# registered later under one of these routers is recognised whether or not `_FEATURE_ROUTE_TABLE`
# was ever updated to name it.
_FEATURE_ROUTE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/players(/.*)?$"),
    re.compile(r"^/api/favourites(/.*)?$"),
    re.compile(r"^/api/matches/\{[^/]+\}/replay/\{[^/]+\}$"),
    re.compile(r"^/api/matches/\{[^/]+\}/analysis$"),
)

# The one route this feature widens rather than adds. `test_no_public_directory.py` (T310) owns
# its header assertion (module docstring); excluded here so `_non_feature_api_routes` below never
# claims it as "unchanged", which would be false the moment T327 lands.
_WIDENED_MATCH_DETAIL_PATH = "/api/matches/{game_id}"


def _is_feature_path(path: str) -> bool:
    return any(pattern.match(path) for pattern in _FEATURE_ROUTE_PATH_PATTERNS)


def _openapi_paths(app: FastAPI) -> dict[str, list[str]]:
    """`{path: [methods]}`, straight from FastAPI's own `openapi()` reflection of its currently
    registered route table — the documented, stable way to read it back. `app.routes` itself, in
    this project's Starlette version, nests every `include_router` behind a private
    `_IncludedRouter`/`original_router` wrapper with no `path` of its own at the top level, which
    is not a surface this test should depend on."""
    schema = app.openapi()
    paths: dict[str, list[str]] = schema.get("paths", {})
    return {path: sorted(operations.keys()) for path, operations in paths.items()}


def _feature_route_cases(app: FastAPI) -> list[tuple[str, str]]:
    """`_FEATURE_ROUTE_TABLE`, unioned with whatever the app has already registered under the
    same path patterns — see the module docstring for why the union, not the table alone, is what
    catches a route someone adds later and forgets to list here."""
    discovered = {
        (method, path)
        for path, methods in _openapi_paths(app).items()
        if _is_feature_path(path)
        for method in methods
    }
    return sorted(set(_FEATURE_ROUTE_TABLE) | discovered)


def _non_feature_api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Every other `/api/*` route this app currently registers — 001's, and anything this
    feature's own routers grow later that does not match `_FEATURE_ROUTE_PATH_PATTERNS` — the set
    that must never carry the new headers."""
    return sorted(
        (method, path)
        for path, methods in _openapi_paths(app).items()
        if path != _WIDENED_MATCH_DETAIL_PATH and not _is_feature_path(path)
        for method in methods
    )


_APP_ROUTE_TABLE = create_app()
_FEATURE_ROUTE_CASES = _feature_route_cases(_APP_ROUTE_TABLE)
_NON_FEATURE_ROUTE_CASES = _non_feature_api_routes(_APP_ROUTE_TABLE)


def _ids(cases: list[tuple[str, str]]) -> list[str]:
    return [f"{method.upper()} {path}" for method, path in cases]


def test_feature_route_table_cannot_silently_shrink_to_nothing() -> None:
    """Guards the specific failure mode this task's instructions call out by name: since none of
    this feature's routers are registered yet, `_feature_route_cases` derives entirely from
    `_FEATURE_ROUTE_TABLE` today, and `@pytest.mark.parametrize` over an empty list collects zero
    test items — a silent no-op that a `pytest` summary cannot distinguish from a pass, not even a
    reported skip. Asserting the counts here, in a test carrying no `xfail`, is what keeps that
    degenerate case from ever looking like coverage — today, and for as long as this file exists."""
    assert len(_FEATURE_ROUTE_CASES) >= len(_FEATURE_ROUTE_TABLE) > 0
    assert set(_FEATURE_ROUTE_TABLE) <= set(_FEATURE_ROUTE_CASES)
    assert len(_NON_FEATURE_ROUTE_CASES) > 0
    assert (_WIDENED_MATCH_DETAIL_PATH not in {path for _, path in _NON_FEATURE_ROUTE_CASES}) and (
        _WIDENED_MATCH_DETAIL_PATH not in {path for _, path in _FEATURE_ROUTE_CASES}
    )


@pytest.mark.parametrize("method,path", _FEATURE_ROUTE_CASES, ids=_ids(_FEATURE_ROUTE_CASES))
def test_feature_route_answers_no_index_headers(method: str, path: str, client: TestClient) -> None:
    """FR-010: `X-Robots-Tag: noindex, nofollow` and `Cache-Control: private` on every route this
    feature adds, whether or not the router behind it is registered yet — the middleware T309
    adds is path-based (module docstring), so the assertion holds on today's plain 404 exactly as
    it will on tomorrow's 200 or 401."""
    response = client.request(method, _concrete_path(path), follow_redirects=False)

    assert response.headers.get("x-robots-tag") == "noindex, nofollow"
    assert response.headers.get("cache-control") == "private"


@pytest.mark.parametrize(
    "method,path", _NON_FEATURE_ROUTE_CASES, ids=_ids(_NON_FEATURE_ROUTE_CASES)
)
def test_non_feature_route_headers_are_unchanged(
    method: str, path: str, client: TestClient
) -> None:
    """001's existing routes — and `/api/matches/{game_id}`, which this feature widens rather
    than adds and does not carry this file's header assertion for (module docstring) — must not
    gain either header as a side effect of T309's middleware. Not `xfail`: this already holds
    before T309 and must keep holding after it, and after every route either module adds later.

    Prefix-scoped, not universal (module docstring, "This file's guarantee is prefix-scoped"): a
    future route registered under a path `_FEATURE_ROUTE_PATH_PATTERNS` does not name falls into
    this test's parametrisation and is asserted here to *lack* the header, whether or not it
    should carry one."""
    response = client.request(method, _concrete_path(path), follow_redirects=False)

    assert "x-robots-tag" not in response.headers
    assert "cache-control" not in response.headers


def test_widened_match_detail_route_is_excluded_from_both_sides() -> None:
    """`GET /api/matches/{game_id}` belongs to neither parametrised set above — see the module
    docstring's "Scope, split with `test_no_public_directory.py`" section. A regression in either
    filter (either claiming this route as "added" or as "unchanged") would silently duplicate or
    drop T310's own assertion of it; this makes that boundary an explicit, checked fact rather
    than an implicit consequence of the two filters happening to agree today."""
    feature_paths = {path for _, path in _FEATURE_ROUTE_CASES}
    non_feature_paths = {path for _, path in _NON_FEATURE_ROUTE_CASES}
    assert _WIDENED_MATCH_DETAIL_PATH not in feature_paths
    assert _WIDENED_MATCH_DETAIL_PATH not in non_feature_paths
    # Sanity: the app registers it (001, T070) — this file is excluding a route that exists and
    # is reachable, never one that is merely absent from the app for an unrelated reason.
    assert _WIDENED_MATCH_DETAIL_PATH in _openapi_paths(_APP_ROUTE_TABLE)
