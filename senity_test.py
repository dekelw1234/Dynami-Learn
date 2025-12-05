# test_sanity_check.py
import numpy as np
from sim_app.services import StructureFactory, ModalService


def run_sanity_check():
    print("🏥 Running Sanity Check (Engineering Physics)...")

    # ==========================================
    # 1. הגדרת בניין בטון ריאליסטי (2 קומות)
    # ==========================================
    # מידות עמוד: 40x40 ס"מ
    b, h = 0.4, 0.4
    Ic_val = (b * h ** 3) / 12.0  # m^4 (0.00213)

    # נתונים מהפרונטאנד (יחידות הנדסיות)
    payload = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],  # גובה קומה 3 מטר
        "Lb": [[6.0, 6.0], [6.0, 6.0]],  # מפתחים 6 מטר

        # שים לב! אנחנו שולחים GPa, לא Pa
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # בטון B30 ~ 30 GPa

        "Ic": [[Ic_val, Ic_val], [Ic_val, Ic_val]],

        "depth": 6.0,  # מטר
        "floor_load": 15.0,  # kN/m^2 (עומס כבד יחסית: משקל עצמי + שימושי)
        "base_condition": 1  # רתום
    }

    # ==========================================
    # 2. בניית המודל דרך ה-Factory
    # ==========================================
    # ה-Factory ימיר:
    # Load: 15 kN -> ~1500 kg/m^2
    # E: 30 GPa -> 30e9 Pa
    model = StructureFactory.create_shear_building(payload)

    print(f"   🏗️  Model created with {model.dofs} DOFs.")
    print(f"   ⚖️  Total Mass (approx): {np.sum(np.diag(model.M)) / 1000:.2f} tons")
    # צפי: שטח קומה 12x6 = 72מ"ר. עומס 1.5 טון/מ"ר. סה"כ מסה ~100 טון לקומה.

    # ==========================================
    # 3. בדיקת תדרים (Modal Analysis)
    # ==========================================
    modal_service = ModalService()
    result = modal_service.run(model)

    T1 = result["periods"][0]  # זמן מחזור מוד ראשון
    w1 = result["frequencies"][0]

    print(f"   ⏱️  Fundamental Period (T1): {T1:.4f} seconds")
    print(f"   📈  Fundamental Freq (f1):   {w1 / (2 * np.pi):.4f} Hz")

    # ==========================================
    # 4. קריטריון הצלחה (Assertion)
    # ==========================================
    # כלל אצבע לבניינים: T ~ 0.1 * מספר הקומות
    # עבור 2 קומות, נצפה ל-T בין 0.1 ל-0.5 שניות.
    # אם קיבלנו 0.0001 שניות -> הקשיחות גדולה מדי (טעות יחידות E)
    # אם קיבלנו 10 שניות -> המבנה רך מדי (טעות יחידות M או K)

    if 0.1 <= T1 <= 0.8:
        print("✅ PASS: Result is physically realistic for a concrete building.")
    else:
        print("❌ FAIL: Result implies unrealistic physics (check units!).")


if __name__ == "__main__":
    run_sanity_check()