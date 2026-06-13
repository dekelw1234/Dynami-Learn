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
                        floor_mass: np.ndarray | float,
                        base_condition: int = 1) -> "ShearBuilding":

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
        K = stiffness_shear_structure(dofs, Hc, Ec, Ic, base=base_condition)

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
