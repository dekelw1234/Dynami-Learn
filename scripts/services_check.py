import sys
import os
import asyncio
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_app.services import StructureFactory, ModalService, TimeSimulationService


async def _run_sim(model, sim_payload):
    frames = []
    async for frame in TimeSimulationService().run(model, sim_payload):
        if frame.get("type") == "DATA":
            frames.append(frame)
    return frames


def check_shear_building_services():
    print("\n==== ShearBuilding Services Check (Corrected Units) ====")

    payload_model = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # 30 GPa
        "Ic": [[0.005, 0.005], [0.005, 0.005]],
        "Lb": [[5.0, 5.0], [5.0, 5.0]],
        "depth": 10.0,
        "floor_mass": 20.0,  # tons per floor
        "base_condition": 1,
        "damping_ratio": 0.0,
    }

    print("1. Creating Model...")
    model = StructureFactory.create_shear_building(payload_model)

    print("2. Running Modal Analysis...")
    modal_result = ModalService().run(model)
    freqs = modal_result["frequencies"]
    f1_hz = freqs[0] / (2 * 3.14159265)
    print(f"   -> Frequencies (rad/s): {freqs}")
    print(f"   -> Fundamental freq:    {f1_hz:.2f} Hz")

    if 0.1 < f1_hz < 25.0:
        print("   [OK] Fundamental frequency is realistic (0.1-25 Hz range).")
    else:
        print(f"   [FAIL] Fundamental frequency seems off! (Got {f1_hz:.2f} Hz)")

    print("3. Running Time Simulation...")
    sim_payload = {
        "t0": 0.0, "tf": 5.0, "dt": 0.02,
        "speed": 100.0,
        "initial_conditions": {"x0": [0.0, 0.0], "v0": [0.0, 0.0]},
        "force_function": {"type": "pulse", "freq": 2.0, "amp": 10.0, "duration": 5.0},
    }

    frames = asyncio.run(_run_sim(model, sim_payload))
    max_disp = max(abs(f["x"]) for f in frames) if frames else 0.0
    print(f"   -> Max Displacement: {max_disp:.5f} m")

    if 0 < max_disp < 10.0:
        print("   [OK] Simulation ran successfully.")
    else:
        print("   [FAIL] Simulation result suspicious.")


if __name__ == "__main__":
    check_shear_building_services()
