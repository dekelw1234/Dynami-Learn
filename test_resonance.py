import numpy as np
import sys
import os

# הוספת הנתיב כדי שהייבוא יעבוד גם בטסטים
sys.path.append(os.getcwd())

from sim_app.services import StructureFactory, ModalService, TimeSimulationService


# השינוי כאן: השם חייב להתחיל ב-test_
def test_resonance_simulation():
    print("\n📢 Starting Resonance Test (Physics Validation)...")

    # 1. יצירת מבנה בטון 3 קומות
    payload = {
        "Hc": [[3.0], [3.0], [3.0]],
        "Lb": [[6.0], [6.0], [6.0]],
        "Ec": [[30.0], [30.0], [30.0]],
        "Ic": [[0.00213], [0.00213], [0.00213]],
        "depth": 6.0,
        "floor_load": 12.0,
        "base_condition": 1,
        "damping_ratio": 0.02
    }

    print("   🏗️  Building structure model...")
    model = StructureFactory.create_shear_building(payload)

    # 2. חישוב תדר טבעי
    modal_res = ModalService().run(model)
    w1 = modal_res["frequencies"][0]
    f1 = w1 / (2 * np.pi)

    print(f"   🔎 Calculated Fundamental Frequency: w1 = {w1:.3f} rad/s ({f1:.3f} Hz)")

    # 3. הפעלת כוח בתדר התהודה
    sim_payload = {
        "t0": 0.0,
        "tf": 15.0,
        "dt": 0.01,
        "force_function": {
            "amp": 5.0,
            "freq": w1
        }
    }

    time_res = TimeSimulationService().run(model, sim_payload)

    # 4. בדיקת התוצאות
    displacements = np.array(time_res["x"])
    roof_disp = displacements[-1, :]

    start_window_idx = int(1.0 / 0.01)
    end_window_idx = int(14.0 / 0.01)

    first_peak = np.max(np.abs(roof_disp[:start_window_idx]))
    last_peak = np.max(np.abs(roof_disp[end_window_idx:]))

    print(f"   📉 Initial Amplitude: {first_peak:.5f} m")
    print(f"   📈 Final Amplitude:   {last_peak:.5f} m")

    ratio = last_peak / (first_peak + 1e-9)
    print(f"   🚀 Amplification Factor: {ratio:.2f}x")

    # Assertions כדי ש-Pytest ידע אם עבר או נכשל
    assert 0.5 < f1 < 5.0, "Frequency is out of realistic range"
    assert ratio > 3.0, "Resonance did not occur (Amplification < 3.0)"


if __name__ == "__main__":
    test_resonance_simulation()