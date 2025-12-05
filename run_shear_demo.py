import numpy as np

from sim_core.structures import ShearBuilding
from sim_core.modal import ModalAnalyzer
from sim_core.response import TimeIntegrator


def main():
    # ===== פרמטרים של מבנה 3 קומות (דוגמה סינתטית) =====
    dofs = 3

    # גובה עמודים בכל קומה (m)
    Hc = np.array([
        [3.0, 3.0],   # קומה 1 – שני עמודים בגובה 3m
        [3.0, 3.0],   # קומה 2
        [3.0, 3.0],   # קומה 3
    ])

    # מודול אלסטיות (Pa) – נגיד בטון ~30GPa
    Ec = np.ones_like(Hc) * 30e9

    # מומנט אינרציה (m^4) – סתם ערך דוגמה
    Ic = np.ones_like(Hc) * 0.2

    # מפתחים (אורך קורה) לכל קומה (m)
    Lb = np.array([
        [5.0, 5.0],   # קומה 1 – שתי קורות 5m
        [5.0, 5.0],
        [5.0, 5.0],
    ])

    depth = 10.0       # עומק המבנה (m)
    floor_load = 20.0  # עומס רצפה אופייני (kN/m^2) – כמו בקוד MATLAB

    # ===== יצירת מודל ShearBuilding =====
    building = ShearBuilding.from_floor_data(
        Hc=Hc,
        Ec=Ec,
        Ic=Ic,
        Lb=Lb,
        depth=depth,
        floor_load=floor_load,
        base_condition=1,      # בסיס מקובע
        damping_ratio=0.0      # בינתיים בלי ריסון
    )

    print("DOFs:", building.dofs)
    print("M:\n", building.M)
    print("K:\n", building.K)

    # ===== ניתוח מודלי =====
    modal = ModalAnalyzer(building).run()
    print("\n--- Modal analysis (shear building) ---")
    print("w_n (rad/s):", modal.frequencies)
    print("T_n (s):    ", modal.periods)
    print("Modes (columns = mode):\n", modal.modes)

    # ===== סימולציה בזמן – כוח סינוסי על הקומה העליונה =====
    def f_func(t: float) -> np.ndarray:
        f = np.zeros(building.dofs)
        # כוח הרמוני על הקומה העליונה (קומה 3)
        f[-1] = 1e3 * np.sin(2.0 * t)  # 1000N, תדר 2 rad/s לדוגמה
        return f

    integrator = TimeIntegrator(building, f_func)

    x0 = np.zeros(building.dofs)
    v0 = np.zeros(building.dofs)
    t_span = (0.0, 10.0)
    dt = 0.01

    time_hist = integrator.run(x0, v0, t_span, dt)

    roof_disp = time_hist.x[-1, :]  # הזזה של הקומה העליונה

    print("\n--- Time history (shear building) ---")
    print("t shape:", time_hist.t.shape)
    print("x shape:", time_hist.x.shape)
    print("max roof |x|:", np.max(np.abs(roof_disp)))


if __name__ == "__main__":
    main()
