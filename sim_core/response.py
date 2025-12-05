# sim_core/response.py
from dataclasses import dataclass
import numpy as np
from scipy.integrate import solve_ivp

from .structures import StructureModel


@dataclass
class TimeHistoryResult:
    t: np.ndarray
    x: np.ndarray
    v: np.ndarray
    a: np.ndarray

    def as_dict(self) -> dict:
        return {
            "t": self.t.tolist(),
            "x": self.x.tolist(),
            "v": self.v.tolist(),
            "a": self.a.tolist(),
        }


class TimeIntegrator:
    def __init__(self, model: StructureModel, f_func):
        """
        f_func(t) -> vector of size DOFs (כוחות חיצוניים בזמן).
        """
        self.model = model
        self.f_func = f_func

    def run(self,
            x0: np.ndarray,
            v0: np.ndarray,
            t_span: tuple[float, float],
            dt: float) -> TimeHistoryResult:

        M, C, K = self.model.M, self.model.C, self.model.K
        n = self.model.dofs

        def ode(t, y):
            x = y[:n]
            v = y[n:]
            f = self.f_func(t)
            rhs = f - C @ v - K @ x
            a = np.linalg.solve(M, rhs)
            return np.concatenate([v, a])

        y0 = np.concatenate([x0, v0])

        t0, tf = t_span
        n_steps = int(np.floor((tf - t0) / dt))
        t_eval = t0 + dt * np.arange(n_steps + 1)

        sol = solve_ivp(ode, (t0, tf), y0, t_eval=t_eval, method="RK45")

        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")

        # התוצאות מ-solve_ivp
        Y = sol.y.T
        x = Y[:, :n].T
        v = Y[:, n:].T

        # -----------------------------
        # 🔍 הוספת בדיקת RESIDUAL כאן
        # -----------------------------
        a = np.zeros_like(x)
        residual_norms = []

        for i, tt in enumerate(sol.t):
            f = self.f_func(tt)
            rhs = f - C @ v[:, i] - K @ x[:, i]
            a[:, i] = np.linalg.solve(M, rhs)

            # בדיקת השארית:  M a + C v + K x - f
            r = M @ a[:, i] + C @ v[:, i] + K @ x[:, i] - f
            residual_norms.append(np.linalg.norm(r))

        print("➡️ max residual =", max(residual_norms))
        # -----------------------------

        return TimeHistoryResult(t=sol.t, x=x, v=v, a=a)

