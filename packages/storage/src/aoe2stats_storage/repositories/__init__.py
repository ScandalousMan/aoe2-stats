"""Repositories over the schema in `aoe2stats_storage.models`.

`base` holds what every repository shares — the async engine, the session factory, one unit of
work, and the `Repository` base class. Everything domain-specific (the claim query, the matches
list, the ratings history) belongs to its own module here, not to `base`.
"""
