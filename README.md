# Dynami-Learn

An interactive structural dynamics simulator for teaching. Students define a small multi-story building, see its natural frequencies and mode shapes, and watch it respond in real time to dynamic loads, including the 1940 El Centro earthquake.

Built at Ben-Gurion University as part of the "360" initiative of the Faculty of Civil Engineering.

**Live demo:** https://dynami-learn.onrender.com/
*(hosted on a free plan, so the first load may take a few seconds)*

## Features

- **Configurable building:** 1–3 stories, with mass and Young's modulus set per floor, circular or rectangular columns, and a fixed or pinned base
- **Modal analysis:** mass and stiffness matrices, natural frequencies, periods and mode shapes
- **Real-time simulation:** the backend integrates the equations of motion step by step and streams the results to the browser over a WebSocket
- **Three load types:** continuous harmonic force, pulsed harmonic force, or the El Centro 1940 ground motion
- **Live visualization:** an animated drawing of the deforming building, plus displacement, velocity and acceleration charts for each mode
- **Classroom tools:** one-click "resonance" presets, pause and resume, a time slider for reviewing past results, and adjustable simulation speed

## How it works

```
Browser (HTML + JavaScript)
  ├─ POST /shear-building/modal  → modal analysis → JSON response
  └─ WebSocket /ws/simulate      → time simulation → stream of results
```

The physics engine (`sim_core/`) is pure Python and NumPy with no I/O:
- Shear-building model with lumped masses
- Modal analysis by solving the generalized eigenvalue problem `Kφ = λMφ`
- Rayleigh damping (`C = αM + βK`) based on a target damping ratio
- Newmark-Beta time integration (average acceleration method)

A service layer (`sim_app/`) builds the models and runs the simulations, and the API layer (`api/`) exposes them. Incoming simulation requests are validated with Pydantic before anything runs.

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, NumPy, SciPy, Pydantic
- **Frontend:** plain HTML, CSS and JavaScript, Chart.js, HTML5 Canvas, WebSocket API
- **Deployment:** Render
- **Desktop version:** pywebview, packaged with PyInstaller

## Running locally

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

### Desktop app
```bash
pip install -r requirements.txt -r requirements-desktop.txt
python desktop_app.py
```

### Tests
```bash
pip install -r requirements-dev.txt
pytest
```

The `scripts/` folder also contains physics sanity checks (for example, checking that the response grows near resonance) and a smoke test for a running server.

## Project structure

```
api/          FastAPI app: REST and WebSocket endpoints
sim_core/     physics engine: models, matrices, modal analysis, earthquake record
sim_app/      service layer between the API and the physics engine
frontend/     single-page user interface
tests/        unit tests for the physics engine
scripts/      validation and demo scripts
desktop_app.py  runs the app in a desktop window
```
