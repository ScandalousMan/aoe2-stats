# Contract: provider additions

One new Protocol, and what this feature asks of two providers that already exist.
[001's providers.md](../../001-steam-link-replay-ingestion/contracts/providers.md) holds unchanged,
including its shared obligations — timeout, `User-Agent`, token bucket, `provider_calls` row, typed
errors, strict Pydantic validation — which are not restated here.

## `PlayerSearchProvider` (new)

```python
def is_degraded(self) -> bool: ...
def last_call_failed(self) -> bool: ...
async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage: ...
```

Implemented by `CompanionEnrichmentProvider`, against
`GET https://data.aoe2companion.com/api/profiles?search={name}` (`docs/data-sources.md` §3).
`is_degraded()` and `last_call_failed()` are both part of this Protocol, not an extension a caller
adds on top of it (round-2 review's BL-2 remediation added the second) — see "Failure" below for
what each means and when a caller must check them.

```python
@dataclass(frozen=True)
class PlayerSearchResult:
    profile_id: int
    alias: str
    country: str | None
    games_played: int | None
    clan: str | None
    # The source's own claim, carried unverified (constitution IX 3.0.0). Never used to link
    # or merge profiles — see "The fields, and the one rule on them" below.
    unverified_steam_id: str | None

@dataclass(frozen=True)
class PlayerSearchPage:
    results: Sequence[PlayerSearchResult]
    has_more: bool
```

### The fields, and the one rule on them

`PlayerSearchResult` carries `profile_id`, `alias`, `country`, `games_played`, `clan` and
`unverified_steam_id`. The last is new: constitution IX at 3.0.0 (2026-08-24) treats every field the
AoE2 DE APIs serve as public and keeps it so, which retired FR-004b's strip.

Its name is the requirement rather than a comment on it. It is `unverified_steam_id` and not
`steam_id` so that **a claim this service has not verified** cannot be read as a fact by a consumer
who never opened this file. A verified Steam sign-in is the only account link this project vouches
for (001 FR-006), and presenting an unchecked third-party assertion beside one without the
distinction is an accuracy fault independent of how the data is classified.

What did not change, and is the half worth testing: it MUST NOT be used to infer, suggest or act
upon a relationship between profiles the user has not proven by signing in — no linking, no merging,
no feature treating two profiles as one person on that basis. That is 001's FR-045 minus the half
the 2026-08-24 decision removed.

`shared`, `shared_history` and `linked_profiles` stay absent, and not as a residue of FR-004b.
`shared` has no known meaning — `docs/data-sources.md` §3 measured both values across 200 records and
says "Do not act on it", so a field nothing may act on is a field with nowhere to be assigned.
`shared_history` is a preference this service neither honours nor circumvents (constitution IX), and
carrying it would invite a consumer to do one or the other. `linked_profiles` is the same
unverifiable claim at a different shape, and nothing reads it — the module docstring records that it
"is not read anywhere below, deliberately", and that stands.

### Hidden profiles — there are none to honour

This provider drops nothing on privacy grounds and reports nothing about it, because there is nothing
to drop. The source's `hidden` field was measured on 2026-08-23 (T301a, `docs/data-sources.md` §3) and
carries no value in any projection; FR-004c was retired on that measurement. `search_players` returns
every record the source returns, minus the fields **The fields that are not there** removes.

The one thing that would change this is a measurement, not a preference: if the source ever starts
populating `hidden`, that is a new fact for §3 and a new decision for the spec.

### Failure

`search_players` behaves like the rest of this provider: it **never raises**. It returns an empty
page, and the caller distinguishes "no such player" from "search is unavailable" from the same two
signals the existing enrichment path's breaker exposes — `is_degraded()` and `last_call_failed()`
(round-2 review, BL-1/BL-2) — not from an exception. This is what makes FR-003 implementable
without inventing a sentinel: a 403 here is documented, expected bot-protection noise
(`docs/data-sources.md` §3), and it must not become a `ProviderRateLimited` the way an unexpected
403 would on any other provider.

The existing circuit breaker and token bucket are shared with `enrich_matches` rather than duplicated.
A search storm and an enrichment storm are the same source under the same protection, and two
independent breakers would each see half the failures and neither would trip.

**A genuine 200 does not, by itself, mean the call succeeded (BL-1).** A body that does not parse
into the contracted `{"profiles": [...]}` shape — a renamed key, a wrapped list, a bare `[]` — is a
source drift, not a confident, empty answer, and `search_players` must record it as a failure, not
as a success: `packages/providers/.../companion/provider.py`'s `_parse_search_page` raises a
private exception on exactly that distinction, and `search_players` only calls
`_breaker.record_success()` once the shape has actually been checked. Recording success
unconditionally before that check — the round-1 shape of this provider — is how a single renamed
field on a single-maintainer API with no published contract would have made FR-003 invert forever:
every search would answer `degraded: false, results: []`, with nothing to self-correct it, because
the breaker never saw a failure.

`is_degraded()` and `last_call_failed()` are both part of `PlayerSearchProvider` itself (see the
Protocol above), not details private to `CompanionEnrichmentProvider`. `is_degraded()` is the only
way a caller can read the breaker's state ahead of a call, since `search_players` never raises. A
caller must also re-read _both_ signals **after** a call that returned a page (BL-2): the call
that trips the breaker, or a post-cooldown probe that fails, still returns an ordinary-looking
(possibly empty) page rather than raising — but `is_degraded()` alone only catches the call that
pushes the breaker's own consecutive-failure count past its threshold. A consecutive-failure
breaker holds `is_degraded()` at `False` through the first `_FAILURE_THRESHOLD - 1` failures of
every fresh outage by construction, and the round-2 review reproduced exactly that by execution:
the first two failing calls of an outage read `is_degraded()` as `False` both before and after,
and were cached as a confident answer. `last_call_failed()` is the signal that closes that gap —
`True` after any failed call, independent of the threshold — and a caller must check
`is_degraded() or last_call_failed()` after every call, not `is_degraded()` alone.
`apps/api/src/aoe2stats_api/search.py` does this.

**The breaker's lifetime is the caller's to manage, not this provider's, and `breaker` is required,
not optional (MJ-3).** A `CompanionEnrichmentProvider` rebuilt per request (because its `call_sink`
closes over a request-scoped resource) must be given the _same_ breaker every time —
`packages/providers/.../companion/provider.py`'s constructor takes a required `breaker`, built once
via `aoe2stats_providers.wiring.build_companion_breaker()` and injected into every request's own,
otherwise disposable, provider instance. The constructor used to default `breaker` to `None` and
build a fresh one silently when omitted; that default was removed because it is exactly how the
next call site (the ingester's own `enrich_matches` wiring) would have reproduced this defect by
omission, with no test able to see it — a breaker rebuilt alongside the provider is always closed,
and `is_degraded()` can never be `True` in production even though every unit test exercises that
branch directly.

### `profile_search_cache.source` — the vocabulary and what a cache hit means

`profile_search_cache` (see [data-model.md](../data-model.md)) has one column this contract, not
`data-model.md`, is the source of truth for: `source`. Two values exist today —

| `source`         | Written when                                                                                                                                                       | A cache hit reads as |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------- |
| `"companion"`    | `search_players` returned a page, and neither `is_degraded()` nor `last_call_failed()` was true before or after the call — a confident, live answer.               | `degraded: false`    |
| `"aoe_profiles"` | A row answered by the local fallback over `aoe_profiles` (`search.py`'s `_local_fallback_results`), cached under a short TTL — see "Caching" below (BL-3 re-take). | `degraded: true`     |

A cache hit derives `degraded` structurally, from `source != "companion"`, never by re-asking the
provider: **any value other than `"companion"` reads as degraded**, not only `"aoe_profiles"`
specifically. This is deliberate — a future third source, or a row seeded directly (as
`apps/api/tests/test_players_routes.py` does, to exercise this reading without a live call), must
not require a change to the reading logic, only to what gets written. A future writer must reuse
`"companion"` for a confident answer and pick a value other than that for anything less than one;
inventing an alternative name for a confident answer (e.g. `"live"`) would silently flip every
existing cached row's `degraded` reading, since only the one literal `"companion"` is exempt.

### Caching

Caching is the caller's, not the provider's (`profile_search_cache`, see
[data-model.md](../data-model.md)). The provider stays a thin, testable boundary; the cache is a
product decision about staleness and belongs where the TTL is configured.

**A fallback answer is cached, under a short, dedicated TTL (BL-3 re-take of the round-1 M1
decision).** Round 1 stopped caching the fallback's own answer at all, reasoning that
`_local_fallback_results` was "a plain, cheap read against a table this service already holds" and
so cost nothing extra to recompute on every degraded request. **That premise was measured false in
round 2**: `_local_fallback_results` is an unfiltered `SELECT profile_id, count(*) FROM
match_players GROUP BY profile_id` subquery joined to `aoe_profiles` — a full aggregate over the
match-participants table, recomputed on _every_ degraded request, up to the per-user rate limit,
precisely while the source is down, against a 0.5 GB Neon instance. Not caching it at all traded a
5-minute cache for a full-table aggregate at request volume, exactly when load on this service is
already elevated (a search storm is often what surfaces an outage in the first place).

The re-take: a fallback answer is now written to `profile_search_cache` under `source =
"aoe_profiles"`, at a short, fixed TTL (`_FALLBACK_CACHE_TTL_SECONDS` in `search.py`, deliberately
not settings-driven — a protective constant, not an operator knob) rather than the caller's own,
much longer `ttl_seconds` (`PLAYER_SEARCH_CACHE_TTL_SECONDS`, `.env.example`). This keeps round 1's
original concern — a `source` written once during an outage pinning every repeat of that query to
the fallback's reduced results even after the source has recovered, "the outage would outlive
itself" — bounded to the short TTL instead of eliminated by not caching at all: a stale fallback row
self-heals within seconds of the source recovering, while a burst of repeat queries against a down
source now recomputes the aggregate once per TTL window rather than once per request.
`profile_search_cache`'s opportunistic pruning (`search.py`'s `_write_cache`) is TTL-aware per
row's own `source` for the same reason: a single, uniform pruning threshold would either prune
fresh fallback rows too eagerly (at the short TTL) or let a stale one outlive its short protection
window (at the long one).

## `ReplayProvider` (existing) — what this feature asks of it

Unchanged interface. Two new callers, with different obligations:

| Caller                                    | What it does with the bytes                                                        |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| download of an `obtainable` point of view | streams them to the user and **stores nothing** (FR-027)                           |
| analysis                                  | stores them byte-for-byte with a checksum, as a `retained_recordings` row (FR-033) |

Both go through the same provider, the same token bucket and the same `provider_calls` record. What
separates them is FR-039: an analysis fetch passes `apps/analyzer/admission.py` first (R7), a
download does not, and neither may consume the budget capture depends on.

`fetch_replay` already returns `NotFound` rather than raising for a 404 — the ordinary outcome the
retention window produces — which is what lets the caller tell `never_recorded` from
`expired_since_page_load` by looking at the match's age rather than at an exception.

## `MatchHistoryProvider` (existing) — what this feature asks of it

Unchanged interface, one widened obligation. 001 read match history for a user's own linked profiles;
this feature reads it for any profile a user opens.

The verbatim-persistence rule follows the data, not the requester: a third party's match history is
irrecoverable exactly as a user's own is, so it is persisted verbatim into `matches.raw_payload`
(FR-011, constitution III). FR-011 states the consequence plainly and it is worth carrying here,
because it is where the code will be written: **viewing a third party's history permanently records
their matches**, and 001's third-party objection route has to cover data recorded this way.

Search results are the opposite case and the contrast is the point: a name search can be re-run at
any time, so it is recoverable, so it is cached rather than persisted. Same source family, opposite
obligation, decided by the same rule.
