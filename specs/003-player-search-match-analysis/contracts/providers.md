# Contract: provider additions

One new Protocol, and what this feature asks of two providers that already exist.
[001's providers.md](../../001-steam-link-replay-ingestion/contracts/providers.md) holds unchanged,
including its shared obligations — timeout, `User-Agent`, token bucket, `provider_calls` row, typed
errors, strict Pydantic validation — which are not restated here.

## `PlayerSearchProvider` (new)

```python
def is_degraded(self) -> bool: ...
async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage: ...
```

Implemented by `CompanionEnrichmentProvider`, against
`GET https://data.aoe2companion.com/api/profiles?search={name}` (`docs/data-sources.md` §3).
`is_degraded()` is part of this Protocol, not an extension a caller adds on top of it — see
"Failure" below for what it means and when a caller must check it.

```python
@dataclass(frozen=True)
class PlayerSearchResult:
    profile_id: int
    alias: str
    country: str | None
    games_played: int | None
    clan: str | None

@dataclass(frozen=True)
class PlayerSearchPage:
    results: Sequence[PlayerSearchResult]
    has_more: bool
```

### The fields that are not there

`PlayerSearchResult` has no `steam_id`, no `shared`, no `shared_history` and no `linked_profiles`,
and this is the substance of FR-004b rather than an omission. The source carries all four
(`docs/data-sources.md` §3's trap), and they are the same unverifiable account-linking claim
001's FR-045 refuses.

The enforcement is the absence of the field, not a filter. A value stripped in a router has already
existed in memory, in a log line and in a traceback; a value with nowhere to be assigned has not.
This provider already demonstrates the pattern for `linkedProfiles` — its module docstring records
that the field "is not read anywhere below, deliberately" — and the search parser follows it exactly:
it reads `profileId`, `name`, `country`, `games`, `clan` and the pagination fields, and no others.

### Hidden profiles — there are none to honour

This provider drops nothing on privacy grounds and reports nothing about it, because there is nothing
to drop. The source's `hidden` field was measured on 2026-08-23 (T301a, `docs/data-sources.md` §3) and
carries no value in any projection; FR-004c was retired on that measurement. `search_players` returns
every record the source returns, minus the fields **The fields that are not there** removes.

The one thing that would change this is a measurement, not a preference: if the source ever starts
populating `hidden`, that is a new fact for §3 and a new decision for the spec.

### Failure

`search_players` behaves like the rest of this provider: it **never raises**. It returns an empty
page, and the caller distinguishes "no such player" from "search is unavailable" from the same signal
the existing enrichment path uses — the circuit breaker's own state — not from an exception. This is
what makes FR-003 implementable without inventing a sentinel: a 403 here is documented, expected
bot-protection noise (`docs/data-sources.md` §3), and it must not become a `ProviderRateLimited` the
way an unexpected 403 would on any other provider.

The existing circuit breaker and token bucket are shared with `enrich_matches` rather than duplicated.
A search storm and an enrichment storm are the same source under the same protection, and two
independent breakers would each see half the failures and neither would trip.

`is_degraded()` is part of `PlayerSearchProvider` itself (see the Protocol above), not a detail
private to `CompanionEnrichmentProvider`: it is the only way a caller can read the breaker's state
ahead of a call, since `search_players` never raises. A caller must also re-read `is_degraded()`
*after* a call that returned a page — the call that trips the breaker, or a post-cooldown probe
that fails, still returns an ordinary-looking (possibly empty) page rather than raising, and only a
post-call check tells that page apart from a genuine answer. `apps/api/src/aoe2stats_api/search.py`
does both.

**The breaker's lifetime is the caller's to manage, not this provider's.** A `CompanionEnrichmentProvider`
rebuilt per request (because its `call_sink` closes over a request-scoped resource) must be given
the *same* breaker every time — `packages/providers/.../companion/provider.py`'s constructor takes
an optional `breaker`, and `build_circuit_breaker()` is how a caller builds a process-lifetime one
to inject. A breaker rebuilt alongside the provider is always closed, and `is_degraded()` can never
be `True` in production even though every unit test exercises that branch directly.

### `profile_search_cache.source` — the vocabulary and what a cache hit means

`profile_search_cache` (see [data-model.md](../data-model.md)) has one column this contract, not
`data-model.md`, is the source of truth for: `source`. Two values exist today —

| `source` | Written when | A cache hit reads as |
| --- | --- | --- |
| `"companion"` | `search_players` returned, and the breaker was closed both before and after the call — a confident, live answer. | `degraded: false` |
| `"aoe_profiles"` | Reserved for a row answered by the local fallback over `aoe_profiles` (`search.py`'s `_local_fallback_results`). **Not currently written** — see "Caching" below. | `degraded: true` |

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

**A fallback answer is not cached at all.** `search_players`'s own cache-first behaviour
(FR-004e) exists to spare a source "that is degradable by design" repeated calls for a repeated
query — but while the breaker is open, `is_degraded()` already stops every call before it reaches
the transport, cache row or not. Caching the fallback's own, reduced answer under `source =
"aoe_profiles"` would buy no further protection and would cost something real: it would pin every
repeat of that query to the fallback's reduced results for the configured TTL (`PLAYER_SEARCH_CACHE_TTL_SECONDS`,
`.env.example`) even after the source has recovered — the outage would outlive itself. The
alternative considered and rejected was a much shorter TTL for a fallback row; not caching it at
all was chosen instead, because there is no protective benefit to trade the staleness risk
against. `_local_fallback_results` is a plain, cheap read against a table this service already
holds in memory-adjacent storage (`aoe_profiles`), not an external call — recomputing it on every
degraded request is not the "repeated calls against a degradable source" FR-004e caches around.

## `ReplayProvider` (existing) — what this feature asks of it

Unchanged interface. Two new callers, with different obligations:

| Caller | What it does with the bytes |
| --- | --- |
| download of an `obtainable` point of view | streams them to the user and **stores nothing** (FR-027) |
| analysis | stores them byte-for-byte with a checksum, as a `retained_recordings` row (FR-033) |

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
