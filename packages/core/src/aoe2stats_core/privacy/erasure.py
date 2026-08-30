"""Erasure's own reusable instrument (T091): pseudonymising one `profile_id` wherever it appears
in `match_players` and `aoe_profiles` — pure logic only, the same "no SQL, no object-store call,
no `aoe2stats_storage` import" split `export.py`'s module docstring draws one level up in this
package.

**Written over an arbitrary `profile_id`, not derived from the user being erased.** `data-model.md`
(001): "The departing user's `profile_id` is pseudonymised in place instead — the same mechanism
FR-039 gives third parties." A third party objecting under FR-039 has no user row at all to derive
a `profile_id` from — only the profile they are named by — so the one function both callers share
has to take a `profile_id` as its own input, never a `User`. `apps/api/src/aoe2stats_api/routers/
privacy.py`'s `POST /api/privacy/erase` (T091) is this function's first caller, over the departing
user's own linked profiles; T092's third-party objection resolution is its second, over whichever
profile a resolved objection names. Neither caller is privileged over the other in this module —
there is exactly one pseudonymisation, called twice.

**Why a new, distinct `profile_id` is unavoidable, not a stylistic choice.**
`match_players.profile_id` carries a foreign key to `aoe_profiles.profile_id`
(`packages/storage/.../models.py`). Overwriting `aoe_profiles.alias`/`country` for the *same*
`profile_id` in place would leave every `match_players` row naming it completely unchanged — the
real, still-linkable numeric identifier would still appear across every match that profile ever
played, which is exactly the trace SC-008 forbids. Pseudonymising has to mean *retargeting* those
rows onto a different, masked profile, and retargeting a foreign key means the row it now points at
has to exist first. `pseudonymise_profile` below only computes what that retargeting needs; the
caller (necessarily I/O, necessarily in the router) is the one that inserts the placeholder row and
runs the `UPDATE`.

**The replacement id is `-abs(profile_id)`: deterministic, not random, and disjoint from every real
one by construction.** Relic's own ids (`aoe_profiles.profile_id`, `docs/data-sources.md`) are
always positive, so negating one can never collide with a real profile — never with the profile
being pseudonymised, never with any other real profile, and never with another pseudonymised
profile's own placeholder, since negation is a bijection over the positive integers. Determinism
is what makes a second call over the same `profile_id` a no-op rather than a hazard: T092 resolving
an objection against a profile 001's own erasure already pseudonymised (or a retry of either) finds
the identical placeholder id, not a fresh, colliding one — the placeholder row will already exist,
and the caller's own `UPDATE ... WHERE profile_id = :profile_id` simply matches nothing the second
time, since every row that could have matched was already moved.

**Rejected: one shared placeholder profile for every pseudonymisation.** A single well-known
"erased" `profile_id` looks simpler until two people who both happen to have played *the same
match* are ever pseudonymised — `match_players`' own primary key is `(game_id, profile_id)`, and a
shared placeholder would make the second retargeting collide with the first inside that one game.
A distinct placeholder per real `profile_id`, derived deterministically from it, cannot collide this
way: two different real ids always retarget onto two different placeholders.

**`alias`/`country` are written twice, not once** — the caller is expected to write this module's
`alias`/`country` pair onto *both* the new placeholder row it inserts *and* the original row the
`profile_id` still names, once every `match_players` row has been moved off it. The original row
usually still exists once this returns — `aoe_profiles` has independent referents (a `favourites`
row someone else holds naming the same `profile_id` before it was ever pseudonymised, a
`rating_snapshots` row) that this module has no way to know about and the caller has no obligation
to remove — so leaving its own identifying columns unscrubbed would leave exactly the trace
pseudonymising `match_players` was meant to close.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Written to both the placeholder `aoe_profiles` row a pseudonymised `profile_id` is retargeted
#: onto and the original row it is retargeted away from (module docstring) — a fixed, generic value
#: rather than anything derived from the real one it replaces, since deriving it from the real alias
#: would still leak a fragment of the identity being pseudonymised.
PSEUDONYMISED_ALIAS = "Erased player"


@dataclass(frozen=True, slots=True)
class ProfilePseudonymisation:
    """Everything pseudonymising one real `profile_id` requires the caller to write.

    `pseudonymous_profile_id` is the placeholder every `match_players` row naming the real
    `profile_id` must be retargeted onto; `alias`/`country` are the masked `aoe_profiles` columns
    for that placeholder row (inserted if it does not already exist) and, per the module docstring,
    for the original row as well.
    """

    pseudonymous_profile_id: int
    alias: str
    country: str | None


def pseudonymise_profile(profile_id: int) -> ProfilePseudonymisation:
    """The pseudonymisation plan for `profile_id` — deterministic and side-effect free (module
    docstring): the same `profile_id` always yields the same placeholder, so a caller may call
    this as many times as its own retry discipline needs without ever producing two different
    answers for the one real profile.
    """
    return ProfilePseudonymisation(
        pseudonymous_profile_id=-abs(profile_id),
        alias=PSEUDONYMISED_ALIAS,
        country=None,
    )
