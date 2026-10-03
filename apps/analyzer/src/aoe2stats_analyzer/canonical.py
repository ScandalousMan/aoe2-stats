"""Canonical serialisation of a published analysis document (T659, FR-041, SC-004).

`canonical_bytes` is the one serialisation `run.py` stores, and `compared_body` is the same bytes
minus the **wall-clock set**: the version 2 `envelope` and the legacy top-level `extracted_at` that
stays for one version because the web reader requires it there. Everything outside that set is a
pure function of the analysis identity (FR-040), so two runs under one identity are byte-identical
there, in this process or a fresh one. The identity digest excludes the wall clock for the same
reason: `AnalysisIdentity` has no field for it.

**The rules, each decided per field and not globally.**

- *Mapping keys are sorted.* A JSON object has no order the reader may rely on, and a dict's
  insertion order is an accident of the producer. Keys are written as strings; two keys that
  collide as strings are refused.
- *A list keeps its order unless the order is a hash- or declaration-order accident.* Lists whose
  order carries meaning are left alone: `participants` (the adapter's player-number order),
  `participants[].builds|trainings|researches` (the command stream, in time), and the `inferred`
  episodes (time order). Sorting any of them would be a bug. The set-like lists are the table
  `_SET_LIKE` below, and they are sorted: `provenance.*.inputs` and `knowledge_gaps[].prevents`
  (sets of register ids, produced today in register declaration order), `inferred.*[].unit_objects`
  (a group of unit objects), and `knowledge_gaps` itself (a set of gap records). A list this module
  does not know is a stream: the safe default is to preserve it.
- *One float format.* A float is rounded to `FLOAT_DECIMALS` (6) decimal places and written as the
  shortest text that reads back as that rounded double (`repr`, which JSON uses). `0.1 + 0.2` and
  `0.3` therefore both write `0.3`: a value that differs only by how it was computed (summation
  order, a different libm) must not move the bytes. Negative zero is written `0.0`. A float stays
  a float (`2.0` is `2.0`, not `2`), so a type does not change under the reader. `nan` and the
  infinities are refused: JSON has no spelling for them and a silent `null` would be a lie.
- *UTF-8, no escaping of non-ASCII, compact separators, no trailing newline or whitespace.*

Standard library only: this module is on the request path (FR-049).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, Final

__all__ = [
    "FLOAT_DECIMALS",
    "WALL_CLOCK_FIELDS",
    "canonical_bytes",
    "compared_body",
]

#: The top-level keys that are not a function of the identity: when the analysis ran.
WALL_CLOCK_FIELDS: Final = frozenset({"envelope", "extracted_at"})

#: Decimal places a float is rounded to before it is written. Six is micro-units of everything the
#: document carries (actions per minute is the only float today); more would only expose noise.
FLOAT_DECIMALS: Final = 6

_ANY: Final = "*"
_ITEMS: Final = "[]"

#: Paths whose list is a set: sorted by value. A path is the mapping keys from the top level, with
#: `*` for any key and `[]` for "each item of a list".
_SET_LIKE_SCALARS: Final[tuple[tuple[str, ...], ...]] = (
    ("provenance", _ANY, "inputs"),
    ("knowledge_gaps", _ITEMS, "prevents"),
    ("inferred", _ANY, _ITEMS, "unit_objects"),
)
#: Paths whose list is a set of records: sorted by each record's own canonical text.
_SET_LIKE_RECORDS: Final[tuple[tuple[str, ...], ...]] = (("knowledge_gaps",),)


def canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """The document as the bytes `run.py` stores. Pure: the same mapping always yields the same
    bytes, whatever order its keys were inserted in."""
    return _dumps(_normalise(document, ()))


def compared_body(document: Mapping[str, Any]) -> bytes:
    """`canonical_bytes` of the document minus exactly `WALL_CLOCK_FIELDS` (SC-004). Anything else
    changing changes these bytes."""
    return canonical_bytes({k: v for k, v in document.items() if k not in WALL_CLOCK_FIELDS})


def _dumps(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _matches(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    return len(pattern) == len(path) and all(
        want in (_ANY, have) for want, have in zip(pattern, path, strict=True)
    )


def _normalise(value: Any, path: tuple[str, ...]) -> Any:
    """The value with float format applied, keys as strings, and set-like lists put in order."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            text = str(key)
            if text in out:
                raise ValueError(f"two keys serialise to {text!r} at {'.'.join(path) or '<root>'}")
            out[text] = _normalise(item, (*path, text))
        return out
    if isinstance(value, (list, tuple)):
        items = [_normalise(item, (*path, _ITEMS)) for item in value]
        if any(_matches(pattern, path) for pattern in _SET_LIKE_SCALARS):
            return sorted(items)
        if any(_matches(pattern, path) for pattern in _SET_LIKE_RECORDS):
            return sorted(items, key=_dumps)
        return items
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{value!r} at {'.'.join(path)} has no JSON spelling")
        # `+ 0.0` turns negative zero, including one produced by rounding, into zero.
        return round(value, FLOAT_DECIMALS) + 0.0
    return value
