# run_dev.py

import numpy as np
from sim_core.structures import ShearBuilding


def build_debug_shear_building():
    """
    בונה את אותו מבנה כמו במיין של MATLAB:
    Nstr = 5, Ncol = 5, Hc = 3.5m, Lb = 6m, Ec = 26.2e6, Ic לפי 300x400mm,
    Depth = 6m, Fser = 10 kN/m^2, base = 1, damping_ratio = 0.02
    """
    Nstr = 5
    Ncol = 5

    # Story heights (Hc) – בדיוק כמו ב-MATLAB
    Hc = np.full((Nstr, Ncol), 3.5, dtype=float)

    # Beam spans (Lb): 6m בין עמודים, ועמודה אחרונה בכל שורה היא 0 (כמו במאטלאב)
    Lb = np.zeros((Nstr, Ncol), dtype=float)
    Lb[:, :-1] = 6.0

    # Column section properties (בדיוק כמו במאטלאב)
    tcc = 300.0 * np.ones((Nstr, Ncol))      # mm
    bcc = 400.0 * np.ones((Nstr, Ncol))      # mm
    Ic = (tcc * (bcc ** 3) / 12.0) * 1e-12   # m^4 (אותו נוסחה כמו במאטלאב)

    # Modulus of elasticity – אותו מספר כמו במאטלאב
    Ec = 26.2e6 * np.ones((Nstr, Ncol), dtype=float)  # kN/m^2 או מה שהקלאס מצפה

    depth = 6.0        # m
    floor_load = 10.0  # kN/m^2
    base_condition = 1
    damping_ratio = 0.02

    model = ShearBuilding.from_floor_data(
        Hc=Hc,
        Ec=Ec,
        Ic=Ic,
        Lb=Lb,
        depth=depth,
        floor_load=floor_load,
        base_condition=base_condition,
        damping_ratio=damping_ratio,
    )

    return model


def main():
    model = build_debug_shear_building()

    np.set_printoptions(precision=4, suppress=True)

    print("=== PYTHON: ShearBuilding matrices (current implementation) ===")

    print("\nMass matrix M (should correspond to 146.8339 ton per floor in MATLAB):")
    print(model.M)

    print("\nStiffness matrix K:")
    print(model.K)

    print("\nDamping matrix C:")
    print(model.C)

    # נחשב גם תדרים טבעיים כדי לוודא שאנחנו בערך באותו עולם כמו MATLAB
    from sim_core.modal import ModalAnalyzer
    modal = ModalAnalyzer(model).run()
    print("\nNatural frequencies (Hz):")
    print(modal.frequencies)


if __name__ == "__main__":
    main()
