# Dynami-Learn — Full Project Analysis

> **Last verified:** 2026-07-25 (no git history in this checkout)

---

## 1. What the Project Does

**Dynami-Learn** is an educational structural dynamics simulator for multi-story shear buildings. It allows students and engineers to:

- Define a building structure (1–3 stories) with custom material and geometric properties
- Compute the mass matrix (M), stiffness matrix (K), natural frequencies, periods, and mode shapes via modal analysis
- Run a real-time time-history simulation with Newmark-Beta integration, streamed live to the browser over WebSocket
- Apply three types of dynamic loading: continuous harmonic force, pulsed harmonic force, or El Centro 1940 earthquake ground motion
- Visualize the building's deformed shape on a live canvas, and plot displacement/velocity/acceleration time-histories per natural mode

It is designed as a learning tool for structural dynamics courses, built at Ben-Gurion University.

---

## 2. Technologies and Libraries

### Backend (Python)

| Library | Role |
|---|---|
| `FastAPI` | REST + WebSocket API server |
| `uvicorn` | ASGI server |
| `numpy` | All matrix/numerical operations |
| `scipy` | RK45 ODE solver via `response.py` (used in tests) |
| `pydantic` | WebSocket payload schema validation |
| `asyncio` | Async generator for streaming simulation data |

### Frontend (Vanilla JS + HTML/CSS)

| Technology | Role |
|---|---|
| Chart.js v4.4.1 (CDN) | Real-time line charts (displacement, velocity, acceleration) |
| HTML5 Canvas API | Building visualizer animation |
| Native WebSocket API | Real-time simulation streaming |
| Native `fetch` API | One-shot modal calculation |
| CSS Variables + Grid/Flexbox | Dark-theme responsive layout |

No build system, no framework, no bundler — the frontend is plain HTML/CSS/JS.

---

## 3. Project Structure

```
Dynami-Learn/
│
├── api/
│   ├── __init__.py
│   └── main.py              ← FastAPI app, routes, WebSocket endpoint
│
├── sim_core/                ← Pure physics/math, no I/O
│   ├── __init__.py
│   ├── structures.py        ← StructureModel, ShearBuilding, SingleDOF dataclasses
│   ├── matrices.py          ← mass_matrix_lumped(), stiffness_shear_structure()
│   ├── modal.py             ← ModalAnalyzer, ModalResult
│   ├── earthquakes.py       ← El Centro 1940 record + inertia force calculator
│   └── response.py          ← TimeIntegrator (scipy RK45) — used only in tests
│
├── sim_app/
│   ├── __init__.py
│   └── services.py          ← StructureFactory, ModalService, TimeSimulationService
│
├── frontend/
│   ├── index.html           ← Single-page UI
│   ├── main.js              ← All frontend logic
│   └── style.css            ← Stylesheet
│
├── tests/
│   └── test_core.py         ← 14 pytest unit tests for sim_core
│
├── scripts/
│   ├── run_dev.py           ← Debug script: print M, K, C matrices
│   ├── run_shear_demo.py    ← End-to-end demo (modal + time integration)
│   ├── services_check.py    ← Integration check for service layer
│   ├── resonance_check.py   ← Physics validation: resonance amplification
│   ├── sanity_check.py      ← Engineering sanity check (T1 plausibility)
│   └── api_smoke_check.py   ← Live API smoke test (requires server running)
│
├── requirements.txt         ← Production dependencies
├── requirements-dev.txt     ← Development/test dependencies (pytest, requests)
├── pyproject.toml           ← Pytest config: testpaths = ["tests"]
└── render.yaml              ← Render.com deployment config
```

### Data Flow

```
Browser (index.html + main.js)
  │
  ├─ POST /shear-building/modal ──► StructureFactory → ModalService → JSON response
  │
  └─ WS /ws/simulate ─────────────► StructureFactory → TimeSimulationService
                                      (async generator, yields DATA frames at dt=0.02s)
                                      ◄── streaming JSON back to browser
```

---

## 4. Main Features Implemented

### Physics Engine

- Lumped-mass shear building model with 2 column lines per story
- Non-uniform floor masses and Young's moduli per floor (each floor independently configurable)
- Fixed and pinned base conditions (`base_condition` parameter)
- Circular and rectangular column cross-sections (moment of inertia computed in frontend)
- Modal analysis via generalized eigenvalue problem `Kφ = λMφ` (numpy `eig` solver)
- Rayleigh proportional damping: `C = αM + βK`, coefficients computed from the first two natural frequencies and a target damping ratio
- Newmark-Beta implicit integration (constant average acceleration: γ=0.5, β=0.25) — unconditionally stable
- El Centro 1940 N-S earthquake record (simplified key-point representation, linearly interpolated)

### API

- Single modal analysis endpoint (`POST /shear-building/modal`)
- Real-time WebSocket simulation streaming with Pydantic schema validation on payload
- Pause/Resume support via `initial_conditions` (position and velocity state preserved client-side)
- CORS middleware (open to all origins, credentials disabled)
- Static file serving for the frontend

### Frontend UI

- Dark-theme professional dashboard layout
- Dynamic sidebar: inputs regenerate when story count changes (1–3)
- Per-floor mass (tons) and Young's modulus (GPa) sliders with synchronized number inputs
- Column profile selector (circular/rectangular) with live moment of inertia display
- Per-mode resonance frequency preset buttons ("Set M1", "Set M2")
- Live building deformation canvas visualizer
- Tabbed multi-chart display (one tab per natural mode), x-axis normalized by period `t/Tₙ`
- Toggle visibility of displacement/velocity/acceleration traces
- Time-scroll slider for reviewing past simulation data
- Simulation speed selector (wired to backend)
- "Stale results" warning overlay when parameters change without recalculating
- Draggable info tooltips on key parameters
- Font size controls, fullscreen toggle
- Responsive layout for mobile widths

---

## 5. Bugs, Issues, and Areas Needing Improvement

All 20 originally-tracked bugs (see `BUGFIX_PLAN.md`, rows 1–20) have been resolved. Four additional issues were identified in the 2026-07-25 review and addressed in the same pass:

| # | Finding | Status |
|---|---------|--------|
| 21 | `scipy` and `pydantic` missing from `requirements.txt` — fresh install broke on import | Fixed |
| 22 | `allow_credentials=True` with `allow_origins=["*"]` is invalid per the CORS/Fetch spec | Fixed |
| 23 | Four root-level scripts still used the `floor_load` key after the `floor_mass` rename, causing `TypeError` at runtime | Fixed |
| 24 | Root-level `test_*.py` files were collected by bare `pytest`, breaking CI with missing-`requests` import errors | Fixed |

### Remaining low-priority items

The following items from the original analysis are lower priority and have not yet been addressed:

- `TimeIntegrator` (scipy RK45) in `response.py` is no longer used by the main application flow — it survives only because the test suite exercises it. It can be removed or moved to a `tests/` helper once the tests are updated to use the Newmark-Beta helper already in `test_core.py`.
- `mass_matrix_lumped()` and `stiffness_shear_structure()` in `matrices.py` are tested but not called by `ShearBuilding.from_floor_data()`, which builds M and K inline. The two implementations should be consolidated.
- The `ModalService` / `StructureFactory` service layer has no integration tests — the REST endpoint is only exercised by `scripts/api_smoke_check.py` when a live server is running.
