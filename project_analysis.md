# Dynami-Learn — Full Project Analysis

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
| `scipy` (indirect) | RK45 ODE solver via `response.py` (unused in main flow) |
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
│   ├── __init__.py  (typo: api/_init__.py)
│   └── main.py          ← FastAPI app, routes, WebSocket endpoint
│
├── sim_core/            ← Pure physics/math, no I/O
│   ├── __init__.py  (typo: sim_core/_init_.py)
│   ├── structures.py    ← StructureModel, ShearBuilding, SingleDOF dataclasses
│   ├── matrices.py      ← mass_matrix_lumped(), stiffness_shear_structure()
│   ├── modal.py         ← ModalAnalyzer, ModalResult
│   ├── earthquakes.py   ← El Centro 1940 record + inertia force calculator
│   └── response.py      ← TimeIntegrator (scipy RK45) — UNUSED in main flow
│
├── sim_app/
│   ├── __init__.py  (typo: sim_app/_init__.py)
│   └── services.py      ← StructureFactory, ModalService, TimeSimulationService
│
├── frontend/
│   ├── index.html       ← Single-page UI, all CSS inlined
│   ├── main.js          ← All frontend logic (~850 lines)
│   └── style.css        ← (minimal, most CSS is in index.html)
│
├── tests/
│   └── test_core.py     ← 7 pytest unit tests for sim_core
│
├── run_dev.py           ← Debug script to print M, K, C matrices
├── run_services_test.py ← Integration test (broken, see bugs)
├── test_resonance.py    ← Resonance validation test (broken, see bugs)
├── test_api_request.py  ← Live API smoke test (requires server running)
└── senity_test.py       ← Sanity test
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
- Real-time WebSocket simulation streaming
- Pause/Resume support via `initial_conditions` (position and velocity state preserved client-side)
- CORS middleware (open to all origins)
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
- Simulation speed selector (UI present — see bugs)
- "Stale results" warning overlay when parameters change without recalculating
- Draggable info tooltips on key parameters
- Font size controls, fullscreen toggle
- Responsive layout for mobile widths

---

## 5. Bugs, Issues, and Areas Needing Improvement

### Critical Bugs

**1. `__init__.py` files have wrong names**

All three package init files have typos:
- `sim_core/_init_.py` — single underscores (should be `__init__.py`)
- `sim_app/_init__.py` — asymmetric underscores (should be `__init__.py`)
- `api/_init__.py` — same issue

Python won't recognize these as packages. Imports only work because scripts manually add paths to `sys.path`. Real package imports will fail.

---

**2. `ShearBuilding.from_floor_data()` parameter renamed, call sites not updated**

The parameter was renamed from `floor_load` to `floor_mass` during a refactor, but two call sites were not updated:
- `run_dev.py:37` — passes `floor_load=floor_load` → `TypeError` at runtime
- `tests/test_core.py:120,224` — same, so `test_shear_building_modal_consistency` and `test_modal_mass_orthogonality_for_shear_building` both crash

---

**3. `TimeSimulationService.run()` is an async generator, but two test files call it as a regular function**

`run_services_test.py:48` and `test_resonance.py:48` call `TimeSimulationService().run(model, sim_payload)` and expect a dict back. The actual method uses `async for` with `yield`, so these tests fail immediately.

---

**4. Earthquake scale factor UI control has no effect**

In `main.js:531`, the force amplitude is hardcoded:
```javascript
amp: 1000,  // always 1000, ignoring the "Scale Factor" slider
```
The backend reads `force_cfg.get("amp")` to scale the earthquake (`services.py:150`), but the frontend never sends the slider value when in earthquake mode. The scale factor control is entirely non-functional.

---

**5. `test_stiffness_shear_structure_diag_like_matlab` test assertion is wrong**

`tests/test_core.py:96` asserts the stiffness matrix equals `np.diag(Kstory)` (a diagonal matrix). But `stiffness_shear_structure()` correctly produces a tridiagonal matrix — which is the proper formulation for a shear building. The test assertion is wrong and will fail.

---

### Significant Issues

**6. Simulation speed selector is non-functional**

The speed dropdown (`#sim-speed`, values 0.25x–2.0x) exists in the UI but its value is never included in the WebSocket payload and never sent to the backend. The `asyncio.sleep(0.005)` in `TimeSimulationService.run()` is hardcoded regardless of selection.

---

**7. Multi-story charts all display the same data (top floor only)**

In `main.js:579`, every chart tab receives the same `msg.x`, `msg.v`, `msg.a` values:
```javascript
chart.data.datasets[0].data.push({ x: normT, y: msg.x });
```
These are top-floor values (`u_next[-1]` in the backend). Tab "Mode 2" and "Mode 3" show identical data to "Mode 1" — only the time normalization differs. If the intent is to show per-floor responses, `msg.all_x[i]` should be used for chart `i`.

---

**8. Building visualizer scale never adapts (`maxAbsDisp` is never updated)**

`maxAbsDisp` is initialized to `0.00001` but is never updated from incoming `msg.x` / `msg.all_x` values during simulation. The canvas scale `sX = (w * 0.3) / dMax` is therefore always fixed, making the visual amplitude meaningless relative to actual structural displacements.

---

**9. `ws.onclose` calls `toggleSimulation()` causing double-close and state corruption**

```javascript
ws.onclose = () => { if (isRunning) toggleSimulation(); };
```
`toggleSimulation()` when running calls `ws.close()` again on an already-closed socket and sets `isPaused = true`, corrupting state (the user can then try to resume a simulation the server has already ended).

---

**10. Story height, beam span, and depth are hardcoded in the frontend**

`getModelPayload()` always sends `Hc=3.0m`, `Lb=[6,6]m`, `depth=6m`. Users have no control over these parameters through the UI, limiting educational value for studying the effect of building geometry.

---

### Code Quality Issues

**11. `sim_core/response.py` is dead code in production**

`TimeIntegrator` (scipy RK45 integrator) is only imported in the tests. It also contains a debug `print("➡️ max residual =", ...)` statement that would pollute server output if ever called. The main simulation flow uses `TimeSimulationService` (Newmark-Beta). The two integrator implementations diverge silently.

---

**12. `mass_matrix_lumped()` and `stiffness_shear_structure()` in `matrices.py` are unused**

`ShearBuilding.from_floor_data()` builds M and K inline rather than calling these functions. Both are tested but never used in the application, creating two diverging implementations of the same computation.

---

**13. `damping_ratio` parameter in `from_floor_data` is dead**

```python
def from_floor_data(cls, ..., damping_ratio: float = 0.0)
```
The parameter is declared and accepted but never used inside the function body. Damping is computed later in `TimeSimulationService.run()`.

---

**14. `Hc` uses only column 0 for story height**

```python
h = Hc[i, 0]  # second column ignored silently
```
Even though the data structure supports 2 column lines with potentially different heights, only the left column's height drives the stiffness calculation.

---

**15. `run_services_test.py` tests an outdated API contract**

The test expects `time_result["max_displacement"]` from `TimeSimulationService`, a key that no longer exists in the service's output format.

---

**16. JavaScript `Array.fill()` with object reference**

```javascript
const Lb_arr = Array(dofs).fill([6.0, 6.0]);
```
All elements share the same array reference. While this doesn't cause a bug here (the array is immediately JSON-serialized), it is a JavaScript pitfall that could cause subtle mutations if the array were later modified.

---

**17. "Quake End" label appears on pulse-type charts**

The chart plugin draws a vertical force-end line for the `pulse` type but labels it `'Quake End'` instead of something like `'Force End'`.

---

**18. Tooltip for "mass" describes the old load-per-area (q) model**

```javascript
"mass": { title: "Floor Load (q)", text: "• Seismic weight [kN/m²].\n• Mass (M) = (q × Area) / g." }
```
After the refactor to direct mass input in tons, this tooltip is factually wrong.

---

**19. `tf` is hardcoded at 60 seconds regardless of UI input**

```python
tf = 60.0  # services.py:71
```
Even if a `tf` key is present in the WebSocket payload, it is ignored. The simulation always runs for 60 seconds.

---

**20. No schema validation on the WebSocket endpoint**

`api/main.py` wraps everything in a bare `except Exception` and forwards the error string back over the socket. There is no Pydantic schema validation for incoming payloads, so malformed inputs produce generic server-side stack traces sent to the client.

---

## Priority Summary

| Priority | # | Issue |
|---|---|---|
| Fix immediately | 1 | `__init__.py` filename typos |
| Fix immediately | 2 | `floor_load` → `floor_mass` rename not propagated to call sites |
| Fix immediately | 3 | Async generator called as sync function in two test files |
| Fix immediately | 4 | Earthquake scale factor slider has no effect (hardcoded `amp: 1000`) |
| Fix immediately | 5 | Stiffness matrix test asserts wrong (diagonal) shape |
| Fix soon | 6 | Speed selector UI control is non-functional |
| Fix soon | 7 | All chart tabs display top-floor data only |
| Fix soon | 8 | Visualizer displacement scale is fixed (never adapts) |
| Fix soon | 9 | `ws.onclose` double-close corrupts pause/resume state |
| Fix soon | 10 | Story height, beam span, depth hardcoded (no UI control) |
| Housekeeping | 11 | `response.py` / `TimeIntegrator` is dead production code |
| Housekeeping | 12 | `matrices.py` functions unused, duplicate inline logic |
| Housekeeping | 13 | `damping_ratio` parameter in `from_floor_data` is dead |
| Housekeeping | 17 | "Quake End" label shown for pulse-type force end line |
| Housekeeping | 18 | Mass tooltip describes outdated load-per-area model |
| Housekeeping | 19 | Simulation `tf` hardcoded at 60s, payload value ignored |
| Housekeeping | 20 | No payload schema validation on WebSocket endpoint |
