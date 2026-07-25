# Dynami-Learn — Bug Fix Plan

> **Last verified:** 2026-07-25 (no git history in this checkout)

| # | Title | Priority | Status | What needs to be done |
|---|-------|----------|--------|-----------------------|
| 1 | `__init__.py` filename typos | Fix immediately | Fixed | Rename `_init_.py` / `_init__.py` files to `__init__.py` in all three packages |
| 2 | `floor_load` → `floor_mass` rename not propagated | Fix immediately | Fixed | Update `run_dev.py` and `tests/test_core.py` call sites to use `floor_mass=` keyword |
| 3 | Async generator called as sync in test files | Fix immediately | Fixed | Rewrite `run_services_test.py` and `test_resonance.py` to iterate the async generator correctly |
| 4 | Earthquake scale factor slider has no effect | Fix immediately | Fixed | Send `numFVal` (not hardcoded `1000`) as `amp` in `wsPayload` when in earthquake mode |
| 5 | Stiffness matrix test asserts wrong shape | Fix immediately | Fixed | Replace `np.diag(Kstory)` assertion with the correct tridiagonal expected matrix |
| 6 | Speed selector is non-functional | Fix soon | Fixed | Include `sim-speed` value in the WebSocket payload and honour it in `TimeSimulationService.run()` |
| 7 | All chart tabs display top-floor data only | Fix soon | Fixed | Use `msg.all_x[i]` / `msg.all_v[i]` for each chart tab's floor index |
| 8 | Visualizer displacement scale never adapts | Fix soon | Fixed | Update `maxAbsDisp` each frame from `msg.all_x` values so canvas scaling is dynamic |
| 9 | `ws.onclose` double-close corrupts pause/resume state | Fix soon | Fixed | Guard `ws.onclose` so it only updates UI state without calling `ws.close()` again |
| 10 | Story height, beam span, depth hardcoded | Fix soon | Fixed | Add UI inputs for `Hc`, `Lb`, and `depth` and wire them into `getModelPayload()` |
| 11 | `response.py` / `TimeIntegrator` is dead code | Housekeeping | Fixed | Remove or clearly isolate `TimeIntegrator`; strip the stray `print` debug statement |
| 12 | `matrices.py` functions unused, duplicate inline logic | Housekeeping | Fixed | Replace inline M/K construction in `ShearBuilding.from_floor_data()` with calls to `matrices.py` |
| 13 | `damping_ratio` param in `from_floor_data` is dead | Housekeeping | Fixed | Remove the unused `damping_ratio` parameter from `from_floor_data()` signature |
| 14 | `Hc` uses only column 0 for story height | Housekeeping | Fixed | Use both column heights (or enforce a single-height input) instead of silently ignoring column 1 |
| 15 | `run_services_test.py` tests outdated API contract | Housekeeping | Fixed | Remove or update the `max_displacement` key assertion to match the current output format |
| 16 | `Array.fill()` shares object reference | Housekeeping | Fixed | Replace `Array(dofs).fill([6.0, 6.0])` with `Array.from({length: dofs}, () => [6.0, 6.0])` |
| 17 | "Quake End" label shown on pulse-type charts | Housekeeping | Fixed | Rename the chart plugin label from `'Quake End'` to `'Force End'` |
| 18 | Mass tooltip describes outdated load-per-area model | Housekeeping | Fixed | Update tooltip text to reflect the current direct-mass-in-tons input model |
| 19 | Simulation `tf` hardcoded at 60 s | Housekeeping | Fixed | Read `tf` from the WebSocket payload in `services.py` instead of ignoring it |
| 20 | No schema validation on WebSocket endpoint | Housekeeping | Fixed | Add a Pydantic model for the WebSocket payload and validate on entry |
| 21 | Missing `scipy` and `pydantic` in `requirements.txt` | Fix immediately | Fixed | Added both to `requirements.txt`; added `pytest` and `requests` to new `requirements-dev.txt` |
| 22 | CORS `allow_credentials=True` with wildcard origin is spec-invalid | Fix immediately | Fixed | Set `allow_credentials=False` in `CORSMiddleware` — no cookie/session auth is used |
| 23 | `floor_load` key still used in root scripts after `floor_mass` rename | Fix immediately | Fixed | Updated key in all four scripts; relocated all to `scripts/` with non-`test_` names |
| 24 | Root-level test files break bare `pytest` collection | Fix immediately | Fixed | Added `pyproject.toml` with `testpaths = ["tests"]`; scripts renamed and moved to `scripts/` |
