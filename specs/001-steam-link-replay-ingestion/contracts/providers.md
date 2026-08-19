# Contract: DataProvider interfaces

The boundary constitution III draws. `apps/*` and `packages/core` depend on these Protocols and
never on a concrete provider, a URL or an HTTP client.

Ground truth for endpoint shapes is `docs/data-sources.md` and the `aoe2-data-sources` skill. This
document is about the *interface*, not the wire format.

## Shared obligations

Every provider, without exception:

- takes an explicit timeout; there is no default that means "forever";
- sends `User-Agent: aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)`;
- passes through a token bucket before every request;
- persists the raw response verbatim before any transformation **when the source is irrecoverable**
  — match history into `matches.raw_payload`, the replay bytes into the object store. Sources that
  can be re-queried at any time (ratings, enrichment, the Steam assertion) are exempt per FR-012: a
  second copy of something still available is a second thing to keep honest, for no gain;
- records a `provider_calls` row;
- raises a typed error — `ProviderUnavailable`, `ProviderRateLimited`, `ProviderContractViolation` —
  and never returns a partially-parsed object;
- validates strictly with Pydantic. A field of an unexpected type is a `ProviderContractViolation`,
  never a coerced value. Silent coercion is how wrong data becomes permanent.

## `SteamAuthProvider`

```python
def begin(self, return_to: str, state: str) -> str: ...
def verify(self, callback_params: Mapping[str, str]) -> SteamId64 | None: ...
```

`verify` performs the `check_authentication` round trip. It returns `None` for any failure and never
raises for an invalid assertion, so that a caller cannot accidentally treat an exception path as
success. It validates `return_to` against configuration and `claimed_id` against the exact expected
pattern.

## `ProfileProvider`

```python
async def resolve_profile(self, steam_id64: str) -> ProfileRef | None: ...
async def personal_stats(self, profile_ids: Sequence[int]) -> list[LeaderboardSnapshot]: ...
```

`resolve_profile` returns `None` when the Steam account has no AoE2 profile — an ordinary outcome
(FR-003), not an error. `personal_stats` accepts up to 50 profiles per call.

## `MatchHistoryProvider`

```python
async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]: ...
```

Batched, up to 10 profiles per call — the response is roughly 400 KB per profile. `RawMatch` carries
the parsed fields *and* the untouched payload.

## `ReplayProvider`

```python
async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound: ...
```

The provider reports what the wire said and nothing more. It holds no `completed_at`, and therefore
cannot know what a 404 means:

| Result | Wire condition | Returned or raised |
| --- | --- | --- |
| `ReplayBlob` | 200 — bytes, filename, content type | returned |
| `NotFound` | 404, carrying the observed status and nothing interpretive | returned |
| `ProviderRateLimited` | 429, or an unexpected 403 | raised |
| `ProviderUnavailable` | 5xx, timeout | raised |

The returned results are ordinary outcomes the caller records. The raised ones are not states of a
capture but conditions of the run, and the signature `ReplayBlob | NotFound` says so.

A `ReplayBlob` is stored and checksummed, **then** validated. A validation failure never discards it
(FR-026): after ~31 days the source holds no replacement, so an unreadable capture is evidence
rather than garbage. The caller marks `stored`, or `quarantined`.

A `NotFound` is a **three-way** decision, and it belongs to the caller because only the caller holds
`matches.completed_at`. The endpoint answers an identical 404 in all three cases:

| Age of the match | Capture becomes | Alert |
| --- | --- | --- |
| younger than `REPLAY_PUBLICATION_GRACE_HOURS` | stays `pending`, retried next cycle | none |
| older than the grace, inside the retention window, **and at least two attempts made** | `unavailable` | none |
| past the retention window | `expired` | severity-1 `expired_capture` |

Getting this wrong means alert fatigue, silence on the one metric that matters, or — the branch that
is easiest to omit — a few hours of publisher latency recorded as a permanent absence.

`ProviderRateLimited` stopping the entire run, rather than that one capture, is deliberate. The
budget is 21 days; there is always tomorrow. Being blocked by the source is not recoverable on the
same timescale.

## `EnrichmentProvider` (aoe2companion)

```python
async def enrich_matches(self, game_ids: Sequence[int]) -> dict[int, MatchEnrichment]: ...
```

Behind a circuit breaker, and the **only** provider whose failure is not an error. It returns
whatever it managed to get; missing keys are normal. A 403 here is expected noise (see
`docs/data-sources.md`). Whether it is reachable from Vercel at all is unverified — the application
must render correctly with this provider returning nothing, and that case gets a test.

Its `linkedProfiles` field is **not to be consumed**. FR-045: only a completed sign-in establishes
that two profiles belong to one person.

## Fixtures

`packages/providers/fixtures/` holds frozen real responses, captured with the checks in
`scripts/checks/`. Unit tests use them exclusively; the network is unavailable in unit tests by
construction. Contract tests against live APIs run nightly and are the only place a schema change is
detected.
