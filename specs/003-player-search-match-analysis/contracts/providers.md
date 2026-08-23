# Contract: provider additions

One new Protocol, and what this feature asks of two providers that already exist.
[001's providers.md](../../001-steam-link-replay-ingestion/contracts/providers.md) holds unchanged,
including its shared obligations — timeout, `User-Agent`, token bucket, `provider_calls` row, typed
errors, strict Pydantic validation — which are not restated here.

## `PlayerSearchProvider` (new)

```python
async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage: ...
```

Implemented by `CompanionEnrichmentProvider`, against
`GET https://data.aoe2companion.com/api/profiles?search={name}` (`docs/data-sources.md` §3).

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

### Hidden profiles

A record the source marks as hidden is dropped inside `search_players` and never reaches a caller
(FR-004c). The provider additionally reports it, so `aoe_profiles.hidden_observed_at` can be set and
the local fallback honours the same request when the source is down.

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

### Caching

Caching is the caller's, not the provider's (`profile_search_cache`, see
[data-model.md](../data-model.md)). The provider stays a thin, testable boundary; the cache is a
product decision about staleness and belongs where the TTL is configured.

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
