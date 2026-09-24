"""T652o: every bullet of the six modelled civilisations' vendored prose must be accounted for.

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Civilisation qualification". Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D5** ("What stays out
of the effect model" and "A bonus is never half-applied").

**The defect this file exists to make impossible.** Before this task, `effects.toml`'s own
transcription silently dropped several bonuses that touch a query-surface field this knowledge base
tracks — Malians' Team Bonus, Teutons' "Murder Holes, Herbal Medicine free", Franks' "Chivalry",
Persians' Town-Center/Dock work-speed clause — because nothing checked that a bonus had been
*considered* at all, only that a present `[[effect]]` entry was well-formed. A test that only reads
`effects.toml` cannot see an omission; this file reads the other side, `strings.en.json`'s own
prose, counts its bullets per civilisation, and fails when `effects.toml` (plus this file's own
closed, reviewed registry of the bullets that structurally cannot become an `[[effect]]` row)
accounts for fewer.

**Why a `source_text` cannot always become an `[[effect]]` row.** `effects.Effect` requires a
non-empty, explicit `selector` on every record, modelled or not (`effects.py`'s own docstring). A
bullet naming no representable unit, building or technology at all (e.g. Franks' "Foragers work
+15% faster" — a gather-rate modifier tied to no `rules.json` record) or whose target could only
ever be an unenumerable fuzzy class with no producing-building anchor either (e.g. Teutons' Team
Bonus "Units more resistant to conversion" — "Units" names every military unit in the game) cannot
be written as an effect table at all (`effects.toml`'s own header comment, "Classification rule").
`_NO_SELECTOR_BULLETS` below is the closed, hand-reviewed list of exactly those bullets, each
carrying its own real reason — the same discipline FR-022b's enumerated exception list uses: a
closed list that lives with the test that asserts it, not a standing licence. A bullet's absence
from both `effects.toml` and this registry is the defect this file exists to catch.

**One bullet, one or more `[[effect]]` rows, never fewer.** A compound bullet that a `modelled =
"yes"` cost fix and the correction's `production_time = 0` grant-fact both touch (Franks' "Mill
technologies free", Teutons' "Murder Holes, Herbal Medicine free", Tatars' "Thumb Ring, Parthian
Tactics free") is two `[[effect]]` rows sharing one `source_text` — counted once here, by distinct
`(civilisation, source_text)` pair, never twice, so adding the second row for the same bullet does
not inflate the count past what `strings.en.json` actually contains.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources

from aoe2stats_knowledge import effects

_PACKAGE = "aoe2stats_knowledge"
_PACK_NAME = "aoe2techtree"

#: Both promoted snapshots share the same real, hand-transcribed `effects.toml` content (their
#: `snapshot.toml` files record why: the same pack revision, unchanged across every build between
#: them) — checking one is checking both; `test_effects.py`'s own integration tests already
#: parametrize over both for the same reason.
_PROMOTED_DIRECTORY = "aoe2techtree-180059"

#: `strings.en.json`'s own `help_string_id` for each of the six modelled civilisations
#: (`effects.toml`'s own header comments carry the same keys against each civilisation's entries).
_SOURCE_KEY_BY_CIVILISATION: Mapping[str, str] = {
    "Franks": "120151",
    "Teutons": "120153",
    "Persians": "120157",
    "Saracens": "120158",
    "Malians": "120175",
    "Tatars": "120182",
}


def _pack_root() -> resources.abc.Traversable:
    """The packaged pack root, resolved through `importlib.resources` alone (constitution III,
    SC-006) — the same mechanism `normalise.py`'s own `_pack_root` uses."""
    return resources.files(_PACKAGE).joinpath("packs").joinpath(_PACK_NAME)


def _strings_en() -> Mapping[str, str]:
    return json.loads(_pack_root().joinpath("strings.en.json").read_text(encoding="utf-8"))


def _bullets_for(help_string_id: str) -> tuple[str, ...]:
    """Every bonus bullet `strings.en.json[help_string_id]` names, in the order it names them:
    every top-level `•` line, every `•` line under "Unique Techs:", and the one line following
    "Team Bonus:" (which the source never itself prefixes with `•`). Deliberately excludes the
    leading civilisation-category label (e.g. "Cavalry civilization" — not a bonus) and the
    "Unique Unit(s):" heading's own named unit (naming which unit is unique carries no numeric
    bonus and touches no field this knowledge base could ever track or gap).

    A bullet whose own sentence carries a mid-string `<br>` (Malians' "Barracks Units .../<br>
    Castle/Imperial Age" — the source's own line wrap, not a second bullet) is rejoined onto the
    bullet it wraps, not counted as a second one: a continuation line starts with neither `•` nor
    a heading, so — while a top-level or "Unique Techs:" bullet is open — it is appended to
    `bullets[-1]` instead (with no separating space when the break falls right after a `/`, the
    one shape this pack's own line wrap actually uses, so the rejoined sentence matches the real,
    hand-transcribed `source_text` byte for byte). Checked directly against all six
    civilisations' real prose: 7, 8, 7, 7, 6, 7 — 42 total, matching this file's own manual
    accounting in T652o's own hand-back.
    """
    raw = _strings_en()[help_string_id]
    lines = [line.strip() for line in raw.replace("<br>\n", "<br>").split("<br>")]
    lines = [line for line in lines if line]
    bullets: list[str] = []
    section = "top"
    for line in lines:
        if line.startswith("<b>Unique Unit"):
            section = "skip"
            continue
        if line.startswith("<b>Unique Tech"):
            section = "unique_techs"
            continue
        if line.startswith("<b>Team Bonus"):
            section = "team_bonus_pending"
            continue
        if section == "skip":
            continue
        if line.startswith("•"):
            bullets.append(line.lstrip("•").strip())
            continue
        if section == "team_bonus_pending":
            # Every existing `[[effect]]` entry for a Team Bonus prefixes its own `source_text`
            # with "Team Bonus: " (Franks' and Persians' Knight-line entries, T645) — matched
            # here so a Team Bonus bullet counts as accounted-for by the same string a real
            # effect entry carries, not by the bare sentence alone.
            bullets.append(f"Team Bonus: {line}")
            section = "done"
            continue
        if section in ("top", "unique_techs") and bullets:
            separator = "" if bullets[-1].endswith("/") else " "
            bullets[-1] = f"{bullets[-1]}{separator}{line}"
            continue
    return tuple(bullets)


def _distinct_effect_source_texts(civilisation: str) -> frozenset[str]:
    """Every distinct `source_text` `effects.toml` carries for `civilisation`, whether
    `modelled = "yes"` or `"no"` — a bullet split across two rows (a cost fix and a
    `production_time` grant-fact sharing one `source_text`) is one entry here, not two."""
    # Test-only reader of a private module function: there is no public "every effect for this
    # civilisation" accessor today, and adding one only for this test would be a production seam
    # with exactly one caller.
    all_effects = effects._effects(_PROMOTED_DIRECTORY)
    return frozenset(
        effect.source_text for effect in all_effects if effect.civilisation == civilisation
    )


#: **The closed registry of bullets with no representable entity at all** (this module's own
#: docstring). Each reason is real, hand-reviewed, and matches `effects.toml`'s own header-comment
#: treatment of the same bullet — this table does not decide anything `effects.toml` does not
#: already say in prose; it only makes that prose machine-checkable. Adding an entry here without
#: a matching, equally honest mention in `effects.toml`'s own header comment is exactly the
#: silent-drop this file exists to prevent, so a reviewer checks both together, not this table
#: alone.
_NO_SELECTOR_BULLETS: Mapping[str, tuple[str, ...]] = {
    "Franks": (
        "Foragers work +15% faster",
        "Mounted Units +20% HP starting in Feudal Age",
    ),
    "Teutons": ("Team Bonus: Units more resistant to conversion",),
    "Persians": (
        "Start with +50 wood and +50 food",
        "Can build Caravanserai in Imperial Age",
    ),
    "Saracens": (),
    "Malians": (),
    "Tatars": (
        "Livestock animals last +50% longer",
        "Units deal +25% damage when fighting from higher elevation",
    ),
}


def test_no_selector_bullets_are_real_bullets_from_strings_en_json() -> None:
    """A stale registry entry (the bullet's own wording changed, or it was actually given an
    effect and the registry entry was never removed) must fail loudly rather than silently
    inflating the accounted-for count — checked before the main coverage assertion below, so a
    failure here names the exact stale string rather than only an off-by-one total."""
    for civilisation, source_key in _SOURCE_KEY_BY_CIVILISATION.items():
        bullets = _bullets_for(source_key)
        for registered in _NO_SELECTOR_BULLETS[civilisation]:
            assert registered in bullets, (
                f"{civilisation}: {registered!r} is registered in _NO_SELECTOR_BULLETS as a real "
                f"bullet with no representable entity, but it is not one of strings.en.json's own "
                f"bullets for help_string_id {source_key} — {bullets!r}. The registry has gone "
                "stale."
            )


def test_every_bullet_is_accounted_for_by_an_effect_or_the_no_selector_registry() -> None:
    """**The assertion this task exists to add.** For each of the six modelled civilisations,
    every bullet `strings.en.json` names must be either a distinct `source_text` in `effects.toml`
    (`modelled = "yes"` or `"no"`, either counts — an unmodelled bonus that is honestly recorded
    as refused is accounted for; only silence is the defect) or a `_NO_SELECTOR_BULLETS` entry.
    Set difference, not a bare count comparison, so a failure names the exact dropped bullet
    rather than only an off-by-one total that leaves the next reader re-deriving which one."""
    for civilisation, source_key in _SOURCE_KEY_BY_CIVILISATION.items():
        bullets = frozenset(_bullets_for(source_key))
        accounted_for = _distinct_effect_source_texts(civilisation) | frozenset(
            _NO_SELECTOR_BULLETS[civilisation]
        )
        missing = bullets - accounted_for
        assert not missing, (
            f"{civilisation}: {len(missing)} bullet(s) from strings.en.json help_string_id "
            f"{source_key} are neither an effects.toml [[effect]] source_text nor a "
            f"_NO_SELECTOR_BULLETS entry — silently dropped, the exact defect this test exists to "
            f"catch: {sorted(missing)!r}"
        )


def test_every_bullet_count_matches_exactly() -> None:
    """The count-level assertion the task text names directly ("count the bullets ... and fail
    when the file accounts for fewer") — kept alongside the set-difference test above rather than
    instead of it: this one also catches the opposite mistake, an `effects.toml` or registry entry
    that accounts for a bullet *twice* under two different exact strings (which would pass the set
    check above by accident if a genuine bullet were simultaneously missing), by requiring the
    accounted-for total to match the real bullet count exactly, not merely cover it."""
    for civilisation, source_key in _SOURCE_KEY_BY_CIVILISATION.items():
        bullets = frozenset(_bullets_for(source_key))
        accounted_for = _distinct_effect_source_texts(civilisation) | frozenset(
            _NO_SELECTOR_BULLETS[civilisation]
        )
        assert len(accounted_for) == len(bullets), (
            f"{civilisation}: strings.en.json names {len(bullets)} bullet(s) "
            f"({sorted(bullets)!r}) but effects.toml plus _NO_SELECTOR_BULLETS accounts for "
            f"{len(accounted_for)} ({sorted(accounted_for)!r}) — a mismatch in either direction "
            "means either a dropped bullet or a stale/duplicated entry."
        )
