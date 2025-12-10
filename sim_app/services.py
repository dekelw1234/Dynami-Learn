from __future__ import annotations
import numpy as np
from sim_core.structures import SingleDOF, ShearBuilding
from sim_core.modal import ModalAnalyzer
import asyncio


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
        Ec = np.array(payload["Ec"]) * 1.0e9
        Ic = np.array(payload["Ic"])

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
    async def run(self, model, payload: dict):
        # 1. קריאת תנאי התחלה (עבור Pause/Resume)
        t0 = float(payload.get("t0", 0.0))
        dt = float(payload.get("dt", 0.02))
        tf = 60.0  # זמן מקסימלי לריצה רצופה

        # קבלת מצב קודם אם קיים (Pause/Resume)
        init_cond = payload.get("initial_conditions", {})
        x0_vec = init_cond.get("x0", None)
        v0_vec = init_cond.get("v0", None)

        dofs = model.dofs
        u = np.array(x0_vec) if x0_vec else np.zeros(dofs)
        v = np.array(v0_vec) if v0_vec else np.zeros(dofs)
        a = np.zeros(dofs)

        # 2. חישוב ריסון (Rayleigh)
        zeta_vec = payload.get("damping_ratios", [0.0] * dofs)
        zeta_val = float(zeta_vec[0]) if zeta_vec else 0.02

        modal = ModalAnalyzer(model).run()
        w = modal.frequencies

        # חישוב מקדמי אלפא/בטא
        w1 = w[0]
        w2 = w[1] if len(w) > 1 else w[0] * 3

        A_mat = np.array([[1 / (2 * w1), w1 / 2], [1 / (2 * w2), w2 / 2]])
        b_vec = np.array([zeta_val, zeta_val])
        try:
            alpha, beta = np.linalg.solve(A_mat, b_vec)
        except:
            alpha, beta = 0.0, 0.0

        model.C = alpha * model.M + beta * model.K
        M, K, C = model.M, model.K, model.C

        # 3. כוח
        force_cfg = payload.get("force_function", {})
        f_amp = float(force_cfg.get("amp", 1000.0))
        f_freq = float(force_cfg.get("freq", 1.0))
        f_type = force_cfg.get("type", "pulse")
        f_dur = float(force_cfg.get("duration", 2.0))

        # 4. Newmark-Beta Setup
        gamma = 0.5
        beta_const = 0.25

        a0 = 1.0 / (beta_const * dt ** 2)
        a1 = gamma / (beta_const * dt)
        a2 = 1.0 / (beta_const * dt)
        a3 = 1.0 / (2.0 * beta_const) - 1.0
        a4 = gamma / beta_const - 1.0
        a5 = (dt / 2.0) * (gamma / beta_const - 2.0)

        K_hat = K + a0 * M + a1 * C
        try:
            K_hat_inv = np.linalg.inv(K_hat)
        except:
            K_hat_inv = np.linalg.pinv(K_hat)

        # 5. INIT
        yield {
            "type": "INIT",
            "dofs": dofs,
            "periods": w.tolist(),
            "duration": f_dur
        }

        # 6. לולאת זמן
        t = t0
        end_time = t0 + tf

        while t < end_time:
            # וקטור כוח
            F = np.zeros(dofs)
            force_val = 0.0

            if f_type == "pulse":
                if t <= f_dur:
                    force_val = f_amp * np.sin(f_freq * t)
            else:  # continuous
                force_val = f_amp * np.sin(f_freq * t)

            if dofs > 0:
                F[-1] = force_val

            # צעד חישוב
            term_M = a0 * u + a2 * v + a3 * a
            term_C = a1 * u + a4 * v + a5 * a
            P_hat = F + M @ term_M + C @ term_C

            u_next = K_hat_inv @ P_hat
            a_next = a0 * (u_next - u) - a2 * v - a3 * a
            v_next = v + dt * ((1.0 - gamma) * a + gamma * a_next)

            # ג. שידור נתונים (התיקון כאן!)
            yield {
                "type": "DATA",
                "t": t,
                "x": u_next[-1],  # עבור הגרף הכחול
                "v": v_next[-1],  # <-- הוספתי: עבור הגרף הירוק!
                "a": a_next[-1],  # עבור הגרף הכתום
                "all_x": u_next.tolist(),
                "all_v": v_next.tolist()  # עבור resume
            }

            u, v, a = u_next, v_next, a_next
            t += dt
            await asyncio.sleep(0.005)