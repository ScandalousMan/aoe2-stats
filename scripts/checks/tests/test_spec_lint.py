"""Tests for the four feature-001-shaped assumptions in `scripts/checks/spec_lint.py` (T201).

`spec_lint.py` was written when this repository held exactly one feature, and four of its checks
(`task-refs`, `alert-kinds`, `env-consumed`, `register-commitments`) quietly baked that in: each one
only ever looks inside the single feature it is linting, never across `specs/`. Feature 002 makes
that assumption visible, because eleven of its own task ids are cited by feature 001 and vice versa
by design (tasks.md, "Numbering starts at T201, deliberately").

Every test below builds its own fixture feature directory under `tmp_path`, never under `specs/`
itself — the linter's own tests must not change meaning the day a third feature is added, and must
not depend on the real repository's current shape. Where a check reads its own inputs from `REPO`
(`check_register_commitments`, via `docs/privacy/processing-register.md`), `monkeypatch` retargets
`spec_lint.REPO` at the fixture tree so the real repository is never touched. `spec_lint` is
imported inside every test body rather than at module scope, per T201: it is not implemented
against these four assumptions yet, and a module-scope import would make every test's failure mode
"collection error" instead of the specific assertion each one is meant to prove.

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

The positive half of each pair is what T202 has to build — none of the four checks can currently see
past the one feature directory it was handed — so those four are marked `@pytest.mark.xfail(
strict=True, reason="T202 not implemented yet")`. The negative half asserts behaviour the checks
already have: each one already fails on an id, a kind or a key that is genuinely defined nowhere,
with or without a second feature in the picture, and T202 must not lose that guard while widening
the check. Run against the checks as they stand today, every negative half already passes, so none
of the four carries the marker — carrying it on a test that is already green would turn the suite
red the moment it lands (CLAUDE.md's test-first convention, and the reason `strict=True` is what
forces T202 to remove each marker rather than merely permitting it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# --------------------------------------------------------------------------------- (a) task-refs


@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")
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


# ------------------------------------------------------------------------------- (b) alert-kinds


@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")
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


# ------------------------------------------------------------------------------ (c) env-consumed


@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")
def test_env_consumed_passes_for_a_key_consumed_by_a_task_in_another_feature(
    tmp_path: Path,
) -> None:
    """A behavioural `.env.example` key this feature never mentions, but that a task in a
    *different* feature reads, must not be reported as consumed by nothing — the key has a reader,
    just not one inside this feature's own `tasks.md`."""
    import scripts.checks.spec_lint as spec_lint

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


def test_env_consumed_fails_for_a_key_consumed_by_no_task_anywhere(tmp_path: Path) -> None:
    """The negative half: a behavioural key that no task, in this feature or any other, ever
    mentions must still be reported — a key that tunes behaviour and is read by nothing is exactly
    the gap this check exists to catch."""
    import scripts.checks.spec_lint as spec_lint

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


# --------------------------------------------------------------------- (d) register-commitments


@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")
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
