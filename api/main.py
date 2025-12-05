import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from sim_app.services import (
    StructureFactory,
    ModalService,
    TimeSimulationService,
)

app = FastAPI(title="DynamiLearn API")

# ==========================================
# 1. הגדרת נתיבים לקבצים (Paths)
# ==========================================
# אנחנו מוצאים את המיקום של הקובץ הזה (api/main.py)
# ועולים תיקייה אחת למעלה כדי להגיע לתיקייה הראשית (Dynami-Learn)
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(current_dir, "frontend")

# ==========================================
# 2. CORS (חובה לתקשורת תקינה)
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 3. הגשת קבצים סטטיים
# ==========================================
# זה מאפשר גישה לקבצים בתיקיית frontend (אם נרצה להוסיף CSS/JS נפרדים בעתיד)
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# הנתיב הראשי - מגיש את קובץ ה-HTML
@app.get("/")
def read_root():
    return FileResponse(os.path.join(frontend_path, "index.html"))

# ==========================================
# 4. המודלים (Schemas)
# ==========================================

class SingleDOFModelRequest(BaseModel):
    m: float
    k: float
    c: float = 0.0

class ShearBuildingModelRequest(BaseModel):
    Hc: List[List[float]]
    Ec: List[List[float]]
    Ic: List[List[float]]
    Lb: List[List[float]]
    depth: float
    floor_load: float
    base_condition: int = 1
    damping_ratio: float = 0.0

class TimeSimulationRequest(BaseModel):
    t0: float
    tf: float
    dt: float
    x0: Optional[List[float]] = None
    v0: Optional[List[float]] = None
    force_function: Optional[dict] = None

# ==========================================
# 5. Endpoints (הלוגיקה)
# ==========================================

@app.post("/single-dof/modal")
def single_dof_modal(model_req: SingleDOFModelRequest):
    model = StructureFactory.create_single_dof(model_req.dict())
    return ModalService().run(model)

@app.post("/single-dof/simulate")
def single_dof_simulate(model_req: SingleDOFModelRequest, sim_req: TimeSimulationRequest):
    model = StructureFactory.create_single_dof(model_req.dict())
    return TimeSimulationService().run(model, sim_req.dict())

@app.post("/shear-building/modal")
def shear_building_modal(model_req: ShearBuildingModelRequest):
    model = StructureFactory.create_shear_building(model_req.dict())
    return ModalService().run(model)

@app.post("/shear-building/simulate")
def shear_building_simulate(model_req: ShearBuildingModelRequest, sim_req: TimeSimulationRequest):
    model = StructureFactory.create_shear_building(model_req.dict())
    return TimeSimulationService().run(model, sim_req.dict())