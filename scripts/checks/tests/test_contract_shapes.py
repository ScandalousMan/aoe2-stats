"""Unit tests for the pure shape assertions behind `contract_sources.py`'s aoe2companion
search-endpoint check (T385a).

No network here — `contract_shapes.py` is pure by construction, exactly so it can be tested this
way instead of only ever being exercised by the nightly contract run. See
`scripts/checks/contract_shapes.py`.
"""

import pytest
from scripts.checks.contract_shapes import assert_companion_search_shape


def test_a_well_shaped_page_passes() -> None:
    """The real, contracted shape (`docs/data-sources.md` §3): `profiles` is a list, each record
    carries `profileId` and `name` among whatever else the source sends."""
    assert_companion_search_shape(
        {
            "page": 1,
            "profiles": [
                {"profileId": 196240, "name": "TheViper", "country": "de", "games": "10665"},
                {"profileId": 9187696, "name": "Vipechester", "country": "ie", "games": "7958"},
            ],
        }
    )


def test_a_genuine_zero_match_page_passes() -> None:
    """`{"profiles": []}` is a real, parseable answer for a substring matching no player — never a
    shape drift (module docstring's BL-1/BL-5 split, mirroring `companion/provider.py`)."""
    assert_companion_search_shape({"profiles": []})


def test_one_bad_record_among_good_ones_is_not_drift() -> None:
    """The contrast case: `_parse_search_page` drops a single malformed entry and still returns
    the rest, so one record missing `profileId`/`name` — with another in the same page carrying
    both — must not raise. Only *every* entry failing is BL-5."""
    assert_companion_search_shape(
        {
            "profiles": [
                {"pid": 1, "displayName": "renamed-record"},
                {"profileId": 196240, "name": "TheViper"},
            ]
        }
    )


def test_envelope_drift_raises_when_profiles_key_is_renamed() -> None:
    """BL-1: the source renames its own envelope key. `results` here instead of `profiles` is
    exactly the drift `_parse_search_page` raises `_MalformedSearchResponse` for — this function's
    job is to raise the same way, from a body that never touches the network."""
    with pytest.raises(AssertionError, match="profiles"):
        assert_companion_search_shape(
            {
                "page": 1,
                "results": [{"profileId": 196240, "name": "TheViper"}],
            }
        )


def test_envelope_drift_raises_when_profiles_is_not_a_list() -> None:
    """BL-1's other shape: `profiles` present but no longer a list (e.g. wrapped in an object)."""
    with pytest.raises(AssertionError, match="profiles"):
        assert_companion_search_shape({"profiles": {"count": 0}})


def test_envelope_drift_raises_when_body_is_not_an_object() -> None:
    """BL-1's third shape: a bare list or scalar instead of the contracted envelope object."""
    with pytest.raises(AssertionError, match="JSON object"):
        assert_companion_search_shape([{"profileId": 196240, "name": "TheViper"}])


def test_record_drift_raises_when_every_record_is_missing_profile_id_and_name() -> None:
    """BL-5: the envelope survives — `profiles` is a real, non-empty list — but every record's
    `profileId`/`name` has been renamed, so nothing survives `_parse_search_result`. A non-empty
    `profiles` list that yields zero usable records is not a genuine zero-match answer."""
    with pytest.raises(AssertionError, match=r"profileId.*name|BL-5"):
        assert_companion_search_shape(
            {
                "profiles": [
                    {"pid": 196240, "displayName": "TheViper"},
                    {"pid": 9187696, "displayName": "Vipechester"},
                ]
            }
        )
