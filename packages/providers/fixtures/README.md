# Provider fixtures

Frozen real responses from every external source `packages/providers` talks to, used exclusively
by the unit tests in `packages/providers/tests/` — the network is unavailable in unit tests by
construction (`tests/conftest.py`, `PYTEST_DISABLE_NETWORK=1`), so these files are what stands in
for it. Nightly contract tests (`scripts/checks/contract_sources.py`) are the only thing that talks
to the live APIs, and they are also what wrote every file in this tree.

**Refreshing this corpus**: `uv run --with requests scripts/checks/contract_sources.py
[--capture-fixtures]`. Every check that already parses a body writes it here as a side effect — the
same real call the nightly job makes anyway, so most of this corpus refreshes for free every time a
human runs the script locally and commits the diff. The nightly CI run makes the same calls and the
same writes, but into an ephemeral runner workspace with `permissions: contents: read` and no commit
step, so what it produces here verifies today's shape against what is already committed and is then
discarded — it never updates what unit tests read on its own (T012b; see the module docstring in
`contract_sources.py`). The one exception is the publication-delay corpus
(`docs/data-sources/publication_delay_samples.jsonl`, not part of this fixtures tree): that one
_does_ accumulate across nightly runs on its own, via a chained GitHub Actions artifact rather than
a git commit — see `docs/data-sources.md` §2 and `scripts/checks/publication_delay.py`. The replay
endpoint is the one exception: downloading a full replay body is real bandwidth beyond what
verifying the contract needs, so that download only happens with `--capture-fixtures` passed
explicitly, never in CI — and even then, only `aoems/replay_200_meta.json` is written. The body is
verified in memory (a real zip, the expected inner filename, the expected inner byte count) and
never committed: nothing in this repository reads it, a second reference replay would just be 2 MB
of permanent git history for a third party's match, and `replay_200_meta.json` already answers
every question a contract test needs to ask of the 200 case (see the module docstring in
`contract_sources.py`). A body-level fixture for a replay already exists where something actually
parses one: `tests/fixtures/replays/AgeIIDE_Replay_500546441.zip` (the parser engine, T079) — a
`ReplayProvider` contract test that needs bytes, not just shape, reads that file rather than adding
a second committed replay here.

When a nightly contract check fails, the shape changed at the source — fix
`docs/data-sources.md` first (constitution: "the document is what the next person will trust"),
then re-run this script to refresh whichever fixture drifted, then update the code.

## What is captured, and from what

Every probe below is public data belonging to real, active players, read the same way any other
visitor to the official leaderboard site would read it.

| File                                        | Provider method it feeds                           | Source call                                                                                                                          |
| ------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `relic/get_personal_stat.json`              | `ProfileProvider.resolve_profile` (found)          | `getPersonalStat?profile_names=["/steam/76561197984749679"]`                                                                         |
| `relic/get_personal_stat_unregistered.json` | `ProfileProvider.resolve_profile` (`None`, FR-003) | `getPersonalStat` for a steamid64 with no AoE2 profile                                                                               |
| `relic/get_personal_stat_batch.json`        | `ProfileProvider.personal_stats` (batching)        | `getPersonalStat?profile_ids=[196240,199325]`                                                                                        |
| `relic/get_recent_match_history.json`       | `MatchHistoryProvider.recent_matches`              | `getRecentMatchHistory?profile_ids=[196240]`, capped to 8 real matches                                                               |
| `relic/get_recent_match_history_batch.json` | `MatchHistoryProvider.recent_matches` (batching)   | `getRecentMatchHistory?profile_ids=[196240,199325]`, capped to 6 real matches                                                        |
| `aoems/replay_200_meta.json`                | `ReplayProvider.fetch_replay` (200 → `ReplayBlob`) | headers + inner filename/byte count of a genuinely downloaded, currently-available replay (body verified, not committed — see above) |
| `aoems/replay_404.json`                     | `ReplayProvider.fetch_replay` (404 → `NotFound`)   | a gameId past the ~31-day retention window                                                                                           |
| `companion/matches.json`                    | `EnrichmentProvider.enrich_matches`                | `data.aoe2companion.com/api/matches`, capped to 3 real matches                                                                       |
| `companion_profiles_search.json`            | `PlayerSearchProvider.search_players` (results)    | `data.aoe2companion.com/api/profiles?search=vipe`, one full page (20 real records), uncapped                                         |
| `companion_profiles_search_empty.json`      | `PlayerSearchProvider.search_players` (no match)   | `data.aoe2companion.com/api/profiles?search=` for a substring matching no player                                                     |
| `steam/check_authentication_invalid.txt`    | `SteamAuthProvider.verify` (rejected)              | a syntactically valid, never-issued `check_authentication` POST                                                                      |
| `steam/check_authentication_valid.txt`      | `SteamAuthProvider.verify` (accepted)              | **not captured — see `steam/README.md`**                                                                                             |

**"Capped to N real matches"** means the fixture holds fewer _entries_ than the live response, not
different ones: `_trim_match_history` in `contract_sources.py` slices the real array and drops
nothing else, so a ~400 KB live payload does not become a ~400 KB file the repository carries
forever for no gain in shape coverage. A 403 from aoe2companion needs no fixture of its own — the
circuit breaker in `EnrichmentProvider` reacts to the status code alone (providers.md), which any
`httpx.MockTransport(lambda r: httpx.Response(403))` covers without a frozen body.

## A field of an unexpected type

`ProfileProvider`'s contract-violation test (T020) needs a response with a field of the wrong type.
That fixture is not captured here — the real API has never returned one — and belongs to the test
itself: mutate a loaded copy of `relic/get_personal_stat.json` in Python rather than freezing a
response that does not exist in the wild. Inventing one here would be the exact "silent coercion"
this whole boundary exists to refuse, applied to the test fixtures instead of the code.
