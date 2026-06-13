from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Any, List, Literal, Optional, Union
import json
import os

from sim_app.services import StructureFactory, ModalService, TimeSimulationService


# ---------------------------------------------------------------------------
# WebSocket payload schema
# ---------------------------------------------------------------------------

class ModelRequest(BaseModel):
    Hc:              List[Any]
    Ec:              List[Any]
    Ic:              List[Any]
    Lb:              List[Any]
    depth:           float = Field(gt=0)
    floor_mass:      Union[float, List[float]]
    base_condition:  int   = Field(default=1, ge=0, le=1)
    damping_ratios:  Optional[List[float]] = None


class ForceFunction(BaseModel):
    type:     Literal["continuous", "pulse", "earthquake"] = "pulse"
    amp:      float = 1000.0
    freq:     float = 0.0
    duration: float = Field(default=2.0, ge=0)


class InitialConditions(BaseModel):
    x0: Optional[List[float]] = None
    v0: Optional[List[float]] = None


class SimRequest(BaseModel):
    t0:                 float            = Field(default=0.0,  ge=0)
    tf:                 float            = Field(default=60.0, gt=0)
    dt:                 float            = Field(default=0.02, gt=0)
    speed:              float            = Field(default=1.0,  gt=0)
    force_function:     ForceFunction    = Field(default_factory=ForceFunction)
    damping_ratios:     List[float]      = Field(default_factory=lambda: [0.02])
    initial_conditions: InitialConditions = Field(default_factory=InitialConditions)


class WsPayload(BaseModel):
    model_req: ModelRequest
    sim_req:   SimRequest = Field(default_factory=SimRequest)

app = FastAPI()

# הגדרות CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === הגדרת נתיבים לקבצים סטטיים ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# 1. נתיב לדף הראשי
@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# 2. נתיב לקובץ ה-JavaScript (התיקון לבעיה שלך!)
@app.get("/main.js")
async def read_main_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "main.js"))

# 3. נתיב לקובץ ה-CSS
@app.get("/style.css")
async def read_style_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

# 4. מאפשר גישה לשאר הקבצים (כמו תמונות אם יהיו) דרך /static
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# === WebSocket Endpoint ===
@app.websocket("/ws/simulate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        raw_text = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    # 1. JSON parse — malformed JSON never reaches the schema layer
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        await websocket.send_json({"type": "ERROR", "message": f"Invalid JSON: {e}"})
        await websocket.close()
        return

    # 2. Schema validation — missing/wrong fields produce a clear field-level report
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

    # 3. Simulation — runtime faults are caught and forwarded as structured ERROR frames
    try:
        model = StructureFactory.create_shear_building(ws_payload.model_req.model_dump())
        simulator = TimeSimulationService()
        async for result in simulator.run(model, ws_payload.sim_req.model_dump()):
            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Simulation error: {e}")
        try:
            await websocket.send_json({"type": "ERROR", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# === API רגיל (חישוב מטריצות) ===
@app.post("/shear-building/modal")
async def calculate_modal_properties(payload: dict):
    try:
        if payload:
            model = StructureFactory.create_shear_building(payload)
            modal_service = ModalService()
            return modal_service.run(model)
        raise HTTPException(status_code=400, detail="Missing configuration.")
    except Exception as e:
        print(f"Error during Modal Calculation: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")