import numpy as np
import sys
import os

# הוספת התיקייה הנוכחית ל-Path
sys.path.append(os.getcwd())

from sim_app.services import StructureFactory, ModalService, TimeSimulationService


def test_shear_building_services():
    print("\n==== ShearBuilding Services Test (Corrected Units) ====")

    payload_model = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # 30 GPa

        # תיקון פיזיקלי: הקטנו את Ic מ-0.2 ל-0.005 (עמוד 50 ס"מ בערך)
        "Ic": [[0.005, 0.005], [0.005, 0.005]],

        "Lb": [[5.0, 5.0], [5.0, 5.0]],
        "depth": 10.0,
        "floor_load": 20.0,  # kN/m^2
        "base_condition": 1,
        "damping_ratio": 0.0,
    }

    print("1. Creating Model...")
    model = StructureFactory.create_shear_building(payload_model)

    print("2. Running Modal Analysis...")
    modal_result = ModalService().run(model)
    freqs = modal_result["frequencies"]
    print(f"   -> Frequencies: {freqs}")

    # עכשיו התדרים אמורים להיות בטווח של 5Hz-20Hz (ולא 100Hz)
    if 0.1 < freqs[0] < 25.0:
        print("   ✅ Frequencies look realistic (0.1Hz - 25Hz range).")
    else:
        print(f"   ❌ Frequencies seem off! (Got {freqs[0]:.2f} Hz)")

    print("3. Running Time Simulation...")
    sim_payload = {
        "t0": 0.0, "tf": 5.0, "dt": 0.02,
        "x0": [0.0, 0.0], "v0": [0.0, 0.0],
        "force_function": {"freq": 2.0, "amp": 10.0}  # 10 kN
    }

    time_result = TimeSimulationService().run(model, sim_payload)

    # עכשיו המפתח max_displacement קיים בגלל התיקון ב-Service
    max_disp = time_result["max_displacement"]
    print(f"   -> Max Displacement: {max_disp:.5f} m")

    if max_disp > 0 and max_disp < 10.0:
        print("   ✅ Simulation run successfully.")
    else:
        print("   ❌ Simulation result suspicious.")


if __name__ == "__main__":
    test_shear_building_services()