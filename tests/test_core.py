import os
import sys
import numpy as np

# להוסיף את תיקיית הפרויקט (התקייה שמעל tests) ל-PYTHONPATH
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sim_core.structures import SingleDOF, ShearBuilding
from sim_core.matrices import mass_matrix_lumped, stiffness_shear_structure
from sim_core.modal import ModalAnalyzer
from sim_core.response import TimeIntegrator


def test_single_dof_modal():
    """
    בדיקה שמערכת מסה-קפיץ-דמפר פשוטה נותנת תדר ותקופה נכונים.
    m = 1, k = 4 ⇒ w = 2 rad/s, T = pi
    """
    model = SingleDOF.from_parameters(m=1.0, k=4.0, c=0.1)

    modal = ModalAnalyzer(model).run()

    assert modal.frequencies.shape == (1,)
    assert modal.periods.shape == (1,)
    assert modal.modes.shape == (1, 1)

    w = modal.frequencies[0]
    T = modal.periods[0]

    assert np.isclose(w, 2.0, rtol=1e-3)
    assert np.isclose(T, np.pi, rtol=1e-3)
    # mode shape ב-SDOF אמור להיות 1
    assert np.isclose(modal.modes[0, 0], 1.0, rtol=1e-6)


def test_mass_matrix_lumped_matches_manual():
    """
    בדיקה שמטריצת המסה הלוקלית תואמת את החישוב הידני:
    M(i,i) = Area(i) * floor_load / 9.807
    """
    dofs = 3
    Lb = np.array([
        [5.0, 5.0],
        [4.0, 6.0],
        [3.0, 7.0],
    ])
    depth = 10.0
    floor_load = 20.0

    M = mass_matrix_lumped(dofs, Lb, depth, floor_load)

    # חישוב ידני
    beam_length_per_story = np.sum(Lb, axis=1)
    area = depth * beam_length_per_story
    M_manual = np.zeros((dofs, dofs))
    for i in range(dofs):
        M_manual[i, i] = area[i] * floor_load / 9.807

    assert M.shape == (dofs, dofs)
    assert np.allclose(M, M_manual, rtol=1e-10)


def test_stiffness_shear_structure_diag_like_matlab():
    """
    לפי StiffMat_ShearStructure.m ב-MATLAB:
    בסוף K = diag(Kstory)
    כאן אנחנו מאשרים שהתוצאה היא מטריצה דיאגונלית
    והאלכסון שווה לסכום EI/H^3 לכל קומה.
    """
    dofs = 3
    Hc = np.array([
        [3.0, 3.0],
        [3.0, 3.0],
        [3.0, 3.0],
    ])
    Ec = np.ones_like(Hc) * 30e9
    Ic = np.ones_like(Hc) * 0.2

    K = stiffness_shear_structure(dofs, Hc, Ec, Ic, base=1)

    # חישוב ידני של Kstory
    coeff_clamped = 12.0
    Kcol = (coeff_clamped * Ec * Ic) / (Hc ** 3)
    Kstory_manual = np.sum(Kcol, axis=1)
    K_manual = np.diag(Kstory_manual)

    assert K.shape == (dofs, dofs)
    # כל האיברים הלא-דיאגונליים צריכים להיות קרובים ל-0
    off_diag = K.copy()
    np.fill_diagonal(off_diag, 0.0)
    assert np.allclose(off_diag, 0.0, atol=1e-8)

    assert np.allclose(K, K_manual, rtol=1e-10)


def test_shear_building_modal_consistency():
    """
    בדיקה שמודל ShearBuilding שבנוי מהפונקציה from_floor_data
    נותן תוצאות מודליות עקביות (לא NaN / infinity, כל התדרים חיוביים).
    """
    dofs = 3
    Hc = np.array([
        [3.0, 3.0],
        [3.0, 3.0],
        [3.0, 3.0],
    ])
    Ec = np.ones_like(Hc) * 30e9
    Ic = np.ones_like(Hc) * 0.2
    Lb = np.array([
        [5.0, 5.0],
        [5.0, 5.0],
        [5.0, 5.0],
    ])
    depth = 10.0
    floor_load = 20.0

    building = ShearBuilding.from_floor_data(
        Hc=Hc,
        Ec=Ec,
        Ic=Ic,
        Lb=Lb,
        depth=depth,
        floor_load=floor_load,
        base_condition=1,
        damping_ratio=0.0,
    )

    modal = ModalAnalyzer(building).run()

    assert modal.frequencies.shape == (dofs,)
    assert modal.modes.shape == (dofs, dofs)

    # כל התדרים חיוביים וסופיים
    assert np.all(modal.frequencies > 0)
    assert np.all(np.isfinite(modal.frequencies))


def test_time_history_single_dof_damped_decays():
    """
    בדיקה שהמערכת המדוכאת SDOF לא 'מתפוצצת' בזמן,
    והאמפליטודה בסוף קטנה מאשר בהתחלה.
    """
    model = SingleDOF.from_parameters(m=1.0, k=4.0, c=0.5)

    def f_func(t: float) -> np.ndarray:
        # ללא כוחות חיצוניים
        return np.zeros(model.dofs)

    integrator = TimeIntegrator(model, f_func)

    x0 = np.array([0.1])
    v0 = np.array([0.0])
    t_span = (0.0, 10.0)
    dt = 0.01

    result = integrator.run(x0, v0, t_span, dt)

    x_initial = result.x[0, 0]
    x_final = result.x[0, -1]

    assert np.isclose(x_initial, 0.1, rtol=1e-5)
    # בסוף ההרצה המשרעת צריכה להיות הרבה יותר קטנה
    assert abs(x_final) < 0.01


def test_single_dof_energy_conservation_without_damping():
    """
    עבור מערכת בלי דמפינג וללא כוחות חיצוניים,
    האנרגיה המכנית אמורה להישמר לאורך זמן (בערך, עד שגיאות נומריות קטנות).
    """
    m = 1.0
    k = 4.0
    c = 0.0
    model = SingleDOF.from_parameters(m=m, k=k, c=c)

    def f_func(t: float) -> np.ndarray:
        return np.zeros(model.dofs)

    integrator = TimeIntegrator(model, f_func)

    x0 = np.array([0.1])
    v0 = np.array([0.0])
    t_span = (0.0, 10.0)
    dt = 0.005

    result = integrator.run(x0, v0, t_span, dt)

    x = result.x[0, :]
    v = result.v[0, :]

    E = 0.5 * k * x**2 + 0.5 * m * v**2

    # נבדוק שהשונות יחסית קטנה (אין "בריחה" של אנרגיה)
    E0 = E[0]
    max_dev = np.max(np.abs(E - E0)) / E0

    assert max_dev < 1e-2  # 1% סטייה לכל היותר


def test_modal_mass_orthogonality_for_shear_building():
    """
    בדיקת אורתוגונליות מודלית:
    PHI^T M PHI אמור להיות (בקירוב) מטריצה דיאגונלית.
    """
    dofs = 3
    Hc = np.array([
        [3.0, 4.0],
        [3.0, 5.0],
        [3.0, 6.0],
    ])
    Ec = np.ones_like(Hc) * 30e9
    Ic = np.ones_like(Hc) * 0.25
    Lb = np.array([
        [5.0, 4.0],
        [5.0, 4.0],
        [5.0, 4.0],
    ])
    depth = 8.0
    floor_load = 15.0

    building = ShearBuilding.from_floor_data(
        Hc=Hc,
        Ec=Ec,
        Ic=Ic,
        Lb=Lb,
        depth=depth,
        floor_load=floor_load,
        base_condition=1,
        damping_ratio=0.0,
    )

    modal = ModalAnalyzer(building).run()
    PHI = modal.modes
    M = building.M

    M_modal = PHI.T @ M @ PHI  # אמור להיות "כמעט דיאגונלי"

    # בודקים שהאיברים מחוץ לאלכסון קטנים ביחס לאלכסון
    diag = np.diag(M_modal)
    off_diag = M_modal.copy()
    np.fill_diagonal(off_diag, 0.0)

    max_off = np.max(np.abs(off_diag))
    mean_diag = np.mean(np.abs(diag))

    assert mean_diag > 0
    assert max_off / mean_diag < 1e-2  # לכל היותר 1% מהסקלת האלכסון


def test_damping_increase_reduces_response_amplitude():
    """
    מוודא שככל שמגדילים דמפינג במערכת SDOF עם אותו עירור,
    האמפליטודה המקסימלית קטנה.
    """
    m = 1.0
    k = 4.0

    def run_with_c(c_value: float) -> float:
        model = SingleDOF.from_parameters(m=m, k=k, c=c_value)

        def f_func(t: float) -> np.ndarray:
            # כוח חיצוני סינוסי קצר
            return np.array([1.0 * np.sin(2.0 * t)])

        integrator = TimeIntegrator(model, f_func)
        x0 = np.array([0.0])
        v0 = np.array([0.0])
        t_span = (0.0, 10.0)
        dt = 0.01
        result = integrator.run(x0, v0, t_span, dt)
        return float(np.max(np.abs(result.x[0, :])))

    amp_low_damp = run_with_c(0.1)
    amp_high_damp = run_with_c(2.0)

    assert amp_high_damp < amp_low_damp



def test_random_single_dof_models_are_stable_enough():
    """
    מייצר כמה מערכות אקראיות (m,k,c חיוביים) ובודק:
    - תדר חיובי
    - אינטגרציה לא מתפוצצת (x לא NaN / inf)
    """
    rng = np.random.default_rng(123)

    for _ in range(5):
        m = float(rng.uniform(0.5, 5.0))
        k = float(rng.uniform(1.0, 20.0))
        c = float(rng.uniform(0.0, 5.0))

        model = SingleDOF.from_parameters(m=m, k=k, c=c)
        modal = ModalAnalyzer(model).run()

        assert modal.frequencies[0] > 0
        assert np.isfinite(modal.frequencies[0])

        def f_func(t: float) -> np.ndarray:
            return np.zeros(model.dofs)

        integrator = TimeIntegrator(model, f_func)
        x0 = np.array([0.1])
        v0 = np.array([0.0])
        t_span = (0.0, 5.0)
        dt = 0.01
        result = integrator.run(x0, v0, t_span, dt)

        assert np.all(np.isfinite(result.x))
        assert np.all(np.isfinite(result.v))
        assert np.all(np.isfinite(result.a))
