"""GDPR use cases: export (T090), erasure (T091) and the third-party objection's own instrument
(T092, not yet written — `erasure.py`'s `pseudonymise_profile` is the instrument it will call).
Pure logic only — see `export.py`'s module docstring for why this package holds no SQL and no
object-store call, the same split `alerting.py` already draws one level up in this package.
"""
