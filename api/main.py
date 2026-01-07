from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import os

# וודא שהייבוא תקין
from sim_app.services import StructureFactory, ModalService, TimeSimulationService

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
    print("Client connected via WebSocket")

    try:
        data = await websocket.receive_text()
        payload = json.loads(data)

        model_req = payload.get("model_req", {})
        sim_req = payload.get("sim_req", {})

        if model_req:
            # כאן המפעל שלך יקבל את המידע החדש (מערכים של מסה וקשיחות)
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