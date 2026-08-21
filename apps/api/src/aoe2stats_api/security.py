"""Server-side sessions (T028): opaque identifiers, a signed cookie, and the CSRF `state` the
Steam sign-in flow relies on.

**The cookie name.** `contracts/http-api.md` and four US1 integration tests (T021, T023, T024,
T025) all needed a name before this task existed to fix it, and converged on ``session_id`` as a
provisional, explicitly-flagged assumption — chosen to mirror ``sessions.id``, the column the
cookie's value ultimately round-trips to (data-model.md). This module makes that choice
authoritative: ``SESSION_COOKIE_NAME`` below, and its counterpart entry in
``specs/001-steam-link-replay-ingestion/contracts/http-api.md``, are now the one place either
value is decided.

**What "signed" buys on top of "opaque".** research.md §3: "A signed, ``HttpOnly``, ``Secure``,
``SameSite=Lax`` cookie holding an opaque session identifier, with session state in Postgres."
The opaque identifier (`generate_session_id`, 256 bits) is already unguessable on its own — the
signature is not what makes the session hard to forge, the database lookup in
`get_active_session` is. What it buys instead is *fast, cheap rejection of a cookie that was
never ours*: a tampered or fabricated cookie value fails `_unsign` before a single query is
issued, rather than spending a database round trip (and a row in whatever logs that round trip)
on a value with no chance of matching. `_sign`/`_unsign` below implement this directly —
``<raw-value>.<hmac-sha256-of-raw-value>``, base64url with padding stripped — rather than pulling
in a cookie-signing dependency for what is sixty lines of ``hmac``, the same call research.md §2
already made for Steam's OpenID handshake.

**Revocation is real, not cookie theatre.** `get_active_session` is a query, evaluated fresh on
every request: `revoke_session` (sign-out; and later, T091's erasure) sets `revoked_at` and the
very next request — cookie signature intact, ``Secure``, ``HttpOnly`` and all — resolves to no
session at all. A self-contained token (a JWT, an encrypted blob) cannot do this without an
additional revocation list that duplicates exactly what the `sessions` table already is
(research.md §3, "Alternatives considered").

**The CSRF `state` is tied to the browser, not to a signed-in user.** `GET /api/auth/steam/start`
runs before any session exists — that is the flow this `state` protects — so it cannot be tied to
`sessions.id`. Instead `issue_csrf_state_cookie` mints one, sets it on its own short-lived signed
cookie (``CSRF_STATE_COOKIE_NAME``), and returns the raw value for the caller to embed in the
outbound ``return_to``/``state`` Steam is asked to echo back. `verify_csrf_state` then accepts a
callback only if the value it carries matches what *this browser's own cookie* says was minted for
it: a `state` issued to one browser is never present in another browsers's `Cookie:` header, so it
can never be replayed there (research.md §2, "A `state` value tied to the browser session guards
the callback against CSRF").

**Single-use and expiry are enforced server-side, in the `csrf_states` table — not merely by the
cookie (T028b).** Both properties look, at a glance, like something the cookie already gives for
free: `clear_csrf_state_cookie` deletes it on every callback, and `max_age=CSRF_STATE_TTL` bounds
how long a browser keeps offering it. Neither is actually a guarantee this service makes, because
both live entirely in the client: a browser (or a captured cookie replayed with a crafted `Cookie:`
header, `HttpOnly` notwithstanding on the wire) is free to keep sending a cookie this module told it
to delete, and free to ignore `max-age` altogether. `issue_csrf_state_cookie` now also inserts a row
into `csrf_states` alongside the cookie, and `verify_csrf_state` consumes it with a single
conditional `UPDATE ... WHERE consumed_at IS NULL AND expires_at > now`: the *database's* row, not
the *client's* cookie, is what decides whether a `state` may still be spent. A second callback
carrying the identical `state` — cookie intact, signature intact — now fails here, and so does one
whose `expires_at` has passed even though it was never used at all. This is the discipline sessions
already had (`get_active_session`, below, is a query re-evaluated on every request, not a claim the
cookie gets to make); the CSRF `state` had it backwards until this task, granting the browser a
guarantee that belonged to the service.

This module is deliberately decoupled from `aoe2stats_api.settings.Settings` — every function
below takes a plain `secret: str`, the same discipline `packages/storage`'s `build_engine` and
`ObjectStore` already follow (`deps.py`'s docstring: "settings meet storage here and nowhere
else"). The auth router (T029) is expected to pass `settings.app_secret_key.get_secret_value()`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import CsrfState as CsrfStateRow
from aoe2stats_storage.models import Session as SessionRow

# --- Names, decided here and nowhere else -------------------------------------------------------

#: `contracts/http-api.md`'s authoritative answer to "what is the session cookie called" —
#: mirrors `sessions.id`, the column its (unsigned) value round-trips to.
SESSION_COOKIE_NAME = "session_id"

#: The short-lived cookie `GET /api/auth/steam/start` sets to carry the CSRF `state` (research.md
#: §2) until the callback returns. Distinct from `SESSION_COOKIE_NAME`: this one exists before,
#: and independently of, any signed-in session.
CSRF_STATE_COOKIE_NAME = "steam_oauth_state"

# --- Lifetimes -----------------------------------------------------------------------------------

#: No requirement in spec.md pins a session lifetime; 30 days matches every US1 integration test
#: that already seeds a `sessions` row directly (test_multi_account.py, test_unlink.py).
SESSION_TTL = timedelta(days=30)

#: The Steam OpenID round trip is two redirects and a form post; a browser that has not completed
#: it within ten minutes has abandoned the attempt, and the `state` should not still be usable if
#: it comes back later.
CSRF_STATE_TTL = timedelta(minutes=10)

# --- Entropy -------------------------------------------------------------------------------------

#: data-model.md, `sessions.id`: "Opaque, 256 bits of randomness." `secrets.token_urlsafe(n)`
#: draws `n` random bytes, so 32 is the 256-bit floor, not a token *length* of 32 characters.
_SESSION_ID_ENTROPY_BYTES = 32
_CSRF_STATE_ENTROPY_BYTES = 32

_SIGNATURE_SEPARATOR = "."


def generate_session_id() -> str:
    """A fresh opaque session identifier: 256 bits of randomness, never derived from anything
    about the user (data-model.md)."""
    return secrets.token_urlsafe(_SESSION_ID_ENTROPY_BYTES)


def generate_csrf_state() -> str:
    """A fresh opaque CSRF `state` value, the same entropy floor as a session id."""
    return secrets.token_urlsafe(_CSRF_STATE_ENTROPY_BYTES)


# --- Signing: detect a tampered or fabricated cookie before it ever reaches the database ---------


def _sign(value: str, secret: str) -> str:
    """`<value>.<base64url(hmac_sha256(secret, value))>`, padding stripped. `value` itself is
    never base64-encoded or otherwise transformed — both `generate_session_id` and
    `generate_csrf_state` already produce a URL-safe, dot-free string (`secrets.token_urlsafe`'s
    own alphabet), so it round-trips unmodified through a `Set-Cookie` header."""
    signature = hmac.new(secret.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{value}{_SIGNATURE_SEPARATOR}{encoded_signature}"


def _unsign(signed_value: str, secret: str) -> str | None:
    """The inverse of `_sign`, or `None` for anything that is not exactly one of this module's
    own signed values under `secret` — malformed shape, wrong secret, or a flipped character
    anywhere in either half all fail the same way, on purpose: this is a well-formedness check,
    not a diagnostic, and none of those failure modes should be distinguishable to a caller."""
    value, separator, encoded_signature = signed_value.rpartition(_SIGNATURE_SEPARATOR)
    if not separator or not value or not encoded_signature:
        return None
    padding = "=" * (-len(encoded_signature) % 4)
    try:
        signature = urlsafe_b64decode(encoded_signature + padding)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        return None
    return value


# --- The session cookie --------------------------------------------------------------------------


def issue_session_cookie(response: Response, session_id: str, secret: str) -> None:
    """Set the session cookie on `response`: signed, `HttpOnly`, `Secure`, `SameSite=Lax`
    (research.md §3), scoped to the whole application."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_sign(session_id, secret),
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie immediately — the client-side half of sign-out. The server-side
    half is `revoke_session`; a caller must do both, since deleting only the cookie leaves the
    `sessions` row alive for anyone who already captured the value (constitution VIII)."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


def read_session_id(cookie_value: str | None, secret: str) -> str | None:
    """The opaque session id carried by a `Cookie:` header value, or `None` if it is absent,
    malformed, or does not verify under `secret`. Verifying the signature here is only ever a
    cheap rejection of a value that was never ours — whether the id it names still identifies a
    live session is `get_active_session`'s question, not this function's."""
    if not cookie_value:
        return None
    return _unsign(cookie_value, secret)


# --- The CSRF `state` cookie, tied to the browser and not to any session -------------------------


async def issue_csrf_state_cookie(
    response: Response, secret: str, db_session: AsyncSession, *, now: datetime | None = None
) -> str:
    """Mint a fresh CSRF `state`, set it (signed) on `CSRF_STATE_COOKIE_NAME`, insert its
    server-side tracking row (T028b: `csrf_states`, `CSRF_STATE_TTL` from now), and return the raw
    value for the caller to embed in the outbound Steam request. The state this returns, the state
    this cookie carries, and the state `csrf_states.id` now names are the same value by
    construction — `verify_csrf_state` is what ties all three back together on the way back.

    Not committed here, by the same discipline `create_session` documents: the caller's
    request-scoped `session_scope` (`aoe2stats_api.deps.get_session`) commits it.
    """
    moment = now or datetime.now(UTC)
    state = generate_csrf_state()
    db_session.add(CsrfStateRow(id=state, created_at=moment, expires_at=moment + CSRF_STATE_TTL))
    response.set_cookie(
        key=CSRF_STATE_COOKIE_NAME,
        value=_sign(state, secret),
        max_age=int(CSRF_STATE_TTL.total_seconds()),
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return state


def clear_csrf_state_cookie(response: Response) -> None:
    """Expire the CSRF `state` cookie — the client-side half of single-use. The server-side half,
    the one this service can actually rely on, is the `csrf_states` row `verify_csrf_state`
    consumes (T028b): a browser that ignores this and keeps sending the cookie anyway still finds
    the `state` it names already spent."""
    response.delete_cookie(
        key=CSRF_STATE_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


async def verify_csrf_state(
    cookie_value: str | None,
    callback_state: str | None,
    secret: str,
    db_session: AsyncSession,
    *,
    now: datetime | None = None,
) -> bool:
    """Whether `callback_state` — the value the Steam callback carries back — both matches the
    `state` minted for *this browser* and is still a live, unconsumed `csrf_states` row (T028b).

    Two checks, in order, each independently sufficient to reject: first, that `callback_state`
    matches what *this browser's own cookie* (`cookie_value`) says was minted for it — a `state`
    minted for one browser is never present in another browser's `Cookie:` header, so it can never
    be replayed there (research.md §2). Second, that the database still considers this `state`
    spendable: `False` for a missing cookie, a missing callback value, a cookie that does not
    verify under `secret` (the same undifferentiated rejection `_unsign` already gives a tampered
    session cookie), or a `state` that this exact `UPDATE` cannot mark consumed because it was
    already consumed, never issued, or has outlived `expires_at` — whatever the cookie, which does
    not control any of that, still claims. The `UPDATE`'s own `WHERE` clause is what makes this
    safe under two concurrent callbacks racing the identical `state`: at most one of them updates
    the row and gets `True` back, never both.
    """
    if not cookie_value or not callback_state:
        return False
    expected = _unsign(cookie_value, secret)
    if expected is None:
        return False
    if not hmac.compare_digest(expected, callback_state):
        return False

    moment = now or datetime.now(UTC)
    result = cast(
        CursorResult[Any],
        await db_session.execute(
            update(CsrfStateRow)
            .where(
                CsrfStateRow.id == callback_state,
                CsrfStateRow.consumed_at.is_(None),
                CsrfStateRow.expires_at > moment,
            )
            .values(consumed_at=moment)
        ),
    )
    return result.rowcount == 1


# --- The `sessions` table: creation, lookup, revocation ------------------------------------------


async def create_session(
    db_session: AsyncSession, *, user_id: UUID, now: datetime | None = None
) -> SessionRow:
    """Insert a fresh `sessions` row for `user_id`: opaque id, `SESSION_TTL` from now, no
    `revoked_at`. Not committed here — the caller's request-scoped `session_scope`
    (`aoe2stats_api.deps.get_session`) commits it, the same discipline every other write in this
    codebase follows; a caller outside a request (a test) commits its own `db_session` instead."""
    moment = now or datetime.now(UTC)
    session_row = SessionRow(
        id=generate_session_id(),
        user_id=user_id,
        created_at=moment,
        expires_at=moment + SESSION_TTL,
    )
    db_session.add(session_row)
    return session_row


async def get_active_session(
    db_session: AsyncSession, session_id: str, *, now: datetime | None = None
) -> SessionRow | None:
    """The `sessions` row `session_id` names, or `None` if it does not exist, has expired, or was
    revoked. This is the query that makes revocation real: a row `revoke_session` has touched, or
    one whose `expires_at` has simply passed, stops answering here on the very next call —
    whatever a cookie's own signature still says (research.md §3)."""
    moment = now or datetime.now(UTC)
    result = await db_session.execute(
        select(SessionRow).where(
            SessionRow.id == session_id,
            SessionRow.revoked_at.is_(None),
            SessionRow.expires_at > moment,
        )
    )
    return result.scalar_one_or_none()


async def revoke_session(
    db_session: AsyncSession, session_id: str, *, now: datetime | None = None
) -> None:
    """End a session immediately and server-side: `revoked_at` is set, so `get_active_session`
    stops returning this row starting with the very next call — sign-out (T029) and erasure
    (T091) both rely on exactly this. A no-op, not an error, for an id that does not exist or was
    already revoked: revocation is idempotent by nature."""
    moment = now or datetime.now(UTC)
    await db_session.execute(
        update(SessionRow)
        .where(SessionRow.id == session_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=moment)
    )
