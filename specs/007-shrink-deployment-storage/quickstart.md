# Quickstart: validating feature 007

Run from the repository root of a checkout of the feature branch. §1–§3 need no host access; §4–§6
are the production acceptance and need the host's dashboard. Expected outcomes reference
`contracts/` and `research.md` rather than restating them.

## 0. Before merging: record the before value

In the host's dashboard, for the **current** production deployment:

1. Deployment → Resources → Functions: note each function's size.
2. Usage → Deployment Storage → Functions Storage → Projects: note this project's figure.

Record both in `docs/adr/0002-hosting.md` with the date and the deployment id (research R7). Do this
first: the deployment may no longer exist by the time the feature lands.

## 1. Offline gates

```bash
uv run pytest -q
```

The whole suite, including the bundle-shaped dry run (`tests/architecture/test_deployment_install.py`,
research R8) and the `excludeFiles` guard (`scripts/checks/tests/test_vercel_bundle.py`). Expected:
exit 0.

```bash
node --test scripts/deploy/ignore-build.test.mjs
```

Expected: every recorded-history fixture and throwaway-repository case passes (research R4).

```bash
node scripts/checks/spa-routing.mjs
```

Expected: exit 0, with `/api/analyze` and `/api/cron/ingest` each resolving by the filesystem to
its own file ahead of `/api/(.*)`
(`contracts/function-layout.md`, invariant 2).

```bash
uv run scripts/checks/api_entrypoint_deps.py
```

Expected: exit 0 over all three files under `api/`.

## 2. `pip` is gone

```bash
uv export --frozen --no-dev --no-editable --no-hashes | grep -i '^pip'
```

Expected: one line, carrying the marker `sys_platform == 'never'` (research R5). Then check that a
non-editable production sync installs no `pip`; the dry run in §1 already asserts it.

## 3. A CLI upload carries no `.claude/`

From a working copy that has local agent worktrees under `.claude/worktrees/`:

```bash
vercel deploy --dry --format=json > /tmp/after.json
```

Compare it with the same command run on `main` (`/tmp/before.json`). Expected: the only paths that
moved to `ignored` are under `.claude/`, and no other file dropped (FR-015, research R9). This needs
the CLI's login and deploys nothing.

## 4. The skip rule in production

After the feature has merged and its own full deployment is live:

1. Push a commit to `main` that touches only `docs/`. Expected: the deployment shows **Canceled**,
   and its build log carries `skip: nothing shipped between <base> and <head> …`, with `<base>` the
   feature's merge commit (`contracts/build-skip-rule.md`, Output).
   - If the log instead shows `build: …` because the comparison base was empty, the host is not
     providing it (research R3, known risk). Record that in the ADR; the rule stays, safe and inert.
2. Push a commit to `main` that touches `uv.lock`. Expected: a full deployment, and the log carries
   `build: uv.lock …`.
3. Optional, costs one deployment: redeploy the latest production deployment from the dashboard.
   Record in the ADR whether the rule ran and what it printed (`contracts/build-skip-rule.md`,
   "Forcing a deploy").

## 5. The three functions answer

Against the first production deployment that carries the feature:

1. The `Production smoke` workflow for that push passes.
2. Request an analysis from the site while signed in (or `POST /api/analyze` with a valid session).
   Expected: the analysis completes, or is refused with its documented error, as before the feature.
3. Trigger the ingestion run by hand:

   ```bash
   curl -sS -X POST -H "Authorization: Bearer $CRON_SECRET" https://aoe2-stats.com/api/cron/ingest
   ```

   `$CRON_SECRET` is the production value from the dashboard; do not paste it into a file. Expected:
   a JSON run report from `run_once`, not a 504, and no `unauthorized`.

4. The next scheduled run at 04:00 UTC appears in the host's cron log with a 200 and in the
   project's capture audit as a normal run.
5. Deployment → Resources → Functions lists **three** functions, as before.

## 6. Record the after value

Repeat §0 for the deployment from §5. Record the values, the ratio to §0, and the date in
`docs/adr/0002-hosting.md`. SC-002 holds when the per-deployment ratio is inside the band research §0
gives. Thirty days later, add the number of canceled deployments and whether any shipped commit was
skipped (SC-006).
