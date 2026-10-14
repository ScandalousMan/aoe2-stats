"""Tests for the feature-001-shaped assumptions in `scripts/checks/spec_lint.py` (T201, T202, T301).

`spec_lint.py` was written when this repository held exactly one feature, and four of its checks
(`task-refs`, `alert-kinds`, `env-consumed`, `register-commitments`) quietly baked that in: each one
only ever looked inside the single feature it was linting, never across `specs/`. Feature 002 made
that assumption visible, because eleven of its own task ids are cited by feature 001 and vice versa
by design (tasks.md, "Numbering starts at T201, deliberately"). T202 widened all four to resolve
identifiers across every feature directory under `specs/`.

Every test below builds its own fixture feature directory under `tmp_path`, never under `specs/`
itself — the linter's own tests must not change meaning the day a third feature is added, and must
not depend on the real repository's current shape. Every check exercised here reads at least one of
its inputs from the module-level `REPO` rather than from an argument (`check_env` and
`check_register_commitments` scan `REPO / "specs"` directly; `check_task_references` is handed
`feature_dir` explicitly but still resolves siblings from `feature_dir.parent`), so `monkeypatch`
retargets `spec_lint.REPO` at the fixture tree wherever a test's own feature tree must be the one
the check actually widens against, rather than the real repository underneath it. `spec_lint` is
imported inside every test body rather than at module scope, matching the convention the rest of
this test suite already uses once a module under test exists (see `test_cron_liveness.py`).

`spec_lint.failures` and `spec_lint.notes` are process-wide mutable lists, not return values, and
`import spec_lint` inside a test body still resolves to the same cached module object every other
test in this process already imported — so every test clears both lists itself before calling a
check function, rather than trusting the previous test to have left them empty.

Each check gets one positive and one negative test:

- `task-refs` (a): an id defined by a *different* feature's `tasks.md` must pass; an id defined
  nowhere must still fail.
- `alert-kinds` (b): a feature declaring no alert vocabulary at all must pass; a feature naming a
  producer with a kind outside its own declared vocabulary must still fail.
- `env-consumed` (c): a behavioural key consumed by a task in another feature must pass; a key
  consumed by no task anywhere must still fail.
- `register-commitments` (d): a launch item naming a task defined in another feature must pass; an
  item naming an id defined nowhere must still fail.
- `task-collisions` (a2, a3, a4): an id two features both define must fail naming both files, and
  a collision recorded in `RECORDED_TASK_ID_COLLISIONS` passes only while exactly its two recorded
  features define it, asserted by the lint of each feature the entry names (an entry no two
  features collide on fails too). `main` is run over a fixture tree so deleting the call from it
  turns the suite red.
- `task-checkbox` (a4): a definition whose checkbox holds an uppercase X must fail naming its id,
  and is still read as a definition so it can collide; a lowercase tick, and an uppercase box on a
  line that defines no task, must pass.
- `alert-kinds` and `literals` readings of a definition line (b, c2): a producer counts only when
  a space and a body follow its id, the last such definition winning; a line is labelled by its
  task id only when a space follows the id.
- `behavioural-section` (e): a `.env.example` section header ending in "tuning" other than the
  literal `Ingestion tuning` — feature 003's own `Search, favourites and analysis tuning` — must
  still mark its keys behavioural; a header that merely *contains* "tuning" without ending in it
  must not.

None of the eight carries `xfail` any more. Under the single-feature checks T201 first wrote these
tests against, every positive half failed structurally and was marked
`@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")`; T202's widening is what each
marker's own reason named, and `strict=True` is what forced every marker off the moment the
positive half started passing for real rather than merely permitting it. The negative half of each
pair was never marked: it asserts a guard the single-feature checks already had — an id, a kind or a
key that is genuinely defined nowhere, in this feature or any other, must still fail — and T202's
widening had to keep that guard rather than lose it while resolving across features.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# --------------------------------------------------------------------------------- (a) task-refs


def test_task_refs_passes_for_an_id_defined_by_a_different_feature(tmp_path: Path) -> None:
    """An id cited in this feature's own artifacts but defined only in another feature's
    `tasks.md` must not be reported as undefined — that is exactly the shape feature 002's own
    tasks.md is in today, citing eleven of feature 001's ids by bare number."""
    import scripts.checks.spec_lint as spec_lint

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T301 A task local to this feature\n")
    (feature_dir / "notes.md").write_text("See T401 for the judgment behind this decision.\n")

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text("- [ ] T401 A task owned by the other feature\n")

    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_task_references(feature_dir, tasks_text)

    assert not any(f.startswith("task-refs") for f in spec_lint.failures)


def test_task_refs_fails_for_an_id_defined_nowhere(tmp_path: Path) -> None:
    """The negative half: an id cited in this feature's artifacts but defined by no feature's
    `tasks.md` at all — not this one, not any other — must still be reported. This is the guard
    the positive half's widening must not lose."""
    import scripts.checks.spec_lint as spec_lint

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T301 A task local to this feature\n")
    (feature_dir / "notes.md").write_text("See T999 for the judgment behind this decision.\n")

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text("- [ ] T401 A task owned by the other feature\n")

    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_task_references(feature_dir, tasks_text)

    assert any(
        f.startswith("task-refs") and "T999" in f and "defined by no task" in f
        for f in spec_lint.failures
    )


# ------------------------------------------------------------------------ (a2) task-collisions


def _two_features(tmp_path: Path, first: str, second: str) -> tuple[Path, Path]:
    """Two sibling feature directories under a fixture `specs/`, returned in the given order."""
    dirs = []
    for name in (first, second):
        feature_dir = tmp_path / "specs" / name
        feature_dir.mkdir(parents=True)
        dirs.append(feature_dir)
    return dirs[0], dirs[1]


def _collisions_of(feature_dir: Path) -> list[str]:
    import scripts.checks.spec_lint as spec_lint

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_task_id_collisions(feature_dir, (feature_dir / "tasks.md").read_text())
    return [f for f in spec_lint.failures if f.startswith("task-collisions")]


def test_task_collisions_fails_for_an_id_two_features_define_naming_both_files(
    tmp_path: Path,
) -> None:
    """Plant: an id two features both define, and no recorded collision covers, is the shape
    003/004 and 005/006 reached by accident. The failure names the id and both `tasks.md` files."""
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T301 Defined here\n")
    (other / "tasks.md").write_text("- [x] T301 Defined there too\n")

    found = _collisions_of(mine)

    assert len(found) == 1
    assert "T301" in found[0]
    assert "specs/002-under-test/tasks.md" in found[0]
    assert "specs/001-other/tasks.md" in found[0]


def test_task_collisions_passes_for_a_recorded_collision_between_its_two_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T301",
        frozenset({"002-under-test", "001-other"}),
    )
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T301 Defined here\n")
    (other / "tasks.md").write_text("- [x] T301 Defined there too\n")

    assert _collisions_of(mine) == []
    assert _collisions_of(other) == []


def test_task_collisions_fails_for_a_recorded_id_colliding_between_the_wrong_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exemption belongs to a pair of features, not to an id: a recorded id that a third
    feature also defines, or that the wrong pair defines, is a new collision."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T301",
        frozenset({"002-under-test", "001-other"}),
    )
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    third = tmp_path / "specs" / "003-third"
    third.mkdir()
    (mine / "tasks.md").write_text("- [ ] T301 Defined here\n")
    (other / "tasks.md").write_text("- [x] T301 Defined there too\n")
    (third / "tasks.md").write_text("- [ ] T301 And a third time\n")

    found = _collisions_of(mine)
    assert found
    assert all("T301" in f for f in found)
    assert any("specs/003-third/tasks.md" in f for f in found)

    wrong_pair, _ = _two_features(tmp_path / "other-tree", "002-under-test", "004-wrong")
    (wrong_pair / "tasks.md").write_text("- [ ] T301 Defined here\n")
    (wrong_pair.parent / "004-wrong" / "tasks.md").write_text("- [ ] T301 Wrong partner\n")

    assert _collisions_of(wrong_pair)


def test_task_collisions_passes_for_an_id_one_feature_defines_and_another_references(
    tmp_path: Path,
) -> None:
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T301 Defined here\n")
    (mine / "notes.md").write_text("See T401.\n")
    (other / "tasks.md").write_text("- [ ] T401 Defined there\n\nIt also mentions T301 in prose.\n")

    assert _collisions_of(mine) == []
    assert _collisions_of(other) == []


def test_task_collisions_treats_a_letter_suffix_as_its_own_id(tmp_path: Path) -> None:
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T672a Suffixed here\n")
    (other / "tasks.md").write_text("- [ ] T672 Unsuffixed there\n")

    assert _collisions_of(mine) == []
    assert _collisions_of(other) == []


# ---------------------------------------------------- (a3) task-collisions: the record, both ways


def test_task_collisions_fails_for_a_recorded_id_that_only_one_feature_defines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plant: a record entry for an id that no two features collide on fails nothing today, so an
    entry added by hand would sit in the record unchallenged. The lint of either recorded feature
    names the id and both recorded features."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T501",
        frozenset({"002-under-test", "001-other"}),
    )
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T501 Defined here only\n")
    (other / "tasks.md").write_text("- [ ] T502 Something else\n")

    for linted in (mine, other):
        found = _collisions_of(linted)
        assert len(found) == 1, found
        assert "T501" in found[0]
        assert "002-under-test" in found[0]
        assert "001-other" in found[0]


def test_task_collisions_fails_for_a_recorded_id_one_of_its_features_stopped_defining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plant: an entry left behind when one of its two features stops defining the id, after which
    a third feature files a different task under the same id (the id is then defined by the wrong
    pair). The remaining definer fails exactly once, with the message that names the recorded
    pair: the unrecorded-collision message stays off a feature the record names."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T501",
        frozenset({"002-under-test", "001-other"}),
    )
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    third = tmp_path / "specs" / "003-third"
    third.mkdir()
    (mine / "tasks.md").write_text("- [ ] T501 Still defined here\n")
    (other / "tasks.md").write_text("- [ ] T999 No longer defines T501\n")
    (third / "tasks.md").write_text("- [ ] T501 A different task under the same id\n")

    found = _collisions_of(mine)
    assert len(found) == 1, found
    assert "T501" in found[0]
    assert "001-other" in found[0]
    assert "002-under-test" in found[0]
    assert _collisions_of(other)
    assert _collisions_of(third)


def test_task_collisions_passes_for_a_recorded_collision_its_two_features_both_define(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contrast: the record is asserted for the features it names and no others. An entry naming
    two other features says nothing about the one being linted."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T501",
        frozenset({"002-under-test", "001-other"}),
    )
    monkeypatch.setitem(
        spec_lint.RECORDED_TASK_ID_COLLISIONS,
        "T502",
        frozenset({"003-third", "004-fourth"}),
    )
    mine, other = _two_features(tmp_path, "002-under-test", "001-other")
    (mine / "tasks.md").write_text("- [ ] T501 Defined here\n")
    (other / "tasks.md").write_text("- [x] T501 Defined there too\n")

    assert _collisions_of(mine) == []
    assert _collisions_of(other) == []


# ------------------------------------------------------------- (a4) main, and the checkbox spelling


def _lint_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tasks_by_feature: dict[str, str],
    linted: str,
) -> tuple[int, str]:
    """Build a fixture repository, run `main` against `linted`, and return (exit code, output).

    `REPO` is resolved because `main` resolves the feature directory and takes its path relative to
    `REPO`; an unresolved temporary directory (a symlink on macOS) would make that raise.
    """
    import scripts.checks.spec_lint as spec_lint

    repo = tmp_path.resolve()
    for name, tasks in tasks_by_feature.items():
        feature_dir = repo / "specs" / name
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# Spec\n\n**FR-001**: A requirement.\n")
        (feature_dir / "plan.md").write_text("# Plan\n")
        (feature_dir / "tasks.md").write_text(f"{tasks}\nCovers FR-001.\n")
    monkeypatch.setattr(spec_lint, "REPO", repo)
    monkeypatch.setattr("sys.argv", ["spec_lint.py", "--feature", f"specs/{linted}"])
    spec_lint.failures.clear()
    spec_lint.notes.clear()
    code = spec_lint.main()
    return code, capsys.readouterr().out


def test_main_exits_1_naming_an_id_two_features_define(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main` is what CI runs. A test of `check_task_id_collisions` alone passes when the call is
    deleted from `main`, and the lint then exits 0 for every feature."""
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"001-other": "- [ ] T301 Defined there\n", "002-under-test": "- [ ] T301 Defined here\n"},
        "002-under-test",
    )

    assert code == 1
    assert "task-collisions" in out
    assert "T301" in out


def test_main_exits_0_when_no_two_features_define_one_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Contrast for the test above: the same fixture tree, with distinct ids, is clean, so the
    exit code of 1 there is the collision and nothing else in the fixture."""
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"001-other": "- [ ] T302 Defined there\n", "002-under-test": "- [ ] T301 Defined here\n"},
        "002-under-test",
    )

    assert code == 0, out


def test_task_checkbox_fails_for_a_definition_with_an_uppercase_x(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Plant: `- [X] T301` is a definition that neither `task-refs` nor `task-collisions` read, so
    an id one feature ticks `[x]` and another ticks `[X]` passed both lints."""
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"002-under-test": "- [X] T301 Ticked with a capital\n"},
        "002-under-test",
    )

    assert code == 1
    assert "T301" in out
    assert "uppercase" in out


def test_an_id_ticked_x_in_one_feature_and_capital_x_in_another_is_a_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"001-other": "- [x] T301 Defined there\n", "002-under-test": "- [X] T301 Defined here\n"},
        "001-other",
    )

    assert code == 1
    assert "task-collisions" in out
    assert "T301" in out


def test_task_checkbox_passes_for_a_ticked_lowercase_definition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"002-under-test": "- [x] T301 Ticked in lowercase\n"},
        "002-under-test",
    )

    assert code == 0, out


def test_task_checkbox_passes_for_an_uppercase_box_on_a_line_that_defines_no_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _lint_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        {"002-under-test": "- [ ] T301 A real task\n- [X] some launch item\n"},
        "002-under-test",
    )

    assert code == 0, out


# ------------------------------------------------------------------------------- (b) alert-kinds


def test_alert_kinds_passes_when_data_model_declares_no_alert_vocabulary(tmp_path: Path) -> None:
    """A feature that names no `kind` enum at all in its `data-model.md` — feature 002's own shape,
    since it defines no alerts — has nothing for this check to say, and must not be treated as a
    malformed enum declaration."""
    import scripts.checks.spec_lint as spec_lint

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "data-model.md").write_text(
        "# Data Model\n\nThis feature adds no new alert kind.\n"
    )
    (feature_dir / "tasks.md").write_text("- [ ] T310 A task unrelated to alerting\n")

    data_model_text = (feature_dir / "data-model.md").read_text()
    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_alert_kinds(data_model_text, tasks_text)

    assert not any(f.startswith("alert-kinds") for f in spec_lint.failures)


def test_alert_kinds_fails_when_a_producer_uses_a_kind_outside_the_vocabulary(
    tmp_path: Path,
) -> None:
    """The negative half: a feature that *does* declare a vocabulary, and whose own tasks.md names
    a producer raising a kind outside it, must still fail — this is single-feature behaviour the
    check already has, and widening the check to cover the positive half above must not weaken it.
    """
    import scripts.checks.spec_lint as spec_lint

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "data-model.md").write_text(
        "# Data Model\n\n`kind` (enum: `foo`, `bar`)\n\nProducers:\n- T701 `foo`\n- T702 `bar`\n"
    )
    (feature_dir / "tasks.md").write_text(
        "- [ ] T701 Raises the foo alert\n"
        "- [ ] T702 Raises the bar alert\n"
        "- [ ] T703 Raises a severity-1 `baz` alert when the sensor trips\n"
    )

    data_model_text = (feature_dir / "data-model.md").read_text()
    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_alert_kinds(data_model_text, tasks_text)

    assert any(
        f.startswith("alert-kinds") and "baz" in f and "not in data-model.md's enum" in f
        for f in spec_lint.failures
    )


def _alert_failures(data_model: str, tasks: str) -> list[str]:
    import scripts.checks.spec_lint as spec_lint

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_alert_kinds(data_model, tasks)
    return [f for f in spec_lint.failures if f.startswith("alert-kinds")]


_ONE_KIND_DATA_MODEL = "# Data Model\n\n`kind` (enum: `foo`)\n\nProducers:\n- T701 `foo`\n"


def test_alert_kinds_fails_for_a_producer_whose_only_definition_has_a_colon_after_its_id() -> None:
    """Plant: a producer counts as defined only when a space and a body follow its id, as it did
    before the single reader. `- [ ] T701: raise ...` is a definition for `task-refs` but was not a
    producer's definition for this check."""
    found = _alert_failures(_ONE_KIND_DATA_MODEL, "- [ ] T701: raise a `foo` alert\n")

    assert len(found) == 1, found
    assert "T701" in found[0]
    assert "defined by no task" in found[0]


def test_alert_kinds_passes_for_a_producer_defined_with_a_body_and_then_again_with_none() -> None:
    """Plant: of several definitions that carry a body the last wins, and a definition with nothing
    after its id carries none, so it replaces nothing."""
    found = _alert_failures(_ONE_KIND_DATA_MODEL, "- [ ] T701 Raises a `foo` alert\n- [ ] T701\n")

    assert found == []


def test_alert_kinds_passes_for_a_producer_defined_with_a_space_and_a_body() -> None:
    """Contrast: the ordinary shape still resolves."""
    assert _alert_failures(_ONE_KIND_DATA_MODEL, "- [ ] T701 Raises a `foo` alert\n") == []


# ------------------------------------------------------------------------------ (c) env-consumed


def test_env_consumed_passes_for_a_key_consumed_by_a_task_in_another_feature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A behavioural `.env.example` key this feature never mentions, but that a task in a
    *different* feature reads, must not be reported as consumed by nothing — the key has a reader,
    just not one inside this feature's own `tasks.md`."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setattr(spec_lint, "REPO", tmp_path)

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T320 A task that never mentions the key\n")

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text(
        "- [ ] T420 Reads SOME_BEHAVIOURAL_KEY from the environment\n"
    )

    env_text = (
        "# --- Ingestion tuning -------------------------------------------------------\n"
        "SOME_BEHAVIOURAL_KEY=42\n"
    )
    env_values, behavioural = spec_lint.parse_env(env_text)
    tasks_text = (feature_dir / "tasks.md").read_text()
    sources = {"tasks.md": tasks_text}

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_env(sources, tasks_text, env_values, behavioural)

    assert not any(f.startswith("env-consumed") for f in spec_lint.failures)


def test_env_consumed_fails_for_a_key_consumed_by_no_task_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative half: a behavioural key that no task, in this feature or any other, ever
    mentions must still be reported — a key that tunes behaviour and is read by nothing is exactly
    the gap this check exists to catch."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setattr(spec_lint, "REPO", tmp_path)

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T320 A task that never mentions the key\n")

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text(
        "- [ ] T420 A task that also never mentions the key\n"
    )

    env_text = (
        "# --- Ingestion tuning -------------------------------------------------------\n"
        "SOME_BEHAVIOURAL_KEY=42\n"
    )
    env_values, behavioural = spec_lint.parse_env(env_text)
    tasks_text = (feature_dir / "tasks.md").read_text()
    sources = {"tasks.md": tasks_text}

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_env(sources, tasks_text, env_values, behavioural)

    assert any(
        f.startswith("env-consumed") and "SOME_BEHAVIOURAL_KEY" in f for f in spec_lint.failures
    )


# ----------------------------------------------------------------------------- (c2) literals


def _literal_failures(tasks: str) -> list[str]:
    import scripts.checks.spec_lint as spec_lint

    env_values, behavioural = spec_lint.parse_env(
        "# --- Ingestion tuning -----------------------------------------------\n"
        "SOME_WINDOW_DAYS=21\n"
    )
    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_literals({"tasks.md": tasks}, env_values, behavioural)
    return [f for f in spec_lint.failures if f.startswith("literals")]


def test_literals_labels_a_line_by_its_line_number_when_a_colon_follows_the_id() -> None:
    """Plant: a line is labelled by its task id only when a space follows the id."""
    found = _literal_failures("- [ ] T330: keep it for 21 days\n")

    assert len(found) == 1, found
    assert "tasks.md:1 " in found[0]
    assert "T330" not in found[0]


def test_literals_labels_a_line_by_its_task_id_when_a_space_follows_the_id() -> None:
    """Contrast: the ordinary shape keeps its id label."""
    found = _literal_failures("- [ ] T330 keep it for 21 days\n")

    assert len(found) == 1, found
    assert "tasks.md T330 " in found[0]


# --------------------------------------------------------------------- (d) register-commitments


def test_register_commitments_passes_for_an_item_naming_a_task_in_another_feature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A processing-register launch item naming a task owned by a *different* feature — exactly how
    feature 001's own register items would read to a feature-002 lint run — must pass, because the
    task delivering it exists, just not in the feature being linted."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setattr(spec_lint, "REPO", tmp_path)

    register_dir = tmp_path / "docs" / "privacy"
    register_dir.mkdir(parents=True)
    (register_dir / "processing-register.md").write_text(
        "- [ ] Ship a widget promised elsewhere — T450.\n"
    )

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text("- [ ] T450 Ships the widget\n")

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T351 A task unrelated to the register item\n")
    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_register_commitments(tasks_text)

    assert not any(f.startswith("register-commitments") for f in spec_lint.failures)


def test_register_commitments_fails_for_an_item_naming_a_task_defined_nowhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative half: a launch item naming an id that no feature's `tasks.md` defines — not
    this one, not any other — must still fail, exactly as it does today."""
    import scripts.checks.spec_lint as spec_lint

    monkeypatch.setattr(spec_lint, "REPO", tmp_path)

    register_dir = tmp_path / "docs" / "privacy"
    register_dir.mkdir(parents=True)
    (register_dir / "processing-register.md").write_text(
        "- [ ] Ship a widget promised to nobody — T999.\n"
    )

    other_feature_dir = tmp_path / "specs" / "001-other"
    other_feature_dir.mkdir(parents=True)
    (other_feature_dir / "tasks.md").write_text("- [ ] T450 Ships the widget\n")

    feature_dir = tmp_path / "specs" / "002-under-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T351 A task unrelated to the register item\n")
    tasks_text = (feature_dir / "tasks.md").read_text()

    spec_lint.failures.clear()
    spec_lint.notes.clear()
    spec_lint.check_register_commitments(tasks_text)

    assert any(
        f.startswith("register-commitments") and "T999" in f and "does not define" in f
        for f in spec_lint.failures
    )


# --------------------------------------------------------------------- (e) behavioural-section


def test_behavioural_section_recognises_any_header_ending_in_tuning() -> None:
    """T301: `parse_env` decided "behavioural" by the single literal header `Ingestion tuning`.
    Feature 003 adds its own section, `Search, favourites and analysis tuning`, and its keys must
    be recognised as behavioural too, without the check learning that literal string by name."""
    import scripts.checks.spec_lint as spec_lint

    env_text = (
        "# --- Search, favourites and analysis tuning ---------------------------------\n"
        "FAVOURITES_MAX_PER_USER=100\n"
    )

    _, behavioural = spec_lint.parse_env(env_text)

    assert "FAVOURITES_MAX_PER_USER" in behavioural


def test_behavioural_section_ignores_a_header_that_only_contains_tuning() -> None:
    """The negative half: a header that mentions "tuning" without *ending* in it must not be
    swept in — the check matches the suffix deliberately, not a substring anywhere in the
    header, so a section like "Tuning notes for the database" (about infrastructure, not
    behaviour) does not silently start requiring its keys to be named by a task."""
    import scripts.checks.spec_lint as spec_lint

    env_text = (
        "# --- Tuning notes for the database --------------------------------------------\n"
        "DATABASE_POOL_SIZE=5\n"
    )

    _, behavioural = spec_lint.parse_env(env_text)

    assert "DATABASE_POOL_SIZE" not in behavioural
