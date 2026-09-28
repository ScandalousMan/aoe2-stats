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
prose, counts its bullets per civilisation, and fails when `effects.toml` (plus this file's own two
closed, reviewed registries of the bullets that structurally cannot, or need not, become an
`[[effect]]` row — `_NO_SELECTOR_BULLETS` for a bullet with no representable entity at all, and
`_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW` for one whose entity is real but whose baseline
already answers correctly, T652q) accounts for fewer.

**Why a `source_text` cannot always become an `[[effect]]` row.** `effects.Effect` requires a
non-empty, explicit `selector` on every record, modelled or not (`effects.py`'s own docstring). A
bullet naming no representable unit, building or technology at all (e.g. Franks' "Foragers work
+15% faster" — a gather-rate modifier tied to no `rules.json` record) or whose target could only
ever be an unenumerable fuzzy class with no producing-building anchor either (e.g. Teutons' Team
Bonus "Units more resistant to conversion" — "Units" names every military unit in the game) cannot
be written as an effect table at all (`effects.toml`'s own header comment, "Classification rule").
`_NO_SELECTOR_BULLETS` below is the closed, hand-reviewed list of exactly those bullets, each
carrying its own real reason — the same discipline FR-022b's enumerated exception list uses: a
closed list that lives with the test that asserts it, not a standing licence. A different bullet
shape — one that *does* name a representable entity, but for which the entity's own flattened
`rules.json` baseline already answers correctly, so an effect row would assert nothing real
(Persians' "Can build Caravanserai in Imperial Age", building 1754, T652q) — is a distinct closed
list, `_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW`, kept separate so neither registry's own name
overclaims what it holds. A bullet's absence from `effects.toml` and both registries is the defect
this file exists to catch.

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
    "Persians": ("Start with +50 wood and +50 food",),
    "Saracens": (),
    "Malians": (),
    "Tatars": (
        "Livestock animals last +50% longer",
        "Units deal +25% damage when fighting from higher elevation",
    ),
}

#: **T652q correction (the fourth review, item 6): a second, distinct closed registry.**
#: "Can build Caravanserai in Imperial Age" used to live in `_NO_SELECTOR_BULLETS` above, but that
#: registry's own name and docstring both say "no representable entity at all", and this bullet
#: has one — building 1754 ("Caravanserai") is a real `rules.json` entity. What actually excludes
#: it from `effects.toml` is a different, narrower fact (`effects.toml`'s own header comment):
#: `query.available_to`'s baseline already answers `True` for Persians with no effect at all,
#: because `rules.json`'s flattened model treats "the entity resolves" as sufficient and this
#: pack revision only lists Caravanserai in `data.json` for Persians and Hindustanis in the first
#: place — so a no-op effect asserting a fact the baseline already gets right would add a row that
#: represents nothing real. Kept as its own table, not folded into `_NO_SELECTOR_BULLETS`, so
#: neither registry's name overclaims what it holds.
_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW: Mapping[str, tuple[str, ...]] = {
    "Franks": (),
    "Teutons": (),
    "Persians": ("Can build Caravanserai in Imperial Age",),
    "Saracens": (),
    "Malians": (),
    "Tatars": (),
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
        for registered in _ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW[civilisation]:
            assert registered in bullets, (
                f"{civilisation}: {registered!r} is registered in "
                "_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW, but it is not one of "
                f"strings.en.json's own bullets for help_string_id {source_key} — {bullets!r}. "
                "The registry has gone stale."
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
        accounted_for = (
            _distinct_effect_source_texts(civilisation)
            | frozenset(_NO_SELECTOR_BULLETS[civilisation])
            | frozenset(_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW[civilisation])
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
        accounted_for = (
            _distinct_effect_source_texts(civilisation)
            | frozenset(_NO_SELECTOR_BULLETS[civilisation])
            | frozenset(_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW[civilisation])
        )
        assert len(accounted_for) == len(bullets), (
            f"{civilisation}: strings.en.json names {len(bullets)} bullet(s) "
            f"({sorted(bullets)!r}) but effects.toml plus _NO_SELECTOR_BULLETS accounts for "
            f"{len(accounted_for)} ({sorted(accounted_for)!r}) — a mismatch in either direction "
            "means either a dropped bullet or a stale/duplicated entry."
        )


def test_malians_pierce_armor_source_text_records_its_line_break_deviation() -> None:
    """**T652x, item (4).** data-model.md §6 calls `source_text` verbatim. Malians' own bullet
    wraps mid-sentence in the raw source — `strings.en.json` help_string_id 120175's own text
    contains `"pierce armor in Feudal/<br>\\nCastle/Imperial Age"`, a rendering line break, not a
    second bullet — and `effects.toml`'s `source_text` rejoins the two halves with no separating
    space rather than transcribing the break literally. The two tests above already prove this
    exact rejoining is `_bullets_for`'s own, universally-applied convention (every civilisation's
    prose is reconstructed the same way, not only Malians'), so this test proves the second half
    data-model.md §6 requires: the deviation is not merely handled by test code far from the row,
    it is recorded in the row's own `validated_by`."""
    raw = _strings_en()["120175"]
    assert "Feudal/<br>\nCastle/Imperial Age" in raw, (
        "strings.en.json help_string_id 120175 no longer wraps this bullet the way this test "
        "(and effects.toml's own recorded deviation) assumes — re-check both against the pack"
    )
    (effect,) = [
        e
        for e in effects._effects(_PROMOTED_DIRECTORY)
        if e.civilisation == "Malians"
        and e.source_text == "Barracks Units +1/+2/+3 pierce armor in Feudal/Castle/Imperial Age"
    ]
    assert "<br>" not in effect.source_text, (
        "source_text should be the rejoined form (this deviation is recorded, not transcribed "
        "literally) — a literal <br> here means the row and this test have drifted apart"
    )
    assert "<br>" in effect.validated_by and "Feudal" in effect.validated_by, (
        "the row's own validated_by must record the line-break deviation data-model.md §6 "
        "requires, not merely rely on a test file to explain it"
    )
