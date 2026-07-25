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
#hi


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
        # np.linalg.eig can return complex128-dtype eigenvectors even when
        # every imaginary part is zero (LAPACK backend-dependent for a
        # general, non-symmetric matrix like M^-1 K). Mode shapes of a real
        # M/K system are real-valued, so any imaginary component here is
        # numerical noise — discard it, or PHI.tolist() produces Python
        # complex numbers that json.dumps can't serialize.
        PHI = np.real(eigvecs[:, idx])
        T_n = 2.0 * np.pi / w_n

        return ModalResult(frequencies=w_n, periods=T_n, modes=PHI)


