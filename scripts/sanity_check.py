import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_app.services import StructureFactory, ModalService


def run_sanity_check():
    print("Running Sanity Check (Engineering Physics)...")

    # 40x40 cm column: I = bh^3/12
    b, h = 0.4, 0.4
    Ic_val = (b * h ** 3) / 12.0  # m^4 approx 0.00213

    payload = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],
        "Lb": [[6.0, 6.0], [6.0, 6.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # 30 GPa
        "Ic": [[Ic_val, Ic_val], [Ic_val, Ic_val]],
        "depth": 6.0,
        "floor_mass": 15.0,  # tons per floor
        "base_condition": 1,
    }

    model = StructureFactory.create_shear_building(payload)

    print(f"   Model created with {model.dofs} DOFs.")
    print(f"   Total Mass (approx): {np.sum(np.diag(model.M)) / 1000:.2f} tons")

    result = ModalService().run(model)

    T1 = result["periods"][0]
    w1 = result["frequencies"][0]

    print(f"   Fundamental Period (T1): {T1:.4f} seconds")
    print(f"   Fundamental Freq (f1):   {w1 / (2 * np.pi):.4f} Hz")

    # Rule of thumb: T ~ 0.1 * number of stories -> 0.1-0.5 s for 2 stories
    if 0.1 <= T1 <= 0.8:
        print("[OK] PASS: Result is physically realistic for a concrete building.")
    else:
        print("[FAIL] FAIL: Result implies unrealistic physics (check units!).")


if __name__ == "__main__":
    run_sanity_check()
