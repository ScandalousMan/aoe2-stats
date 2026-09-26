"""T652b: keep `snapshot.py`'s newly cached build-resolution functions test-isolated.

`load_all_snapshots`, `load_resolvable_snapshots` and `snapshot_for` gained `functools.cache`
(T652b, finding (d): one `coverage()` call re-read and re-digested the packaged `snapshots/` tree
612 times over one committed recording, 1.47s, because nothing cached them the way
`query._rules`/`query._civilisations_modelled`/`effects._effects` already did). That caching is
correct and desired for a real process's lifetime — the packaged tree is immutable once committed
(FR-025) — but `test_snapshot.py` monkeypatches `snapshot._snapshots_root` to a fresh, ephemeral
`tmp_path` in most of its own tests, several of them reusing the same build number
(`snapshot_for(101102)`, for instance) against a *different* monkeypatched root each time. Left
uncleared, the first such test's cached answer would leak into the next — and, since these three
caches have no arguments distinguishing "real packaged tree" from "this test's tmp_path", into
every other package's tests that import `aoe2stats_knowledge` in the same pytest session
(`packages/replay-engine/tests/test_extract_limits.py` calls `coverage.coverage` for real).

Clearing both before and after every test in this package handles both directions: before, so a
prior test's monkeypatched result can never answer this one; after, so this package's own
monkeypatching can never answer a later test anywhere else in the same session. A real production
caller never monkeypatches `_snapshots_root`, so this fixture changes nothing about how long the
cache lives there — for the whole process, exactly as `query.py`'s and `effects.py`'s existing
caches already do.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from aoe2stats_knowledge import snapshot


@pytest.fixture(autouse=True)
def _clear_snapshot_resolution_caches() -> Iterator[None]:
    snapshot.load_all_snapshots.cache_clear()
    snapshot.load_resolvable_snapshots.cache_clear()
    snapshot.snapshot_for.cache_clear()
    yield
    snapshot.load_all_snapshots.cache_clear()
    snapshot.load_resolvable_snapshots.cache_clear()
    snapshot.snapshot_for.cache_clear()
