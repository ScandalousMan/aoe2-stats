"""Truth tiers, confidence, provenance and the determinability register.

Naming discipline (FR-012, T622). A datum id states what was measured, never what a reader would
like it to mean. This is 003's FR-043b discipline applied to the whole vocabulary, and it is cheap
to hold now and impossible to retrofit once ids are in published documents.

- ``age_up_commands``, not ``age_up_times``: the recording carries the command, and a command is
  not the moment the age was reached.
- ``villagers_ordered``, not ``villagers``: an order is not a unit that exists.
- ``builds``, not ``built``: a placement command is not a finished building.

An id is two or more dot-separated segments, each lowercase ``[a-z][a-z0-9_]*``. The register
loader (``register.py``) refuses an id of another shape, and refuses one whose segment carries an
outcome word (``times``, ``built``) or is the bare outcome noun ``villagers``. A clock value is a
field of a command (``..._ms``), not a datum named after the time it is hoped to give.
"""
