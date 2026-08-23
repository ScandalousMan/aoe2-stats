"""Guards constitution V and plan.md's constitution-V row: importing the FastAPI application must
never load the replay engine (T018c).

`apps/api` depends on `apps/ingester` only so `routers/cron.py` can call `run_once()` for the
local trigger route (T018); from T055 onward `apps/ingester` depends on `packages/replay-engine`
for its capture stage, which pulls in `aoe2rec_py` — a PyO3 extension documented as able to raise
`BaseException` panics (`packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`). If any
module on the path from `aoe2stats_api.app` down to that adapter imported it at module scope, the
mere act of importing the ASGI app — which every cold start of the API function does, including
the ones that only ever serve `GET /api/health` — would load a C extension into the API process:
exactly what "the API never loads an engine at all" and "a parser crash affects neither the API
nor the ingester" forbid.

Run in a subprocess rather than checked against the current process's `sys.modules`. An in-process
assertion has two ways to lie: nothing in this suite imports `aoe2rec_py` today, so it would
trivially pass forever even after a regression that makes the *import chain* eager again — the
package genuinely does not exist below `aoe2stats_ingester.run` until T055 lands; and even once it
does, most files in this directory already import `aoe2stats_api.app` before this test runs in the
same pytest session, so a stale `sys.modules` entry from an earlier test would make a later,
regressed import look clean. A subprocess starts with an empty `sys.modules` every time, so this
is the only form of the assertion neither failure mode can dodge. The second assertion — that
`aoe2stats_ingester.run` itself is absent — is the one that is already meaningful today: it is red
against the code this task replaces (a module-scope `from aoe2stats_ingester.run import run_once`
in `routers/cron.py`) and green after it, which is the evidence this task actually changed
something rather than merely adding a check that starts and stays vacuously true.

003's `apps/analyzer` (T302) widens the boundary the same reasoning covers. `apps/api` declares no
dependency on it at all — `api/analyze.py` (Phase 7) is a separate Vercel function that calls
`apps/analyzer`'s own `run_once`, never `aoe2stats_api.app` — so nothing on the import path from
the ASGI app should ever reach `aoe2stats_analyzer`. That absence is not provable from the
dependency graph either: `apps/analyzer` also depends on `packages/replay-engine`, this time to
*extract* rather than merely validate (plan.md), and it sits in the same shared workspace
environment as `aoe2stats_api` — `uv sync --all-packages --dev` installs both into one venv, so
`aoe2stats_analyzer` is importable from `aoe2stats_api`'s process the moment someone writes the
import, whether or not `apps/api/pyproject.toml` ever declares it. A fourth assertion, run in the
same subprocess as the first three, closes that gap the same way: today it is vacuously true
because nothing in `apps/api/src` imports `aoe2stats_analyzer`, and it stays meaningful for the
same reason the second assertion does — a regression that reaches for it from a router would turn
this test red on the next run, in-process or not.
"""

from __future__ import annotations

import subprocess
import sys

_CHECK = (
    "import sys\n"
    "import aoe2stats_api.app\n"
    "assert 'aoe2stats_ingester.run' not in sys.modules, sorted(sys.modules)\n"
    "assert 'aoe2rec_py' not in sys.modules, sorted(sys.modules)\n"
    "assert 'aoe2stats_analyzer' not in sys.modules, sorted(sys.modules)\n"
    "print('ok')\n"
)


def test_importing_the_app_never_loads_run_once_or_the_replay_engine() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _CHECK],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok"
