from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, ValidationError, model_validator
from typing import Any, List, Literal, Optional, Union
import json
import math
import os

from sim_app.services import StructureFactory, ModalService, TimeSimulationService

# ---------------------------------------------------------------------------
# Resource / safety limits — tune here, not scattered through the code
# ---------------------------------------------------------------------------

MAX_DOFS             = 20          # stories; generous vs. the UI's 1-3 design
MAX_TF               = 600.0       # seconds; cap on simulation duration
MIN_DT               = 1e-4        # seconds; floor on time step (prevents runaway step count)
MAX_SPEED            = 10.0        # playback speed multiplier (UI max is 2.0)
MAX_WS_MESSAGE_BYTES = 1_048_576   # 1 MiB; explicit app gate before json.loads

# ---------------------------------------------------------------------------
# CORS — set ALLOWED_ORIGINS env var in production (e.g. on Render)
# ---------------------------------------------------------------------------

_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,https://dynami-learn.onrender.com",
)
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]

# ---------------------------------------------------------------------------
# WebSocket payload schema
# ---------------------------------------------------------------------------

class ModelRequest(BaseModel):
    Hc:             List[Any]
    Ec:             List[Any]
    Ic:             List[Any]
    Lb:             List[Any]
    depth:          float = Field(gt=0)
    floor_mass:     Union[float, List[float]]
    base_condition: int   = Field(default=1, ge=0, le=1)
    damping_ratios: Optional[List[float]] = None

    @model_validator(mode='after')
    def _validate_structure(self) -> 'ModelRequest':
        dofs = len(self.Hc)

        if dofs == 0:
            raise ValueError("Hc must have at least one entry (dofs >= 1)")
        if dofs > MAX_DOFS:
            raise ValueError(
                f"Model has {dofs} stories; maximum allowed is MAX_DOFS={MAX_DOFS}"
            )

        # All story arrays must have the same row count as Hc
        for name, arr in [("Ec", self.Ec), ("Ic", self.Ic), ("Lb", self.Lb)]:
            if len(arr) != dofs:
                raise ValueError(
                    f"{name} has {len(arr)} rows; expected {dofs} to match Hc"
                )
        if isinstance(self.floor_mass, list) and len(self.floor_mass) != dofs:
            raise ValueError(
                f"floor_mass has {len(self.floor_mass)} entries; expected {dofs} to match Hc"
            )

        # All physical values must be finite and in a sensible range
        def _check(field_name: str, data: list, allow_zero: bool = False) -> None:
            for ri, row in enumerate(data):
                items = row if isinstance(row, list) else [row]
                for ci, v in enumerate(items):
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        raise ValueError(f"{field_name}[{ri}][{ci}] is not a number")
                    if not math.isfinite(fv):
                        raise ValueError(f"{field_name}[{ri}][{ci}] is not finite")
                    if allow_zero and fv < 0:
                        raise ValueError(f"{field_name}[{ri}][{ci}] must be >= 0")
                    if not allow_zero and fv <= 0:
                        raise ValueError(f"{field_name}[{ri}][{ci}] must be > 0")

        _check("Hc", self.Hc)                      # story height: strictly positive
        _check("Ec", self.Ec)                      # Young's modulus: strictly positive
        _check("Ic", self.Ic)                      # moment of inertia: strictly positive
        _check("Lb", self.Lb, allow_zero=True)     # beam span: >= 0 (last col is often 0)

        # depth is already validated gt=0 by Field, but Inf passes gt; check finiteness
        if not math.isfinite(self.depth):
            raise ValueError("depth must be finite")

        masses = self.floor_mass if isinstance(self.floor_mass, list) else [self.floor_mass]
        for i, m in enumerate(masses):
            if not math.isfinite(m) or m <= 0:
                raise ValueError(f"floor_mass[{i}] must be finite and positive")

        return self


class ForceFunction(BaseModel):
    type:     Literal["continuous", "pulse", "earthquake"] = "pulse"
    amp:      float = 1000.0
    freq:     float = 0.0
    duration: float = Field(default=2.0, ge=0)


class InitialConditions(BaseModel):
    x0: Optional[List[float]] = None
    v0: Optional[List[float]] = None


class SimRequest(BaseModel):
    t0:                 float             = Field(default=0.0,  ge=0)
    tf:                 float             = Field(default=60.0, gt=0,    le=MAX_TF)
    dt:                 float             = Field(default=0.02, ge=MIN_DT)
    speed:              float             = Field(default=1.0,  gt=0,    le=MAX_SPEED)
    force_function:     ForceFunction     = Field(default_factory=ForceFunction)
    damping_ratios:     List[float]       = Field(default_factory=lambda: [0.02])
    initial_conditions: InitialConditions = Field(default_factory=InitialConditions)


class WsPayload(BaseModel):
    model_req: ModelRequest
    sim_req:   SimRequest = Field(default_factory=SimRequest)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Static file serving ===
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/main.js")
async def read_main_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "main.js"))

@app.get("/style.css")
async def read_style_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# === WebSocket endpoint ===
@app.websocket("/ws/simulate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        raw_text = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    # 1. App-level message-size gate — explicit, not relying on library defaults
    if len(raw_text.encode()) > MAX_WS_MESSAGE_BYTES:
        await websocket.send_json({
            "type": "ERROR",
            "message": f"Message too large (limit {MAX_WS_MESSAGE_BYTES // 1024} KiB).",
        })
        await websocket.close()
        return

    # 2. JSON parse
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        await websocket.send_json({"type": "ERROR", "message": f"Invalid JSON: {e}"})
        await websocket.close()
        return

    # 3. Schema + domain validation (ModelRequest.model_validator runs here)
    try:
        ws_payload = WsPayload.model_validate(raw)
    except ValidationError as e:
        errors = [
            {"field": " -> ".join(str(p) for p in err["loc"]), "detail": err["msg"]}
            for err in e.errors()
        ]
        await websocket.send_json({"type": "ERROR", "message": "Invalid payload", "errors": errors})
        await websocket.close()
        return

    # 4. Simulation
    try:
        model = StructureFactory.create_shear_building(ws_payload.model_req.model_dump())
        async for result in TimeSimulationService().run(model, ws_payload.sim_req.model_dump()):
            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Simulation error: {e}")
        try:
            await websocket.send_json({
                "type": "ERROR",
                "message": "Simulation failed — invalid input or internal error.",
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# === REST endpoint (modal analysis only) ===
@app.post("/shear-building/modal")
async def calculate_modal_properties(payload: ModelRequest):
    """
    Accepts the same ModelRequest schema as the WebSocket endpoint so all
    validation (dofs cap, finiteness, range checks) runs automatically.
    """
    try:
        model = StructureFactory.create_shear_building(payload.model_dump())
        return ModalService().run(model)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during Modal Calculation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Modal calculation failed — invalid input or internal error.",
        )
