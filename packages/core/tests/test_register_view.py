"""The generated register view (FR-006a, T617): its structure and its drift gate.

Written first as strict xfails; T617 implemented the renderer and the markers are gone.
"""

from __future__ import annotations

from importlib import resources

from aoe2stats_core.truth.register import (
    NON_DETERMINABLE,
    REGENERATE_COMMAND,
    REGISTER,
    load_register_text,
    render_view,
)

_TEXT = """
[datum."a.observed_thing"]
classification = "observed"
status = "published"
source = "s"
method = "m"
requires_knowledge = []
depends_on = []
validation = "v"
evidence = "e"

[datum."a.lost_thing"]
classification = "non-determinable"
status = "blocked"
blocked_on = "an outcome event"
reason = "R-TEXT"
impact = "I-TEXT"
approximation = "A-TEXT"
approximation_acceptable = "no"
would_change_if = "W-TEXT"
source = "s"
method = "m"
requires_knowledge = []
depends_on = []
validation = "v"
evidence = "e"

[datum."a.guess"]
classification = "inferred"
status = "planned"
source = "s"
method = "m"
requires_knowledge = []
depends_on = []
validation = "v"
evidence = "e"
"""


def test_non_determinable_come_first_and_in_full() -> None:
    view = render_view(load_register_text(_TEXT))
    lost, observed, guess = (
        view.index(f"a.{n}") for n in ("lost_thing", "observed_thing", "guess")
    )
    assert lost < observed < guess
    for text in ("R-TEXT", "I-TEXT", "A-TEXT", "W-TEXT", "an outcome event"):
        assert text in view
    assert "approximation_acceptable" in view


def test_the_view_names_its_source_and_is_deterministic() -> None:
    register = load_register_text(_TEXT)
    view = render_view(register)
    header = view.split("\n## ", 1)[0]
    assert "register.toml" in header
    assert "generated" in header.lower()
    assert render_view(register) == view
    assert view.endswith("\n") and not view.endswith("\n\n")


def test_every_packaged_entry_appears_in_the_view() -> None:
    view = render_view(REGISTER)
    for entry in REGISTER:
        assert f"`{entry.id}`" in view
    first_nd = next(e.id for e in REGISTER if e.classification == NON_DETERMINABLE)
    assert view.index(first_nd) < view.index("## observed")


def test_the_committed_view_matches_the_register_byte_for_byte() -> None:
    committed = resources.files("aoe2stats_core.truth").joinpath("REGISTER.md").read_text("utf-8")
    assert committed == render_view(REGISTER), (
        "REGISTER.md has drifted from register.toml. Regenerate it with: " + REGENERATE_COMMAND
    )
