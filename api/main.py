from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <-- ייבוא חדש
from fastapi.responses import FileResponse  # <-- ייבוא חדש
import json
import os

# וודא שהנתיב תקין (משתמשים ב-sim_app/services)
from sim_app.services import StructureFactory, ModalService, TimeSimulationService

app = FastAPI()

# הגדרות CORS (נשארות למקרה שתרצה לעבוד גם דרך PyCharm)
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:63342",
    "http://localhost:63342",
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === WebSocket Endpoint ===
@app.websocket("/ws/simulate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected via WebSocket")

    try:
        data = await websocket.receive_text()
        payload = json.loads(data)

        model_req = payload.get("model_req", {})
        sim_req = payload.get("sim_req", {})

        if model_req:
            model = StructureFactory.create_shear_building(model_req)
            simulator = TimeSimulationService()
            async for result in simulator.run(model, sim_req):
                await websocket.send_json(result)

    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print(f"Simulation error: {e}")
        await websocket.send_json({"type": "ERROR", "message": str(e)})
    finally:
        try:
            await websocket.close()
        except:
            pass


# === API רגיל ===
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


# === הגשת דף הבית (החלק החדש!) ===
# מוודא שהשרת יודע איפה התיקייה נמצאת ביחס לקובץ המריץ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


# נתיב שמגיש את index.html כשנכנסים לכתובת הראשי (/)
@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# (אופציונלי) אם בעתיד יהיו תמונות/CSS נפרדים, השורה הזו תאפשר גישה אליהם
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")