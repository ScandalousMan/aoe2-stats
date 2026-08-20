"""FastAPI routers, one module per resource in `contracts/http-api.md`.

Every router here is included by `app.py` with `app.include_router(<module>.router,
prefix="/api")` and nothing more elaborate than that — see that module's docstring for why the
pattern is kept this flat.
"""
