import numpy as np

import numpy as np


def mass_matrix_lumped(dofs: int,
                       Lb: np.ndarray,
                       depth: float,
                       floor_load: np.ndarray) -> np.ndarray:  # <-- שינוי: עכשיו מצפים למערך
    """
    יצירת מטריצת מסה.
    floor_load: וקטור באורך dofs (או סקלר שיומר) המייצג עומס לכל קומה.
    """
    # המרה למערך למקרה שהגיע סקלר
    if np.isscalar(floor_load):
        floor_load = np.full(dofs, floor_load)

    beam_length_per_story = np.sum(Lb, axis=1)
    area = depth * beam_length_per_story

    M = np.zeros((dofs, dofs), dtype=float)

    for i in range(dofs):
        # שימוש בערך הספציפי של הקומה i
        M[i, i] = area[i] * floor_load[i] / 9.807

    return M


def caughey_damping(M: np.ndarray, K: np.ndarray, zeta) -> np.ndarray:
    """
    Classical Caughey modal-superposition damping matrix (port of caugheydamping.m).

    Exact per-mode damping: for every mode i,
        phi_i^T @ C @ phi_i  ==  2 * zeta[i] * w_n[i] * (phi_i^T @ M @ phi_i)

    Unlike Rayleigh damping (which only hits the target at the two chosen frequencies),
    this guarantees the requested zeta in ALL modes.

    Parameters
    ----------
    M    : (n, n) mass matrix (diagonal, positive-definite)
    K    : (n, n) stiffness matrix (symmetric, positive-definite)
    zeta : scalar or sequence
        Target modal damping ratio per mode.  If fewer values are supplied than
        there are DOFs, the last value is broadcast to fill the remaining modes
        (matches MATLAB main.m: zeta = 0.02 * ones(1, DOFs)).

    Returns
    -------
    C : (n, n) symmetric damping matrix  C = M * C_modal * M
    """
    # Deferred imports break the circular chain: matrices <- structures <- modal <- matrices
    from .modal import ModalAnalyzer
    from .structures import StructureModel

    n = M.shape[0]

    modal = ModalAnalyzer(StructureModel(M=M, K=K)).run()
    w_n = modal.frequencies          # (n,) rad/s, ascending
    PHI = np.real(modal.modes)       # (n, n), columns = mode shapes

    # Broadcast zeta to exactly n values
    zeta_arr = np.atleast_1d(np.asarray(zeta, dtype=float)).ravel()
    if zeta_arr.size < n:
        zeta_arr = np.append(zeta_arr, np.full(n - zeta_arr.size, zeta_arr[-1]))
    zeta_arr = zeta_arr[:n]

    # C_modal = sum_i  (2 * zeta_i * w_i / m_i) * outer(phi_i, phi_i)
    C_modal = np.zeros((n, n))
    for i in range(n):
        phi_i = PHI[:, i]
        m_i = float(phi_i @ M @ phi_i)
        C_modal += (2.0 * zeta_arr[i] * w_n[i] / m_i) * np.outer(phi_i, phi_i)

    return M @ C_modal @ M


def stiffness_shear_structure(dofs: int,
                              Hc: np.ndarray,
                              Ec: np.ndarray,
                              Ic: np.ndarray,
                              base: int = 1) -> np.ndarray:
    """
    תרגום רעיוני של StiffMat_ShearStructure.m:
    1. מחשב קשיחות צידית שקולה לכל קומה (story stiffness)
    2. מרכיב מטריצת קשיחות גלובלית K של מבנה גזירה (shear building),
       בצורה תלת־אלכסונית כמו במטלאב.

    Kstory[i] = Σ (coeff * Ec * Ic / H^3) על כל העמודים בקומה i
    ואז:
        קומה 1:   K11 = k1 + k2,   K12 = -k2
        קומה i:   Kii = ki + k(i+1),  Ki,i-1 = -ki,  Ki,i+1 = -k(i+1)
        קומה עליונה: KNN = kN,      KN,N-1 = -kN
    """
    coeff_clamped = 12.0   # קבוע לעמוד מקובע–מקובע/חופשי
    coeff_simple = 3.0     # קבוע לעמוד פשוט–פשוט

    # קשיחות כל עמוד בכל קומה
    Kcol = np.zeros_like(Hc, dtype=float)

    for i in range(dofs):
        # בקומה הראשונה לוקחים בחשבון את תנאי הבסיס
        if i == 0:
            coeff = coeff_clamped if base == 1 else coeff_simple
        else:
            coeff = coeff_clamped

        # K = coeff * E * I / H^3 לכל עמוד בקומה
        Kcol[i, :] = (coeff * Ec[i, :] * Ic[i, :]) / (Hc[i, :] ** 3)

    # story stiffness שקולה לכל קומה (סכום על כל העמודים)
    Kstory = np.sum(Kcol, axis=1)   # וקטור באורך dofs

    # ===== הרכבת מטריצת הקשיחות הגלובלית K (תלת־אלכסונית) =====
    K = np.zeros((dofs, dofs), dtype=float)

    for i in range(dofs):
        if i == 0:
            # קומה ראשונה – קשיחות מעל הבסיס (k1) ועוד story שמעליה (k2)
            K[i, i] += Kstory[i]
            if dofs > 1:
                K[i, i] += Kstory[i + 1]
                K[i, i + 1] -= Kstory[i + 1]

        elif i == dofs - 1:
            # קומה עליונה – רק story האחרון
            K[i, i] += Kstory[i]
            K[i, i - 1] -= Kstory[i]

        else:
            # קומה פנימית – story מתחת (ki) ו-story מעל (k(i+1))
            K[i, i] += Kstory[i] + Kstory[i + 1]
            K[i, i - 1] -= Kstory[i]
            K[i, i + 1] -= Kstory[i + 1]

    return K
