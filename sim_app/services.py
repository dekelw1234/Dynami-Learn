from __future__ import annotations
import numpy as np
from sim_core.structures import SingleDOF, ShearBuilding
from sim_core.modal import ModalAnalyzer
from sim_core.response import TimeIntegrator


class StructureFactory:
    @staticmethod
    def create_single_dof(payload: dict):
        return SingleDOF.from_parameters(
            m=float(payload["m"]) * 1000.0,
            k=float(payload["k"]) * 1000.0,
            c=float(payload.get("c", 0.0)) * 1000.0
        )

    @staticmethod
    def create_shear_building(payload: dict):
        Hc = np.array(payload["Hc"], dtype=float)
        Lb = np.array(payload["Lb"], dtype=float)
        Ec = np.array(payload["Ec"], dtype=float) * 1.0e9
        Ic = np.array(payload["Ic"], dtype=float)

        return ShearBuilding.from_floor_data(
            Hc=Hc, Ec=Ec, Ic=Ic, Lb=Lb,
            depth=float(payload["depth"]),
            floor_load=float(payload["floor_load"]) * 1000.0,
            base_condition=int(payload.get("base_condition", 1))
        )


class ModalService:
    def run(self, model) -> dict:
        modal = ModalAnalyzer(model).run()
        resp = modal.as_dict()
        resp["M_matrix"] = model.M.tolist()
        resp["K_matrix"] = model.K.tolist()
        return resp


class TimeSimulationService:
    def run(self, model, payload: dict) -> dict:
        t0 = float(payload["t0"])
        tf = float(payload["tf"])
        dt = float(payload["dt"])

        # === התיקון הברזל (Bulletproof Fix) ===
        # 1. קריאה בטוחה מה-payload
        x0_raw = payload.get("x0")
        v0_raw = payload.get("v0")

        # 2. אם לא קיים, צור אפסים
        if x0_raw is None:
            x0 = np.zeros(model.dofs, dtype=float)
        else:
            # הופך למערך שטוח ומוודא שהסוג הוא float64
            x0 = np.array(x0_raw, dtype=float).flatten()

        if v0_raw is None:
            v0 = np.zeros(model.dofs, dtype=float)
        else:
            v0 = np.array(v0_raw, dtype=float).flatten()

        # 3. הגנה מפני אורך לא מתאים (משלים באפסים או חותך)
        if x0.size != model.dofs:
            new_x0 = np.zeros(model.dofs, dtype=float)
            min_len = min(x0.size, model.dofs)
            new_x0[:min_len] = x0[:min_len]
            x0 = new_x0

        if v0.size != model.dofs:
            new_v0 = np.zeros(model.dofs, dtype=float)
            min_len = min(v0.size, model.dofs)
            new_v0[:min_len] = v0[:min_len]
            v0 = new_v0

        # 4. בדיקת NaN/Inf סופית
        if not np.all(np.isfinite(x0)) or not np.all(np.isfinite(v0)):
            raise ValueError("Initial conditions contain NaN or Inf values.")
        # ======================================

        force_data = payload.get("force_function", {})
        amp = float(force_data.get("amp", 0.0)) * 1000.0
        freq = float(force_data.get("freq", 0.0))

        def f_func(t):
            f = np.zeros(model.dofs)
            if model.dofs > 0:
                f[-1] = amp * np.sin(freq * t)
            return f

        integrator = TimeIntegrator(model, f_func)
        result = integrator.run(x0, v0, (t0, tf), dt)

        resp = result.as_dict()
        resp["max_displacement"] = float(np.max(np.abs(result.x)))
        return resp