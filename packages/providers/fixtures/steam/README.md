# Steam `check_authentication` fixtures

## `check_authentication_invalid.txt` — real, captured

Written by `_steam_check_authentication_invalid` in `scripts/checks/contract_sources.py`: a
syntactically well-formed but never-issued OpenID 2.0 assertion, POSTed to
`https://steamcommunity.com/openid/login?openid.mode=check_authentication`. Steam's real reply is
frozen verbatim. This is the shape `SteamAuthProvider.verify` must turn into `None` for every
rejection quickstart scenario 1 exercises: a replayed callback, a tampered `claimed_id`, and this
one — an assertion that was never associated with a real login at all.

## `check_authentication_valid.txt` — hand-written, not captured

This one file in the whole corpus is not frozen from a live call, and cannot be by an unattended
script: a genuine `is_valid:true` response is bound to one specific, already-completed, interactive
Steam login (research.md §2 — "the identifier is then extracted from `openid.claimed_id`"). Getting
one for real means:

- filling in real account credentials (and clearing 2FA) into an automated script — the exact thing
  constitution VIII forbids ("no secret in the repository, ever"), and
- the assertion is single-use: `check_authentication` invalidates it the moment it succeeds, so
  even a manually captured one could never be replayed as a fixture for a second test run.

Its content is instead the OpenID 2.0 wire format Steam is confirmed (by the sibling fixture above)
to implement — the spec fixes the reply to exactly two lines, `ns:` echoing the namespace and
`is_valid:` true or false, and nothing else varies between a rejection and an acceptance. This is
the one fixture in the corpus that is structurally guaranteed rather than observed, which is a
different thing from invented: the format is dictated by a published, stable standard Steam's own
reply already demonstrates conformance to, not guessed at from a JSON API that could silently drift.

Nothing in `contract_sources.py` writes over this file — there is no automated call that could. If
a real, completed sign-in is ever captured by hand (a natural moment for that is the manual
quickstart walkthrough in T105, run against a real Steam account), replace this file with the
genuine response and delete this paragraph.
