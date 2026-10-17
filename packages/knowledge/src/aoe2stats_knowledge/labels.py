"""A display label for an entity, looked up in the snapshot a *document* names (T709).

`query.name` answers "what is entity X called for build B", resolving B to the promoted snapshot
for that build. A published analysis needs the other question: "what does the snapshot this
document was produced under call X". Those are different when a knowledge refresh has promoted a
second snapshot for the same build, and FR-027 forbids answering the second question with the
first's machinery: this module takes a snapshot **digest** (the document's
`identity.knowledge.digest`) and matches it exactly against the snapshots the loader finds, with no
build argument, no nearest and no latest.

Two things differ from `query.name`, both deliberate and both at the presentation boundary:

- An id the snapshot does not name is `None`, never the bare id echoed back. The page renders an
  unnamed entity as an unresolved identifier (003 FR-043a), which is only possible if the wire
  says "nothing" rather than a string that looks like a name.
- The vendored names carry the source's line-break markup (``"Town<br>\\nCenter"``, 300+ names per
  snapshot). The snapshot is digested and frozen, so the markup is collapsed to a space here, on the
  way out, not in the data.

Pure and offline: it reads the packaged, immutable snapshot tree through the same cached loaders
`query.py` uses.
"""

from __future__ import annotations

import re

from aoe2stats_knowledge import snapshot
from aoe2stats_knowledge.query import _rules

_LINE_BREAK_MARKUP = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)


def label_in_snapshot(digest: str, kind: str, entity_id: str) -> str | None:
    """The display name of entity (`kind`, `entity_id`) in the loaded snapshot whose identity
    digest is exactly `digest`, or `None`: no loaded snapshot has that digest, or the snapshot does
    not name the entity. `kind` is `"unit"`, `"building"` or `"technology"`; `entity_id` is the
    numeric id spelled as a string, as `rules.json` keys it."""
    for loaded in snapshot.load_all_snapshots():
        if loaded.identity.digest != digest:
            continue
        record = _rules(loaded.directory).get("entities", {}).get(kind, {}).get(entity_id)
        display_name = record.get("name") if record is not None else None
        if not display_name:
            return None
        return _LINE_BREAK_MARKUP.sub(" ", display_name).strip()
    return None
