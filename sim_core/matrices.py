import numpy as np


def mass_matrix_lumped(dofs: int,
                       Lb: np.ndarray,
                       depth: float,
                       floor_load: float) -> np.ndarray:
    """
    תרגום של MassMat.m:
    יצירת מטריצת מסה לוקלית לכל קומה על בסיס עומס רצפה.

    התוצאה ביחידות "מסה שקולה" כמו במטלאב:
    area * floor_load / g
    """
    beam_length_per_story = np.sum(Lb, axis=1)  # סכום המפתחים בכל קומה
    area = depth * beam_length_per_story        # שטח רצפה
    M = np.zeros((dofs, dofs), dtype=float)
    print("DEBUG mass_matrix_lumped:")
    print("  beam_length_per_story =", beam_length_per_story)
    print("  depth =", depth)
    print("  floor_load =", floor_load)
    print("  area =", area)
    for i in range(dofs):
        # floor_load בק״נ/מ^2, area במ״ר → kN
        # חילוק ב-g → "טון" כמו בקוד MATLAB
        M[i, i] = area[i] * floor_load / 9.807

    return M


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
