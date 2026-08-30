# Runbook: syncing the map thumbnail pack after a new map is added to the pool

`packages/game-assets/maps/` holds 435 hand-vendored WebP files, one per AoE2:DE lobby map — the
minimap preview `mapThumbnail()` resolves in `packages/game-assets/src/index.ts`. Age of Empires II
adds maps periodically (new DLC, a community map promoted into the ranked pool, an event map), and
each addition leaves the pack one file short until someone re-syncs it. This is that procedure.

**Source**: `SiegeEngineers/aoe2cm2`'s `public/images/maps/` — see `packages/game-assets/maps/
LICENCE.md` and `docs/asset-packs.md` for the full licence record (Microsoft "Game Content Usage
Rules", `COPY IN`) and `specs/004-visual-parity/research.md` **D9** for why this source and not a
higher-resolution one.

## Why the download is a manual step, never something the repository's own code does

Constitution: "No external network call outside `packages/providers`." `scripts/checks/
contract_sources.py`'s own module docstring names itself the _only_ check allowed to touch the
network, and this is not that check. `scripts/ops/sync_map_thumbnails.py` therefore takes a
**local** folder of already-downloaded source PNGs via `--source-dir` and does only the
deterministic, network-free half of the job — re-encode to WebP, compare against the committed
pack, report or write the difference. Fetching the source is Step 1 below, run by a human, outside
the repository, exactly how the pack was first vendored (`specs/004-visual-parity/tasks.md` T405).

## The 140 px limitation — read before reaching for a "sharper" source

aoe2cm2 ships these previews natively at 140×140. A higher-resolution mirror of the same asset
exists at `aoe2insights.com/static/images/maps/<slug>.png`, and it is **deliberately not used**:
the whole domain sits behind an interactive Cloudflare bot-challenge (`cf-mitigated: challenge`) —
a scripted fetch gets a 403 interstitial, a real browser gets a "verify you are human" checkbox —
and that challenge must not be bypassed, automated, or solved by any tool in this repository or by
a human acting on its behalf. If AoE2:DE is ever installed on a Windows machine, the game keeps
these previews as loose image files (not inside a `.drs`/`.sld` archive), so a higher-fidelity
local extraction is possible in principle — but it is a manual, by-hand copy on that machine, not
something this script or runbook automates, and it is out of scope until someone actually has that
machine. Until then, 140 px is the accepted resolution; see research.md D9 for the full
investigation.

## Procedure

### 1. Download the current aoe2cm2 map set to a local folder (outside the repository)

Either a plain `curl` loop against the raw file host, or a sparse git checkout. Either way, the
result should be a folder of `<slug>.png` files matching aoe2cm2's own naming — run this in a
scratch directory, never inside the repository working tree:

```sh
mkdir -p /tmp/aoe2cm2-maps && cd /tmp/aoe2cm2-maps
# List of slugs: derive from the current pack, or from a directory listing of aoe2cm2's
# public/images/maps/ (GitHub API: repos/SiegeEngineers/aoe2cm2/contents/public/images/maps).
ls /path/to/aoe2-stats/packages/game-assets/maps/*.webp \
  | xargs -n1 basename | sed 's/\.webp$//' > slugs.txt
cat slugs.txt | xargs -P 8 -I{} curl -sf -o "{}.png" \
  "https://raw.githubusercontent.com/SiegeEngineers/aoe2cm2/master/public/images/maps/{}.png"
```

For a map that was **added** to the pool since the last sync, its slug will not be in the existing
pack's file listing yet — add it to `slugs.txt` by hand (or download aoe2cm2's full directory
listing instead of deriving `slugs.txt` from the current pack) so its PNG is fetched too. A
sparse checkout of the whole `public/images/maps/` directory sidesteps this entirely:

```sh
git clone --filter=blob:none --sparse https://github.com/SiegeEngineers/aoe2cm2.git /tmp/aoe2cm2
cd /tmp/aoe2cm2 && git sparse-checkout set public/images/maps
# source folder is now /tmp/aoe2cm2/public/images/maps
```

This step is what keeps `scripts/ops/sync_map_thumbnails.py` and every other file committed to
this repository network-free, per the constitution rule above, and it is the same manual step
that originally vendored the pack.

### 2. Preview, then apply

From the repository root:

```sh
uv run scripts/ops/sync_map_thumbnails.py --source-dir /tmp/aoe2cm2-maps --dry-run
```

Read the report — `N unchanged, N added, N changed, N removed` — before writing anything. A sync
against an unmodified aoe2cm2 checkout reports **zero** changes: the script's WebP encoding
parameters (quality 80, method 6) were chosen to reproduce the committed pack byte-for-byte, so
"zero changes" is the expected steady state, not a sign the script did nothing. Seeing anything
under `changed` for a map you did not expect to have moved is worth investigating before applying
— it usually means aoe2cm2 itself re-rendered that preview upstream.

Once the preview looks right, write it:

```sh
uv run scripts/ops/sync_map_thumbnails.py --source-dir /tmp/aoe2cm2-maps --apply
```

A map removed from the pool (rare — this repository has not seen one yet) is reported under
`removable` either way, but only deleted when `--prune` is also passed:

```sh
uv run scripts/ops/sync_map_thumbnails.py --source-dir /tmp/aoe2cm2-maps --apply --prune
```

Leaving `--prune` off is the safer default for a routine sync: a `--source-dir` that is
accidentally partial (a failed download, a typo in `slugs.txt`) reports every missing map as
`removable` rather than silently deleting most of the pack.

The pack's coverage set is read from its own directory listing at build time
(`packages/game-assets/src/index.ts`'s `import.meta.glob`) — no separate manifest or list needs
updating after this step.

### 3. Bump the licence record if the set materially changed

`packages/game-assets/maps/LICENCE.md`'s **Checked** date, and the mirrored row in
`docs/asset-packs.md`, record when the pack's contents were last verified against its source.
Bump both — together, to the same date — when the sync above added, changed, or removed files; a
sync that reported zero changes does not need either touched. Then confirm the licence gate still
holds:

```sh
uv run scripts/checks/asset_packs.py
```

`check_docs_mirror` fails the build the moment `LICENCE.md` and `docs/asset-packs.md` disagree on
any of the five recorded fields, so edit both in the same commit or not at all.

### 4. Commit

Stage only the new or changed `packages/game-assets/maps/*.webp` files (and, if step 3 applied,
the two licence-record edits) — never the scratch download directory from step 1, which lives
outside the repository and should not be added by hand.
