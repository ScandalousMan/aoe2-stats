"""Method identifiers shared by the analysis path and the request path (T709b).

A published datum names the method that produced it (FR-009). Most are assigned in `extract.py`'s
`_METHODS`, which only the analysis path loads. The `names.` family is produced on the request path,
by `names.py`, and recorded by the block it serves, while `_METHODS` has to assign it too, so that
the register's publication gate resolves it. Each of those two reading the other would make the
analysis path load request-path code (or the reverse) for two constants, so the constants live here.

This module imports nothing: it adds no knowledge, truth or request-path import to either reader,
and `tests/architecture/test_feature_006_boundaries.py` keeps it that way.
"""

from __future__ import annotations

from typing import Final

__all__ = ["NAMES_METHOD_ID", "NAMES_METHOD_VERSION"]

#: The method behind every `names.` datum: a lookup of the display name a knowledge snapshot gives
#: an identifier, cleaned of the source's line-break markup. `extract._METHODS` assigns it and
#: `names.py` records it in the block it serves. Version 2: the served label is the cleaned
#: one (`names.clean_label`), where version 1 served the vendored value as it stood.
NAMES_METHOD_ID: Final[str] = "knowledge-snapshot.name"
NAMES_METHOD_VERSION: Final[str] = "2"
