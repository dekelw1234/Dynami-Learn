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
                        floor_mass: np.ndarray | float,  # <-- שינוי שם: mass במקום load
                        base_condition: int = 1,
                        damping_ratio: float = 0.0) -> "ShearBuilding":

        dofs = Hc.shape[0]

        # בדיקות תקינות... (אותו דבר)
        if Hc.shape != (dofs, 2) or Ec.shape != (dofs, 2) or Ic.shape != (dofs, 2) or Lb.shape != (dofs, 2):
            raise ValueError("All input arrays must have shape (dofs, 2)")

        # ---- MASS (Direct Assignment) ----
        # המרה למערך אם הגיע סקלר
        if np.isscalar(floor_mass):
            floor_mass = np.full(dofs, floor_mass)

        # יצירת מטריצת מסה אלכסונית ישירות מהמסה שהתקבלה
        M = np.diag(floor_mass)

        # ---- STIFFNESS (K) ----
        # חישוב קשיחות נשאר ללא שינוי
        k_story = np.zeros(dofs)
        for i in range(dofs):
            h = Hc[i, 0]
            # חישוב קשיחות לכל עמוד
            k_cols = 0.0
            for col in range(2):
                E = Ec[i, col]
                I = Ic[i, col]
                if base_condition == 0:  # Pinned
                    k_c = (3 * E * I) / (h ** 3)
                elif base_condition == 1:  # Fixed
                    k_c = (12 * E * I) / (h ** 3)
                else:  # Roller
                    k_c = (12 * E * I) / (h ** 3)  # הנחה
                k_cols += k_c
            k_story[i] = k_cols

        K = np.zeros((dofs, dofs))
        for i in range(dofs):
            K[i, i] = k_story[i]
            if i < dofs - 1:
                K[i, i] += k_story[i + 1]
                K[i, i + 1] = -k_story[i + 1]
                K[i + 1, i] = -k_story[i + 1]

        # ---- DAMPING (C) ----
        # מטריצת C ראשונית (תעודכן בסימולציה לפי ריילי)
        C = np.zeros_like(K)

        return cls(M=M, K=K, C=C,
                   Hc=Hc, Ec=Ec, Ic=Ic,
                   Lb=Lb, depth=depth,
                   floor_load=0.0,  # לא רלוונטי יותר לאחסון
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
