# sim_core/structures.py
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .matrices import mass_matrix_lumped, stiffness_shear_structure


@dataclass
class StructureModel:
    """
    מודל כללי של מערכת דינמית ליניארית:
    M x¨ + C x˙ + K x = f(t)
    """
    M: np.ndarray
    K: np.ndarray
    C: np.ndarray | None = None

    dofs: int = field(init=False)

    def __post_init__(self):
        if self.M.shape != self.K.shape:
            raise ValueError("M and K must have the same shape")
        self.dofs = self.M.shape[0]
        if self.C is None:
            self.C = np.zeros_like(self.M)

    def as_dict(self) -> dict:
        return {
            "dofs": self.dofs,
            "M": self.M.tolist(),
            "K": self.K.tolist(),
            "C": self.C.tolist(),
        }


@dataclass
class ShearBuilding(StructureModel):
    """
    מבנה גזירה רב־קומתי (shear building).
    נבנה מתוך פרמטרים גיאומטריים וחומריים.
    """
    Hc: np.ndarray = field(repr=False, default=None)   # גובה עמודים
    Ec: np.ndarray = field(repr=False, default=None)   # מודול אלסטיות
    Ic: np.ndarray = field(repr=False, default=None)   # מומנט אינרציה
    Lb: np.ndarray = field(repr=False, default=None)   # מפתחים בכל קומה
    depth: float = 0.0
    floor_load: float = 0.0
    base_condition: int = 1  # 1=קבוע, 0=פשוט נתמך

    @classmethod
    def from_floor_data(cls,
                        Hc: np.ndarray,
                        Ec: np.ndarray,
                        Ic: np.ndarray,
                        Lb: np.ndarray,
                        depth: float,
                        floor_load: float,
                        base_condition: int = 1,
                        damping_ratio: float = 0.0) -> "ShearBuilding":
        dofs = Hc.shape[0]

        # --- 🛡️ בדיקת תקינות (Validation Fix) ---
        if Lb.shape[0] != dofs:
            # אם מספר השורות ב-Lb לא תואם למספר הקומות, נתקן או נזרוק שגיאה.
            # כאן נזרוק שגיאה ברורה כדי שתדע לתקן את ה-Frontend
            raise ValueError(f"Mismatch: Hc implies {dofs} floors, but Lb has data for {Lb.shape[0]} floors.")

        # בדיקה גם ל-Ec ו-Ic
        if Ec.shape[0] != dofs or Ic.shape[0] != dofs:
            raise ValueError("Mismatch: Ec or Ic dimensions do not match number of floors (Hc).")
        # ----------------------------------------

        # ---- MASS ----
        M = mass_matrix_lumped(dofs, Lb, depth, floor_load)

        # ---- STIFFNESS ----
        K = stiffness_shear_structure(dofs, Hc, Ec, Ic, base=base_condition)

        # ---- DAMPING (Rayleigh) ----
        C = np.zeros_like(M)
        if damping_ratio > 0.0:
            eigvals, _ = np.linalg.eig(np.linalg.solve(M, K))
            omega = np.sqrt(np.clip(np.real(eigvals), 0.0, None))
            omega.sort()

            w1 = omega[0]
            alpha0 = 0.0
            alpha1 = 0.0

            if dofs >= 2:
                w2 = omega[1]
                rel_diff = abs(w2 - w1) / max(w1, w2)
                if rel_diff > 1e-3:
                    A = np.array([[1.0 / w1, w1], [1.0 / w2, w2]])
                    b = np.array([2.0 * damping_ratio, 2.0 * damping_ratio])
                    alpha0, alpha1 = np.linalg.solve(A, b)
                else:
                    alpha0 = 2.0 * damping_ratio * w1
                    alpha1 = 0.0
            else:
                alpha0 = 2.0 * damping_ratio * w1
                alpha1 = 0.0

            C = alpha0 * M + alpha1 * K

        return cls(M=M, K=K, C=C,
                   Hc=Hc, Ec=Ec, Ic=Ic,
                   Lb=Lb, depth=depth,
                   floor_load=floor_load,
                   base_condition=base_condition)


@dataclass
class SingleDOF(StructureModel):
    """
    מערכת מסה–קפיץ–דמפר בודדת (SDOF) – מקרה פרטי.
    """
    m: float = 0.0
    k: float = 0.0
    c: float = 0.0

    @classmethod
    def from_parameters(cls, m: float, k: float, c: float = 0.0) -> "SingleDOF":
        M = np.array([[m]], dtype=float)
        K = np.array([[k]], dtype=float)
        C = np.array([[c]], dtype=float)
        return cls(M=M, K=K, C=C, m=m, k=k, c=c)
