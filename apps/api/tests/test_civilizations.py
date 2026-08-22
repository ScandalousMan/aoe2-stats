"""Unit tests for `aoe2stats_api.civilizations` (T070c).

Mirrors `test_leaderboards.py` (T033a) byte for byte in shape: this is the one place
`civ_id -> name` is hand-maintained (see the module docstring), a self-contained unit test, no
database and no network.
"""

from aoe2stats_api.civilizations import civilisation_name


def test_names_a_known_civilisation_id() -> None:
    assert civilisation_name(1) == "Britons"


def test_falls_back_to_civilisation_id_for_an_unrecognised_id() -> None:
    """An id this table does not carry — including every civilisation added by an expansion since
    the game's original release — renders as "Civilisation <id>", never a guessed name (module
    docstring)."""
    assert civilisation_name(999) == "Civilisation 999"


def test_none_stays_none() -> None:
    """A participant with no recorded civilisation is not itself a guess to paper over — `None`
    in, `None` out (module docstring)."""
    assert civilisation_name(None) is None
