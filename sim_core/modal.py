# sim_core/modal.py
from dataclasses import dataclass
import numpy as np

from .structures import StructureModel


@dataclass
class ModalResult:
    frequencies: np.ndarray     # w_n [rad/s]
    periods: np.ndarray         # T_n [s]
    modes: np.ndarray           # PHI (columns = modes)

    def as_dict(self) -> dict:
        return {
            "frequencies": self.frequencies.tolist(),
            "periods": self.periods.tolist(),
            "modes": self.modes.tolist(),
        }


class ModalAnalyzer:
    def __init__(self, model: StructureModel):
        self.model = model

    def run(self) -> ModalResult:
        M = self.model.M
        K = self.model.K

        # פתרון K φ = λ M φ
        M_inv_K = np.linalg.solve(M, K)
        eigvals, eigvecs = np.linalg.eig(M_inv_K)

        w_n = np.sqrt(np.real(eigvals))
        idx = np.argsort(w_n)
        w_n = w_n[idx]
        PHI = eigvecs[:, idx]
        T_n = 2.0 * np.pi / w_n

        return ModalResult(frequencies=w_n, periods=T_n, modes=PHI)
