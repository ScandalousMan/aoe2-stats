"""The auth router: `GET /api/auth/steam/start`, `GET /api/auth/steam/callback`,
`POST /api/auth/signout`, `GET /api/me`.

Ties together `security.py` (T028, sessions and the CSRF `state` cookie), `SteamAuthProvider`
(T026) and `RelicProfileProvider` (T027) into the one flow `contracts/http-api.md`'s
Authentication section describes, plus the closed-beta allowlist (T030, FR-005, below) and the
backfill request stamped on every successful link (T031a, below).

**Why `state` is embedded in `return_to`'s own query string, not left as `begin()`'s throwaway
top-level parameter.** `security.py`'s own docstring is explicit that the CSRF `state` is "embedded
in the outbound `return_to`" — and Steam's OpenID implementation does not echo back any parameter
that is not part of `return_to` itself (`packages/providers/src/aoe2stats_providers/steam/
provider.py`'s module docstring: "Steam does not echo unrecognised parameters back"). The only
place a value can survive the round trip to Steam and back is inside `return_to`'s own query,
which Steam preserves verbatim and appends its own `openid.*` fields onto. `SteamAuthProvider.
verify()` compares `openid.return_to` against the exact string the provider instance was built
with (`packages/providers/tests/test_steam.py`: this is a real, already-green behaviour, not
advisory) — so this module builds a **fresh, lightweight `SteamAuthProvider` per request**,
reusing the one process-wide `httpx.Client`/rate limiter (the actually expensive resources), with
`return_to` reconstructed from *this* request's own `state` (and, when present, `link`) query
parameters. A tampered `state` or `link` value changes the reconstructed `return_to`, which no
longer matches what Steam actually signed — caught by `check_authentication`, never by trusting the
client's own claim.

**`link=1` survives the same way.** `contracts/http-api.md`: "Accepts `?link=1` when already
signed in, to add a second Steam account rather than replace the session." Whether this flow is a
link or a fresh sign-in must survive the redirect to Steam and back exactly like `state` does, so it
travels the identical path — folded into `return_to`'s query, protected by the same signature Steam
computes over `openid.signed`'s `return_to` entry. No second cookie, no server-side flow table.

**CSRF binding is cookie-presence, not a second independently-sourced token beyond `state`
itself.** `verify_csrf_state(cookie_value, callback_state, secret)` compares the raw `state` this
request's own query carries (extracted independently of `openid.return_to`'s field, directly from
`request.query_params`) against what the signed `steam_oauth_state` cookie says was minted for
*this browser* (`security.py`). A captured, genuine callback URL replayed against a browser that
never completed its own `/start` — or completed a different one — carries no matching cookie and is
rejected before `SteamAuthProvider.verify()` is ever called, which is also what makes an exact
replay of an already-consumed callback fail: the cookie is single-use, cleared on every callback
this router answers (`clear_csrf_state_cookie`), successful or not.

**The closed-beta allowlist (T030, FR-005) is enforced once `SteamAuthProvider.verify()` has
returned a Steam id this router actually trusts:** `not link_mode and existing_identity is None
and steam_id64 not in settings.beta_allowlist_steam_ids` raises `not_allowlisted` before anything
is written. `link_mode` and an already-linked identity are both exempt — FR-005 restricts
**account creation**, and neither case creates one: an existing user who returns, or who links a
second Steam identity to the account they already have, is unaffected by whatever the allowlist
currently says. This is also where `users.allowlisted_at` gets stamped, on the very `User` row
this same branch inserts — the first sign-in that ever passed this gate for that identity.

A CSRF-state failure never reaches this gate: it is rejected earlier, with the generic
`steam_assertion_invalid`, before any Steam id is trusted (T030a — an earlier version of this
router answered a CSRF failure by reading `openid.claimed_id` unverified off the query string and
checking *that* against the allowlist, which let anyone learn a Steam id's allowlist status with
no signature, no session and no valid state; deleted for exactly that reason, along with the test
that could only reach it by skipping `/start`).

**The backfill request (T031a, FR-015, SC-003)** is stamped on every `ProfileLink` this module
inserts, `backfill_requested_at = now`, whether that row is a brand-new link or a relink of a
profile that was previously unlinked — both take the same `existing_link is None` branch below,
because the partial unique index (`data-model.md`: `UNIQUE (profile_id) WHERE unlinked_at IS
NULL`) means a relink always creates a fresh row rather than resurrecting the old one. This module
cannot enqueue the sweep itself: a `replay_captures` row's deadline is computed from
`matches.completed_at` (T053), and there are no `matches` rows yet for a profile nobody has ever
polled. The flag is how a link asks the next ingestion cycle to do the sweep it cannot do itself —
T054 reads it, enqueues the preceding 31 days, and clears it only once that sweep has actually run,
so an interrupted cycle repeats it rather than skipping it. A link that failed to stamp this would
silently lose everything the player played before signing up, which is exactly the loss this whole
feature exists to prevent.

**Ratings are resolved here, not deferred** (T033's `RatingsRepository.record_snapshot`): FR-009
requires the rating history to start accumulating from the first sign-in, and sign-in is the one
moment this feature already talks to Relic. The same call answers `resolve_profile` failing
gracefully into `no_aoe2_profile` (FR-003) and the profile-conflict checks FR-045 requires — no
step here ever infers a relationship between two profiles it has not itself just proven by a
completed sign-in.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.settings import Settings
from aoe2stats_providers.base import ProviderCallRecord
from aoe2stats_providers.relic.profile import RelicProfileProvider
from aoe2stats_providers.steam.provider import SteamAuthProvider
from aoe2stats_providers.wiring import build_async_client_resources, build_sync_client_resources
from aoe2stats_storage.models import AoeProfile, ProfileLink, ProviderCall, SteamIdentity, User
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.ratings import RatingsRepository

router = APIRouter(tags=["auth"])

#: The full path (including the `/api` prefix this router is mounted under, `app.py`) — needed as
#: a literal string because it is embedded in `return_to`, never taken from `request.url_for`: the
#: value Steam echoes back must match byte-for-byte what this module itself constructed.
_CALLBACK_PATH = "/api/auth/steam/callback"

# Interactive sign-in traffic, not the daily bulk cycle `AOEMS_MAX_REQUESTS_PER_SECOND` governs
# (`.env.example`) — a closed beta of a handful of concurrent sign-ins never approaches either
# figure, so these are generous, fixed constants rather than a settings knob nothing else needs.
_PROVIDER_TIMEOUT_SECONDS = 10.0
_STEAM_RATE_PER_SECOND = 5.0
_RELIC_RATE_PER_SECOND = 5.0


# --- Provider construction: expensive resources built once per process, thin wrappers per call ---
#
# `build_sync_client_resources`/`build_async_client_resources` (`aoe2stats_providers.wiring`) are
# what let this module build these without ever writing `import httpx` itself:
# `tests/architecture/test_import_graph.py` enforces constitution III — "apps/* ... never
# [depends] on ... an HTTP client" (`contracts/providers.md`) — by scanning every file under
# `apps/api/src` for exactly that import, so the client object every provider's constructor
# requires has to be built inside `packages/providers`, the one place a network client is allowed
# to live, and merely *held* here.

_STEAM_HTTP_CLIENT, _STEAM_RATE_LIMITER = build_sync_client_resources(_STEAM_RATE_PER_SECOND)
_RELIC_HTTP_CLIENT, _RELIC_RATE_LIMITER = build_async_client_resources(_RELIC_RATE_PER_SECOND)


def _sync_call_sink(db_session: AsyncSession) -> Callable[[ProviderCallRecord], None]:
    """Writes a `provider_calls` row through `db_session.add` — no `await` needed, since `add`
    performs no I/O itself; the request's own `session_scope` (`deps.py`) flushes it."""

    def _sink(record: ProviderCallRecord) -> None:
        db_session.add(
            ProviderCall(
                provider=record.provider,
                endpoint=record.endpoint,
                status_code=record.status_code,
                duration_ms=record.duration_ms,
                called_at=record.called_at,
                rate_limited=record.rate_limited,
            )
        )

    return _sink


def _async_call_sink(db_session: AsyncSession) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    async def _sink(record: ProviderCallRecord) -> None:
        db_session.add(
            ProviderCall(
                provider=record.provider,
                endpoint=record.endpoint,
                status_code=record.status_code,
                duration_ms=record.duration_ms,
                called_at=record.called_at,
                rate_limited=record.rate_limited,
            )
        )

    return _sink


def _build_steam_provider(*, return_to: str, db_session: AsyncSession) -> SteamAuthProvider:
    """A fresh, lightweight `SteamAuthProvider` for exactly this request's `return_to` — see the
    module docstring for why `return_to` cannot be a single process-wide constant here."""
    return SteamAuthProvider(
        client=_STEAM_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_STEAM_RATE_LIMITER,
        return_to=return_to,
        call_sink=_sync_call_sink(db_session),
    )


def _build_relic_provider(db_session: AsyncSession) -> RelicProfileProvider:
    return RelicProfileProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_RELIC_RATE_LIMITER,
        call_sink=_async_call_sink(db_session),
    )


# --- `return_to` construction, shared by /start and /callback ------------------------------------


def _build_return_to(base_url: str, *, state: str, link: bool) -> str:
    """The exact `return_to` this deployment asks Steam to echo back: the callback path, `state`
    (the CSRF binding), and `link=1` only when this is a link-a-second-account flow. Built the
    same way at mint time (`start`) and at reconstruction time (`callback`) so the two agree
    byte-for-byte whenever nothing was tampered with (module docstring).
    """
    params: dict[str, str] = {"state": state}
    if link:
        params["link"] = "1"
    return f"{base_url}{_CALLBACK_PATH}?{urlencode(params)}"


def _error_redirect(response: Response, settings: Settings, code: str) -> Response:
    """302 back into the app carrying `?error=<code>` — the shape `contracts/http-api.md`'s
    documented failure codes `steam_assertion_invalid`, `no_aoe2_profile`, `profile_already_linked`
    and `not_allowlisted` are all delivered in. `not_allowlisted` (T030, T030b) joins the other
    three here rather than answering the plain JSON error envelope: the caller mid-callback is a
    browser following a redirect chain from Steam, not an API client, and T036's sign-in screen now
    has a `not_allowlisted` outcome — with its explanation and its retry — to send it back into.
    A JSON body at an API address told a developer, not the rejected visitor FR-005 means to
    inform."""
    response.status_code = 302
    response.headers["location"] = f"{settings.public_base_url}/?{urlencode({'error': code})}"
    return response


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — `security.read_session_id` rejects the first two before ever touching the database,
    `security.get_active_session` the last two (security.py)."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


# --- GET /api/auth/steam/start --------------------------------------------------------------------


@router.get("/auth/steam/start")
async def start(request: Request, db_session: SessionDep, settings: SettingsDep) -> Response:
    link_mode = request.query_params.get("link") == "1"
    secret = settings.app_secret_key.get_secret_value()

    if link_mode:
        # Adding a second Steam account only means something for an already-signed-in caller
        # (contracts/http-api.md); checked here, before ever redirecting to Steam, rather than
        # only at the callback, so a signed-out caller is told immediately rather than after a
        # detour through Steam's own sign-in page.
        session_row = await _current_session_row(request, db_session, secret)
        if session_row is None:
            raise APIError(
                status_code=401,
                code="not_authenticated",
                message="Sign in before linking another Steam account.",
            )

    response = Response(status_code=302)
    state = security.issue_csrf_state_cookie(response, secret)
    return_to = _build_return_to(settings.public_base_url, state=state, link=link_mode)
    steam_provider = _build_steam_provider(return_to=return_to, db_session=db_session)
    response.headers["location"] = steam_provider.begin(return_to, state)
    return response


# --- GET /api/auth/steam/callback -----------------------------------------------------------------


@router.get("/auth/steam/callback")
async def callback(request: Request, db_session: SessionDep, settings: SettingsDep) -> Response:
    secret = settings.app_secret_key.get_secret_value()
    now = datetime.now(UTC)

    # The CSRF cookie is single-use regardless of outcome (module docstring): cleared on the
    # response this handler builds no matter which branch below is eventually taken.
    response = Response(status_code=302)
    security.clear_csrf_state_cookie(response)

    incoming_state = request.query_params.get("state")
    link_mode = request.query_params.get("link") == "1"
    csrf_cookie = request.cookies.get(security.CSRF_STATE_COOKIE_NAME)

    if not security.verify_csrf_state(csrf_cookie, incoming_state, secret):
        return _error_redirect(response, settings, "steam_assertion_invalid")
    # `verify_csrf_state` already rejects a `None` `incoming_state` (security.py), so it is a
    # plain `str` from here on — asserted for mypy rather than defended against again.
    assert incoming_state is not None

    return_to = _build_return_to(settings.public_base_url, state=incoming_state, link=link_mode)
    steam_provider = _build_steam_provider(return_to=return_to, db_session=db_session)
    # Only the `openid.*` fields go to `verify()` (and, inside it, back to Steam's own
    # `check_authentication`): `state` and `link` are this router's own addition to `return_to`
    # (module docstring), never something Steam signed or expects echoed back to it.
    callback_params = {
        key: value for key, value in request.query_params.items() if key.startswith("openid.")
    }
    steam_id64 = steam_provider.verify(callback_params)
    if steam_id64 is None:
        return _error_redirect(response, settings, "steam_assertion_invalid")

    link_target_user_id: uuid.UUID | None = None
    if link_mode:
        session_row = await _current_session_row(request, db_session, secret)
        if session_row is None:
            return _error_redirect(response, settings, "not_authenticated")
        link_target_user_id = session_row.user_id

    existing_identity = await db_session.get(SteamIdentity, steam_id64)

    # T030 (FR-005): the closed beta gates account *creation* only. `link_mode` never creates a
    # new aoe2-stats account (it attaches a second identity to the caller's existing session), and
    # an identity that already owns an account is a returning sign-in, not a new one — both are
    # unaffected by whatever `BETA_ALLOWLIST_STEAM_IDS` currently contains. Checked here, before
    # `resolve_profile` below, so a visitor this closed beta will refuse never costs a Relic call.
    if (
        not link_mode
        and existing_identity is None
        and steam_id64 not in settings.beta_allowlist_steam_ids
    ):
        return _error_redirect(response, settings, "not_allowlisted")

    if link_mode:
        assert link_target_user_id is not None
        if existing_identity is not None and existing_identity.user_id != link_target_user_id:
            return _error_redirect(response, settings, "profile_already_linked")
        user_id = link_target_user_id
    elif existing_identity is not None:
        user_id = existing_identity.user_id
    else:
        user_id = uuid.uuid4()

    relic_provider = _build_relic_provider(db_session)
    profile_ref = await relic_provider.resolve_profile(steam_id64)
    if profile_ref is None:
        return _error_redirect(response, settings, "no_aoe2_profile")

    # A second, profile-level conflict check, independent of the identity-level one above: the
    # same AoE2 profile must never end up linked to two different accounts, whichever row a future
    # inconsistency would otherwise let slip through (FR-045).
    link_result = await db_session.execute(
        select(ProfileLink).where(
            ProfileLink.profile_id == profile_ref.profile_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    existing_link = link_result.scalar_one_or_none()
    if existing_link is not None and existing_link.user_id != user_id:
        return _error_redirect(response, settings, "profile_already_linked")

    # Every write below happens only once every rejection above has already returned — no row is
    # ever created for a flow that ends in an error.
    if existing_identity is None:
        if not link_mode:
            # The allowlist gate above already guarantees `steam_id64 in settings.
            # beta_allowlist_steam_ids` for every `User` row created here — this is the first
            # sign-in that ever passed it for this identity, which is exactly what
            # `allowlisted_at` records (data-model.md: "Null means the closed beta refuses them").
            db_session.add(User(id=user_id, created_at=now, allowlisted_at=now))
        db_session.add(
            SteamIdentity(
                steam_id64=steam_id64, user_id=user_id, verified_at=now, last_sign_in_at=now
            )
        )
    else:
        existing_identity.verified_at = now
        existing_identity.last_sign_in_at = now

    profile = await db_session.get(AoeProfile, profile_ref.profile_id)
    if profile is None:
        db_session.add(
            AoeProfile(
                profile_id=profile_ref.profile_id,
                alias=profile_ref.alias,
                country=profile_ref.country,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    else:
        profile.alias = profile_ref.alias
        profile.country = profile_ref.country
        profile.last_seen_at = now

    if existing_link is None:
        active_links = await db_session.scalar(
            select(func.count())
            .select_from(ProfileLink)
            .where(ProfileLink.user_id == user_id, ProfileLink.unlinked_at.is_(None))
        )
        db_session.add(
            ProfileLink(
                id=uuid.uuid4(),
                user_id=user_id,
                profile_id=profile_ref.profile_id,
                steam_id64=steam_id64,
                is_primary=(not active_links),
                linked_at=now,
                # FR-015, SC-003 (module docstring): this link cannot enqueue the 31-day sweep
                # itself, since no `matches` rows exist yet for a profile nobody has ever polled.
                # T054 consumes this flag and clears it once the sweep has actually run.
                backfill_requested_at=now,
            )
        )

    # FR-009: the rating history starts accumulating from the first sign-in.
    ratings_repo = RatingsRepository(db_session)
    for snapshot in await relic_provider.personal_stats([profile_ref.profile_id]):
        await ratings_repo.record_snapshot(
            profile_id=snapshot.profile_id,
            leaderboard_id=snapshot.leaderboard_id,
            rating=snapshot.rating,
            rank=snapshot.rank,
            wins=snapshot.wins,
            losses=snapshot.losses,
            streak=snapshot.streak,
            highest_rating=snapshot.highest_rating,
            captured_at=now,
        )

    if not link_mode:
        # A plain sign-in always ends with a fresh session for whichever user this identity
        # belongs to — replacing the caller's previous session rather than extending it
        # (contracts/http-api.md: "`?link=1`... to add a second Steam account rather than replace
        # the session" implies the plain path does replace it).
        previous_session_id = security.read_session_id(
            request.cookies.get(security.SESSION_COOKIE_NAME), secret
        )
        if previous_session_id is not None:
            await security.revoke_session(db_session, previous_session_id)
        new_session = await security.create_session(db_session, user_id=user_id)
        security.issue_session_cookie(response, new_session.id, secret)

    response.headers["location"] = f"{settings.public_base_url}/"
    return response


# --- POST /api/auth/signout -----------------------------------------------------------------------


@router.post("/auth/signout")
async def signout(request: Request, db_session: SessionDep, settings: SettingsDep) -> Response:
    secret = settings.app_secret_key.get_secret_value()
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is not None:
        await security.revoke_session(db_session, session_id)

    response = Response(status_code=200)
    security.clear_session_cookie(response)
    return response


# --- GET /api/me ---------------------------------------------------------------------------------


@router.get("/me")
async def me(request: Request, db_session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """`contracts/http-api.md`: "Session, allowlist state, consent state, linked profiles, which
    is primary" — and 200 with `{"authenticated": false}`, never 401, when signed out, since this
    is the front end's bootstrap call."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = await _current_session_row(request, db_session, secret)
    if session_row is None:
        return {"authenticated": False}

    links_result = await db_session.execute(
        select(ProfileLink, AoeProfile)
        .join(AoeProfile, ProfileLink.profile_id == AoeProfile.profile_id)
        .where(ProfileLink.user_id == session_row.user_id, ProfileLink.unlinked_at.is_(None))
        .order_by(ProfileLink.linked_at)
    )
    profiles = [
        {
            "profile_id": profile.profile_id,
            "alias": profile.alias,
            "country": profile.country,
            "is_primary": link.is_primary,
        }
        for link, profile in links_result.all()
    ]

    user = await db_session.get(User, session_row.user_id)
    # T037a: `ingest_consent_at is not None` alone was reported here for as long as this route
    # existed, which made `ingest_consent` true forever after the first grant — T032 (privacy.py,
    # data-model.md) deliberately never clears `ingest_consent_at` on withdrawal, since it is the
    # record of what was agreed and when, but that means it is *not* by itself the answer to "is
    # ingestion happening right now". The router's own selection query for that
    # (`ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL`, privacy.py's module
    # docstring, mirrored by the ingester's own row selection) is reproduced here so a withdrawn
    # consent is reported as withdrawn on the very next `GET /api/me` — the request a page reload
    # performs — rather than staying "granted" until the browser is told otherwise by some other
    # means. Both timestamps are returned alongside the derived boolean, in the same field names
    # `POST /api/privacy/consent` already answers with, so a reload can render "granted",
    # "declined" or "withdrawn, previously granted at ..." without the front end needing to hold
    # any consent state of its own between requests (`contracts/http-api.md`).
    ingest_consent_at = user.ingest_consent_at if user is not None else None
    ingest_consent_withdrawn_at = user.ingest_consent_withdrawn_at if user is not None else None
    return {
        "authenticated": True,
        "user_id": str(session_row.user_id),
        # `allowlisted_at` is stamped once, at account creation (T030) — reported here exactly
        # as the column holds it.
        "allowlisted": user.allowlisted_at is not None if user is not None else False,
        "ingest_consent": ingest_consent_at is not None and ingest_consent_withdrawn_at is None,
        "ingest_consent_at": ingest_consent_at.isoformat()
        if ingest_consent_at is not None
        else None,
        "ingest_consent_withdrawn_at": (
            ingest_consent_withdrawn_at.isoformat()
            if ingest_consent_withdrawn_at is not None
            else None
        ),
        "profiles": profiles,
    }
