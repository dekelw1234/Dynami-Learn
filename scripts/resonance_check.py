import sys
import os
import asyncio
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_app.services import StructureFactory, ModalService, TimeSimulationService


async def _collect_displacements(model, sim_payload):
    all_x_frames = []
    async for frame in TimeSimulationService().run(model, sim_payload):
        if frame.get("type") == "DATA":
            all_x_frames.append(frame["all_x"])
    return np.array(all_x_frames).T  # shape: (dofs, n_steps)


def resonance_simulation():
    print("Starting Resonance Check (Physics Validation)...")

    payload = {
        "Hc": [[3.0, 3.0], [3.0, 3.0], [3.0, 3.0]],
        "Lb": [[6.0, 6.0], [6.0, 6.0], [6.0, 6.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0], [30.0, 30.0]],
        "Ic": [[0.00213, 0.00213], [0.00213, 0.00213], [0.00213, 0.00213]],
        "depth": 6.0,
        "floor_mass": 12.0,  # tons per floor
        "base_condition": 1,
        "damping_ratio": 0.02
    }

    print("   Building structure model...")
    model = StructureFactory.create_shear_building(payload)

    modal_res = ModalService().run(model)
    w1 = modal_res["frequencies"][0]
    f1 = w1 / (2 * np.pi)

    print(f"   Fundamental Frequency: w1 = {w1:.3f} rad/s ({f1:.3f} Hz)")

    sim_payload = {
        "t0": 0.0,
        "tf": 15.0,
        "dt": 0.01,
        "speed": 100.0,
        "force_function": {
            "type": "continuous",
            "amp": 5.0,
            "freq": w1,
            "duration": 15.0,
        }
    }

    displacements = asyncio.run(_collect_displacements(model, sim_payload))
    roof_disp = displacements[-1, :]

    start_window_idx = int(1.0 / 0.01)
    end_window_idx = int(14.0 / 0.01)

    first_peak = np.max(np.abs(roof_disp[:start_window_idx]))
    last_peak = np.max(np.abs(roof_disp[end_window_idx:]))

    print(f"   Initial Amplitude: {first_peak:.5f} m")
    print(f"   Final Amplitude:   {last_peak:.5f} m")

    ratio = last_peak / (first_peak + 1e-9)
    print(f"   Amplification Factor: {ratio:.2f}x")

    assert 0.5 < f1 < 5.0, f"Frequency {f1:.3f} Hz is out of realistic range (0.5-5.0 Hz)"
    assert ratio > 3.0, f"Resonance did not occur (Amplification {ratio:.2f} < 3.0)"
    print("[OK] All assertions passed.")


if __name__ == "__main__":
    resonance_simulation()
