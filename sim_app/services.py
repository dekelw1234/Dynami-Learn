from __future__ import annotations
import numpy as np
from sim_core.structures import SingleDOF, ShearBuilding
from sim_core.modal import ModalAnalyzer
from sim_core.response import TimeIntegrator

# Global variable to track if final damping matrix was printed
DAMPING_CALC_DONE = False


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
    def run(self, model, payload: dict) -> dict:
        global DAMPING_CALC_DONE
        t0 = float(payload["t0"])
        tf = float(payload.get("tf", 60.0))
        dt = float(payload["dt"])

        # === 1. הגנה וקריאת תנאי התחלה ===
        x0_raw = payload.get("x0")
        v0_raw = payload.get("v0")

        if x0_raw is None:
            x0 = np.zeros(model.dofs, dtype=float)
        else:
            x0 = np.array(x0_raw, dtype=float).flatten()

        if v0_raw is None:
            v0 = np.zeros(model.dofs, dtype=float)
        else:
            v0 = np.array(v0_raw, dtype=float).flatten()

        if x0.size != model.dofs: x0 = np.resize(x0, model.dofs)
        if v0.size != model.dofs: v0 = np.resize(v0, model.dofs)

        if not np.all(np.isfinite(x0)) or not np.all(np.isfinite(v0)):
            raise ValueError("Initial conditions contain NaN or Inf values.")

        # === 2. בניית מטריצת ריסון (Rayleigh Damping FIX) ===
        zeta_vec = payload.get("damping_ratios", [0.0] * model.dofs)
        zeta_target = float(zeta_vec[0]) if zeta_vec else 0.05

        modal_res = ModalAnalyzer(model).run()
        w_n = modal_res.frequencies
        Phi = modal_res.modes

        w1 = w_n[0]
        w2 = w_n[1] if model.dofs > 1 else w_n[0] * 1.5

        A = np.array([
            [1 / (2 * w1), w1 / 2],
            [1 / (2 * w2), w2 / 2]
        ])
        b = np.array([zeta_target, zeta_target])

        try:
            alpha, beta = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            alpha, beta = 0.0, 0.0

        model.C = alpha * model.M + beta * model.K

        # --- DEBUG PRINT: Damping Parameters ---
        if not DAMPING_CALC_DONE:
            print("--- DAMPING CALCULATION (Rayleigh) ---")
            print(f"Target Zeta: {zeta_target:.3f}")
            print(f"w1: {w1:.3f} rad/s, w2: {w2:.3f} rad/s")
            print(f"Alpha (α): {alpha:.2e}, Beta (β): {beta:.2e}")
            DAMPING_CALC_DONE = True
        # -------------------------------------

        # === 3. פונקציית הכוח (עם לוגיקת הפסקה) ===
        force_data = payload.get("force_function", {})
        amp = float(force_data.get("amp", 0.0)) * 1000.0
        freq = float(force_data.get("freq", 0.0))

        force_type = force_data.get("type", "continuous")
        duration = float(force_data.get("duration", 15.0))

        # --- DEBUG PRINT: Force Config ---
        print(f"\n--- FORCE CONFIG ---")
        print(f"Type: {force_type}, Duration: {duration}s, Freq: {freq:.2f} Hz")

        # ---------------------------------

        def f_func(t):
            f = np.zeros(model.dofs)
            if model.dofs > 0:
                if force_type == "pulse":
                    if t <= duration:
                        f[-1] = amp * np.sin(freq * t)
                    else:
                        # --- DEBUG PRINT: Force Stop ---
                        if t > duration and t < duration + dt * 2:  # Print only near cutoff
                            print(f"*** FORCE STOPPED at t={t:.2f}s ***")
                        # -------------------------------
                        f[-1] = 0.0
                else:
                    f[-1] = amp * np.sin(freq * t)
            return f

        # === 4. הרצה ===
        integrator = TimeIntegrator(model, f_func)
        result = integrator.run(x0, v0, (t0, tf), dt)

        # === 5. חישוב תאוצות ופירוק ===
        Phi = modal_res.modes  # נדרש שוב לפירוק
        accel_matrix = np.zeros_like(result.x)
        M_inv = np.linalg.inv(model.M)

        for i, t in enumerate(result.t):
            F_t = f_func(t)
            x_t = result.x[:, i]
            v_t = result.v[:, i]

            forces_internal = (model.C @ v_t) + (model.K @ x_t)
            a_t = M_inv @ (F_t - forces_internal)
            accel_matrix[:, i] = a_t

        try:
            q_x = np.linalg.solve(Phi, result.x)
            q_v = np.linalg.solve(Phi, result.v)
            q_a = np.linalg.solve(Phi, accel_matrix)
        except np.linalg.LinAlgError:
            q_x = np.zeros_like(result.x)
            q_v = np.zeros_like(result.v)
            q_a = np.zeros_like(accel_matrix)

        roof_idx = model.dofs - 1
        decomposed_data = {}

        for i in range(model.dofs):
            phi_roof = Phi[roof_idx, i]
            decomposed_data[str(i)] = {
                "x": (phi_roof * q_x[i, :]).tolist(),
                "v": (phi_roof * q_v[i, :]).tolist(),
                "a": (phi_roof * q_a[i, :]).tolist()
            }

        resp = result.as_dict()
        resp["max_displacement"] = float(np.max(np.abs(result.x)))
        resp["a"] = accel_matrix.tolist()
        resp["modal_decomposition"] = decomposed_data
        resp["quake_duration"] = duration
        resp["force_config"] = {
            "type": force_type,
            "duration": duration
        }

        return resp