import os
import sys
import numpy as np
import pytest

# להוסיף את תיקיית הפרויקט (התקייה שמעל tests) ל-PYTHONPATH
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sim_core.structures import SingleDOF, ShearBuilding
from sim_core.matrices import mass_matrix_lumped, stiffness_shear_structure, caughey_damping
from sim_core.modal import ModalAnalyzer
from sim_core.response import TimeIntegrator
from sim_core.earthquakes import get_el_centro_record, get_earthquake_force


# ---------------------------------------------------------------------------
# Helper: Newmark-Beta integrator mirroring TimeSimulationService.run()
# ---------------------------------------------------------------------------

def _newmark_beta(model, x0, v0, tf, dt, f_func=None):
    """
    Newmark-Beta (gamma=0.5, beta=0.25, constant-average-acceleration) stepping.
    Mirrors TimeSimulationService.run() exactly: starts with a = zeros.
    Returns (t_arr, x_arr, v_arr); x_arr/v_arr have shape (dofs, n_steps+1).
    """
    gamma      = 0.5
    beta_const = 0.25
    M, K, C = model.M, model.K, model.C

    a0 = 1.0 / (beta_const * dt ** 2)
    a1 = gamma / (beta_const * dt)
    a2 = 1.0 / (beta_const * dt)
    a3 = 1.0 / (2.0 * beta_const) - 1.0
    a4 = gamma / beta_const - 1.0
    a5 = (dt / 2.0) * (gamma / beta_const - 2.0)

    K_hat     = K + a0 * M + a1 * C
    K_hat_inv = np.linalg.inv(K_hat)

    n_steps = int(round(tf / dt))
    t_arr = np.arange(n_steps + 1) * dt
    x_arr = np.zeros((model.dofs, n_steps + 1))
    v_arr = np.zeros((model.dofs, n_steps + 1))

    u = x0.copy()
    v = v0.copy()
    a = np.zeros(model.dofs)   # mirrors service: a starts at zero

    x_arr[:, 0] = u
    v_arr[:, 0] = v

    for i in range(n_steps):
        t = (i + 1) * dt
        F = f_func(t) if f_func else np.zeros(model.dofs)

        term_M = a0 * u + a2 * v + a3 * a
        term_C = a1 * u + a4 * v + a5 * a
        P_hat  = F + M @ term_M + C @ term_C

        u_next = K_hat_inv @ P_hat
        a_next = a0 * (u_next - u) - a2 * v - a3 * a
        v_next = v + dt * ((1.0 - gamma) * a + gamma * a_next)

        x_arr[:, i + 1] = u_next
        v_arr[:, i + 1] = v_next
        u, v, a = u_next, v_next, a_next

    return t_arr, x_arr, v_arr


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


def test_stiffness_shear_structure_tridiagonal():
    """
    Verifies that stiffness_shear_structure() produces the correct tridiagonal
    shear-building stiffness matrix.

    For story stiffnesses k = [k1, k2, k3] the assembled K must be:
        K[i,i]   = k[i] + k[i+1]   (internal floors)
        K[i,i+1] = K[i+1,i] = -k[i+1]
        K[n-1,n-1] = k[n-1]         (top floor)
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

    # Per-story stiffness: sum of both columns
    coeff_clamped = 12.0
    Kcol = (coeff_clamped * Ec * Ic) / (Hc ** 3)
    ks = np.sum(Kcol, axis=1)   # [k1, k2, k3]

    # Build expected tridiagonal K manually
    K_expected = np.zeros((dofs, dofs))
    for i in range(dofs):
        K_expected[i, i] = ks[i]
        if i < dofs - 1:
            K_expected[i, i]     += ks[i + 1]
            K_expected[i, i + 1]  = -ks[i + 1]
            K_expected[i + 1, i]  = -ks[i + 1]

    assert K.shape == (dofs, dofs)
    assert np.allclose(K, K_expected, rtol=1e-10)


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
    floor_mass = 20.0

    building = ShearBuilding.from_floor_data(
        Hc=Hc,
        Ec=Ec,
        Ic=Ic,
        Lb=Lb,
        depth=depth,
        floor_mass=floor_mass,
        base_condition=1,
    )

    modal = ModalAnalyzer(building).run()

    assert modal.frequencies.shape == (dofs,)
    assert modal.modes.shape == (dofs, dofs)

    # כל התדרים חיוביים וסופיים
    assert np.all(modal.frequencies > 0)
    assert np.all(np.isfinite(modal.frequencies))


def test_time_history_single_dof_damped_decays():
    """
    Damped free-vibration SDOF (zeta=0.125): mechanical energy at t=10 s must be
    less than 5% of the initial energy, proving the envelope decayed — not merely
    that one sample happened to land near a zero-crossing.
    """
    m, k, c = 1.0, 4.0, 0.5
    model = SingleDOF.from_parameters(m=m, k=k, c=c)

    def f_func(t: float) -> np.ndarray:
        return np.zeros(model.dofs)

    integrator = TimeIntegrator(model, f_func)

    x0 = np.array([0.1])
    v0 = np.array([0.0])

    result = integrator.run(x0, v0, (0.0, 10.0), dt=0.01)

    assert np.isclose(result.x[0, 0], 0.1, rtol=1e-5)

    E_init  = 0.5 * k * result.x[0, 0]  ** 2 + 0.5 * m * result.v[0, 0]  ** 2
    E_final = 0.5 * k * result.x[0, -1] ** 2 + 0.5 * m * result.v[0, -1] ** 2
    assert E_final < 0.05 * E_init, (
        f"Final energy {E_final:.2e} is not < 5% of initial {E_init:.2e}; "
        "damped system did not decay as expected"
    )


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
    Modal orthogonality for a 3-DOF shear building:
      - PHI^T M PHI must be nearly diagonal (mass orthogonality)
      - all diagonal modal masses must be strictly positive
      - PHI^T K PHI must also be nearly diagonal (stiffness orthogonality)
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
    floor_mass = 15.0

    building = ShearBuilding.from_floor_data(
        Hc=Hc, Ec=Ec, Ic=Ic, Lb=Lb,
        depth=depth, floor_mass=floor_mass,
        base_condition=1,
    )

    modal = ModalAnalyzer(building).run()
    PHI = modal.modes
    M   = building.M
    K   = building.K

    M_modal = PHI.T @ M @ PHI
    K_modal = PHI.T @ K @ PHI

    diag_M   = np.diag(M_modal)
    off_M    = M_modal - np.diag(diag_M)
    diag_K   = np.diag(K_modal)
    off_K    = K_modal - np.diag(diag_K)

    # All modal masses must be positive (modes are real, M is positive-definite)
    assert np.all(diag_M > 0), f"Non-positive modal mass found: {diag_M}"

    # Off-diagonal terms must be < 1% of the mean diagonal (mass orthogonality)
    assert np.max(np.abs(off_M)) / np.mean(np.abs(diag_M)) < 1e-2

    # Stiffness orthogonality: PHI^T K PHI also diagonal
    assert np.max(np.abs(off_K)) / np.mean(np.abs(diag_K)) < 1e-2


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
    Five random SDOF systems (m, k > 0, c >= 0):
    - computed natural frequency must equal sqrt(k/m) within 0.1%
    - time-history integration must stay finite
    """
    rng = np.random.default_rng(123)

    for _ in range(5):
        m = float(rng.uniform(0.5, 5.0))
        k = float(rng.uniform(1.0, 20.0))
        c = float(rng.uniform(0.0, 5.0))

        model = SingleDOF.from_parameters(m=m, k=k, c=c)
        modal = ModalAnalyzer(model).run()

        w_expected = np.sqrt(k / m)
        assert np.isclose(modal.frequencies[0], w_expected, rtol=1e-3), (
            f"ModalAnalyzer gave ω={modal.frequencies[0]:.6f}, "
            f"expected sqrt(k/m)={w_expected:.6f} (m={m:.3f}, k={k:.3f})"
        )

        def f_func(t: float) -> np.ndarray:
            return np.zeros(model.dofs)

        integrator = TimeIntegrator(model, f_func)
        result = integrator.run(np.array([0.1]), np.array([0.0]), (0.0, 5.0), 0.01)

        assert np.all(np.isfinite(result.x))
        assert np.all(np.isfinite(result.v))
        assert np.all(np.isfinite(result.a))


# ---------------------------------------------------------------------------
# New tests: Newmark-Beta integrator (production engine)
# ---------------------------------------------------------------------------

def test_newmark_beta_sdof_free_vibration():
    """
    Newmark-Beta free vibration of SDOF (m=1, k=4, c=0):
    - displacement at T/4 must be the amplitude peak (~1.0)
    - displacement at T   must return to zero
    - peak amplitude stays ≈ 1.0 over 3 periods (no artificial dissipation)

    Start at x0=0, v0=w_n so initial acceleration is exactly zero,
    eliminating the first-step error caused by a=zeros initialisation.
    """
    m, k = 1.0, 4.0
    w_n  = np.sqrt(k / m)          # 2 rad/s
    T    = 2.0 * np.pi / w_n       # π s  ≈ 3.1416 s

    model = SingleDOF.from_parameters(m=m, k=k, c=0.0)
    x0    = np.array([0.0])
    v0    = np.array([w_n])         # exact solution: x(t) = sin(2t), amplitude = 1

    dt = 0.005
    tf = 3 * T

    t_arr, x_arr, _ = _newmark_beta(model, x0, v0, tf, dt)
    x = x_arr[0]

    idx_quarter = int(round((T / 4) / dt))
    idx_period  = int(round(T / dt))

    assert np.isclose(x[idx_quarter], 1.0, atol=0.005), (
        f"x at T/4 = {x[idx_quarter]:.5f}, expected ≈ 1.0"
    )
    assert np.isclose(x[idx_period], 0.0, atol=0.005), (
        f"x at T = {x[idx_period]:.5f}, expected ≈ 0.0"
    )
    assert np.max(np.abs(x)) > 0.99, "Amplitude dropped below 0.99 — unexpected dissipation"


def test_newmark_beta_energy_conservation():
    """
    Newmark-Beta with no damping and no external force must conserve
    mechanical energy E = 0.5*k*x² + 0.5*m*v² to within 1% over 30 seconds.

    Uses x0=0, v0=w_n so a_initial=0 is exact and there is no first-step error.
    """
    m, k = 1.0, 4.0
    w_n  = np.sqrt(k / m)

    model = SingleDOF.from_parameters(m=m, k=k, c=0.0)
    x0 = np.array([0.0])
    v0 = np.array([w_n])
    E0 = 0.5 * m * w_n ** 2          # = 0.5 * k * A² = 2.0 J

    t_arr, x_arr, v_arr = _newmark_beta(model, x0, v0, tf=30.0, dt=0.005)
    x = x_arr[0]
    v = v_arr[0]

    E       = 0.5 * k * x ** 2 + 0.5 * m * v ** 2
    max_dev = np.max(np.abs(E - E0)) / E0

    assert max_dev < 0.01, (
        f"Energy drift {max_dev:.4%} exceeds 1% — Newmark-Beta is dissipating or adding energy"
    )


# ---------------------------------------------------------------------------
# New tests: ShearBuilding.from_floor_data construction
# ---------------------------------------------------------------------------

def test_from_floor_data_stiffness_values():
    """
    from_floor_data assembles K whose values must match the manual 12EI/H³ formula.

    2-DOF building, identical column heights in both columns → Bug 14 (col-0-only)
    does not affect the result, so we can validate the assembly independently.

    Expected tridiagonal K for uniform story stiffness k_story:
        K = [[ 2*k,  -k ],
             [ -k,    k ]]
    """
    dofs = 2
    H, E, I = 3.0, 30e9, 0.2
    Hc = np.array([[H, H], [H, H]])
    Ec = np.array([[E, E], [E, E]])
    Ic = np.array([[I, I], [I, I]])
    Lb = np.array([[6.0, 6.0], [6.0, 6.0]])

    building = ShearBuilding.from_floor_data(
        Hc=Hc, Ec=Ec, Ic=Ic, Lb=Lb,
        depth=6.0, floor_mass=50_000.0, base_condition=1,
    )

    k_col   = 12.0 * E * I / H ** 3   # stiffness of one column
    k_story = 2 * k_col                # two columns per story

    K_expected = np.array([
        [2 * k_story, -k_story],
        [-k_story,     k_story],
    ])

    assert np.allclose(building.K, K_expected, rtol=1e-8), (
        f"K mismatch.\nGot:\n{building.K}\nExpected:\n{K_expected}"
    )
    assert building.K[0, 1] < 0, "Off-diagonal K[0,1] must be negative"
    assert building.K[1, 0] < 0, "Off-diagonal K[1,0] must be negative"
    assert np.allclose(building.K, building.K.T, atol=1e-10), "K must be symmetric"


def test_from_floor_data_per_floor_mass_array():
    """
    from_floor_data must accept a per-floor mass array and place each value
    on the corresponding diagonal entry of M, with all off-diagonal entries zero.
    """
    dofs   = 3
    masses = np.array([10_000.0, 20_000.0, 30_000.0])   # kg per floor

    building = ShearBuilding.from_floor_data(
        Hc=np.full((dofs, 2), 3.0),
        Ec=np.full((dofs, 2), 30e9),
        Ic=np.full((dofs, 2), 0.1),
        Lb=np.full((dofs, 2), 5.0),
        depth=6.0,
        floor_mass=masses,
        base_condition=1,
    )

    assert building.M.shape == (dofs, dofs)
    assert np.allclose(np.diag(building.M), masses), (
        f"M diagonal {np.diag(building.M)} does not match input masses {masses}"
    )
    off = building.M - np.diag(np.diag(building.M))
    assert np.all(off == 0.0), "M has non-zero off-diagonal entries"


# ---------------------------------------------------------------------------
# New tests: earthquake record
# ---------------------------------------------------------------------------

def test_earthquake_record_interpolation():
    """
    El Centro 1940 record and force-vector calculation:
    - Record arrays have the correct shape and start/end times
    - Force at t=0 is zero (ag=0 at record start)
    - Force at the peak time matches the manual formula F = -M * ag * g * scale
    - Force after the record ends is zero
    - Doubling the scaling factor doubles the force
    """
    t_pts, a_pts = get_el_centro_record()

    assert t_pts.shape == a_pts.shape
    assert t_pts[0] == pytest.approx(0.0)
    assert t_pts[-1] > 0.0

    M = np.array([[1_000.0]])   # 1000 kg, 1-DOF

    # t=0: record starts at 0 g → force must be zero
    F0 = get_earthquake_force(t=0.0, M=M, scaling_factor=1.0)
    assert np.isclose(F0[0], 0.0, atol=1e-6), f"Force at t=0 should be 0, got {F0[0]}"

    # t=2.14 s: record near its peak (~0.319 g)
    t_peak   = 2.14
    ag_peak  = float(np.interp(t_peak, t_pts, a_pts))   # g
    F_peak   = get_earthquake_force(t=t_peak, M=M, scaling_factor=1.0)
    F_manual = -M[0, 0] * ag_peak * 9.807
    assert np.isclose(F_peak[0], F_manual, rtol=1e-6), (
        f"Peak force mismatch: got {F_peak[0]:.4f}, expected {F_manual:.4f}"
    )

    # t > record duration: force must be zero
    F_late = get_earthquake_force(t=1_000.0, M=M, scaling_factor=1.0)
    assert np.isclose(F_late[0], 0.0, atol=1e-6), f"Force after record should be 0, got {F_late[0]}"

    # Scaling factor of 2 must double the force magnitude
    F_scale2 = get_earthquake_force(t=t_peak, M=M, scaling_factor=2.0)
    assert np.isclose(F_scale2[0], 2.0 * F_peak[0], rtol=1e-6), (
        f"scale=2 force {F_scale2[0]:.4f} ≠ 2 × scale=1 force {F_peak[0]:.4f}"
    )


# ---------------------------------------------------------------------------
# New tests: Caughey damping
# ---------------------------------------------------------------------------

def test_caughey_damping_exact_per_mode_zeta():
    """
    Caughey damping must recover the requested zeta in EVERY mode, not just the
    first two.  Rayleigh damping fails this: its parabola overshoots the target
    for any mode outside the two calibration frequencies.

    Verified property for each mode i:
        phi_i^T @ C @ phi_i / (2 * w_n[i] * modal_mass_i)  ==  zeta[i]

    Tests:
    1. Uniform zeta broadcast from a scalar  (all modes same target)
    2. Distinct per-mode zeta list           (exercises the per-mode logic)
    3. Short zeta list broadcast             (last value filled for extra modes)
    4. Symmetry of C
    """
    dofs = 3
    building = ShearBuilding.from_floor_data(
        Hc=np.full((dofs, 2), 3.0),
        Ec=np.full((dofs, 2), 30e9),
        Ic=np.full((dofs, 2), 0.2),
        Lb=np.full((dofs, 2), 5.0),
        depth=6.0,
        floor_mass=50_000.0,
        base_condition=1,
    )
    M, K = building.M, building.K
    modal = ModalAnalyzer(building).run()
    w_n = modal.frequencies
    PHI = np.real(modal.modes)

    def check_zeta(C, zeta_expected):
        for i in range(dofs):
            phi_i = PHI[:, i]
            m_i = float(phi_i @ M @ phi_i)
            zeta_i = (phi_i @ C @ phi_i) / (2.0 * w_n[i] * m_i)
            assert np.isclose(zeta_i, zeta_expected[i], rtol=1e-8), (
                f"Mode {i + 1}: got zeta={zeta_i:.10f}, expected {zeta_expected[i]}"
            )

    # 1. Uniform zeta via scalar broadcast
    zeta_scalar = 0.05
    C1 = caughey_damping(M, K, zeta_scalar)
    check_zeta(C1, [zeta_scalar] * dofs)
    assert np.allclose(C1, C1.T, atol=1e-10), "C must be symmetric"

    # 2. Distinct per-mode zeta — mode 3 has a different target than modes 1-2,
    #    the case that would fail with Rayleigh damping
    zeta_list = [0.02, 0.05, 0.10]
    C2 = caughey_damping(M, K, zeta_list)
    check_zeta(C2, zeta_list)
    assert np.allclose(C2, C2.T, atol=1e-10), "C must be symmetric"

    # 3. Short list broadcast (only 1 value supplied; modes 2 and 3 inherit it)
    zeta_short = [0.03]
    C3 = caughey_damping(M, K, zeta_short)
    check_zeta(C3, [0.03, 0.03, 0.03])


def test_caughey_damping_sdof_matches_classical():
    """
    For a SDOF system, Caughey C must equal the classical formula c = 2*zeta*w_n*m.
    This is the ground-truth limit case.
    """
    m, k, zeta = 5_000.0, 2e6, 0.07
    M = np.array([[m]])
    K = np.array([[k]])
    w_n = np.sqrt(k / m)

    C = caughey_damping(M, K, zeta)

    c_classical = 2.0 * zeta * w_n * m
    assert np.isclose(C[0, 0], c_classical, rtol=1e-10), (
        f"SDOF Caughey C={C[0,0]:.6f}, classical c={c_classical:.6f}"
    )


# ---------------------------------------------------------------------------
# Security / resource-limit tests
# ---------------------------------------------------------------------------

def _make_valid_model_req_dict(dofs=3):
    """Return a minimal valid ModelRequest dict for use in security tests."""
    return {
        "Hc":         [[3.0, 3.0]] * dofs,
        "Ec":         [[30.0, 30.0]] * dofs,
        "Ic":         [[0.002, 0.002]] * dofs,
        "Lb":         [[6.0, 6.0]] * dofs,
        "depth":      6.0,
        "floor_mass": 10.0,
        "base_condition": 1,
    }


def test_model_request_rejects_too_many_dofs():
    """ModelRequest must reject dofs > MAX_DOFS (prevents unbounded matrix allocation)."""
    from pydantic import ValidationError as PydanticValidationError
    from api.main import ModelRequest, MAX_DOFS

    d = _make_valid_model_req_dict(dofs=MAX_DOFS + 1)
    with pytest.raises(PydanticValidationError) as exc_info:
        ModelRequest.model_validate(d)

    errors = exc_info.value.errors()
    messages = " ".join(e["msg"] for e in errors)
    assert "MAX_DOFS" in messages or str(MAX_DOFS) in messages, (
        f"Expected MAX_DOFS in error message, got: {messages}"
    )


def test_model_request_rejects_mismatched_array_lengths():
    """ModelRequest must catch inconsistent story-array lengths (Ec shorter than Hc)."""
    from pydantic import ValidationError as PydanticValidationError
    from api.main import ModelRequest

    d = _make_valid_model_req_dict(dofs=3)
    d["Ec"] = [[30.0, 30.0], [30.0, 30.0]]   # 2 rows instead of 3

    with pytest.raises(PydanticValidationError) as exc_info:
        ModelRequest.model_validate(d)

    messages = " ".join(e["msg"] for e in exc_info.value.errors())
    assert "Ec" in messages


def test_model_request_rejects_nan_and_inf():
    """ModelRequest must reject NaN and Inf in physical arrays (prevents silent bad math)."""
    from pydantic import ValidationError as PydanticValidationError
    from api.main import ModelRequest
    import math

    for bad_value in [float("nan"), float("inf"), float("-inf")]:
        d = _make_valid_model_req_dict(dofs=2)
        d["Hc"][0][0] = bad_value
        with pytest.raises(PydanticValidationError):
            ModelRequest.model_validate(d)


def test_model_request_rejects_non_positive_physical_values():
    """Hc, Ec, Ic must be strictly positive; zero or negative must raise ValidationError."""
    from pydantic import ValidationError as PydanticValidationError
    from api.main import ModelRequest

    for field, idx in [("Hc", 0), ("Ec", 0), ("Ic", 0)]:
        d = _make_valid_model_req_dict(dofs=2)
        d[field][0][idx] = 0.0   # zero is invalid for these fields
        with pytest.raises(PydanticValidationError, match=r"must be > 0"):
            ModelRequest.model_validate(d)

        d[field][0][idx] = -1.0
        with pytest.raises(PydanticValidationError, match=r"must be > 0"):
            ModelRequest.model_validate(d)


def test_sim_request_rejects_out_of_bounds_fields():
    """SimRequest must enforce tf<=MAX_TF, dt>=MIN_DT, speed<=MAX_SPEED bounds."""
    from pydantic import ValidationError as PydanticValidationError
    from api.main import SimRequest, MAX_TF, MIN_DT, MAX_SPEED

    with pytest.raises(PydanticValidationError):
        SimRequest(tf=MAX_TF + 1.0)   # exceeds cap

    with pytest.raises(PydanticValidationError):
        SimRequest(dt=MIN_DT / 2.0)   # below floor

    with pytest.raises(PydanticValidationError):
        SimRequest(speed=MAX_SPEED + 1.0)   # exceeds cap


def test_simulation_max_steps_guard():
    """
    TimeSimulationService.run() must emit an ERROR frame and stop immediately
    when (tf / dt) > MAX_STEPS, without entering the Newmark loop.
    """
    import asyncio
    from sim_app.services import TimeSimulationService, MAX_STEPS
    from sim_app.services import StructureFactory

    d = _make_valid_model_req_dict(dofs=1)
    model = StructureFactory.create_shear_building(d)

    dt = 1e-4           # MIN_DT
    tf = (MAX_STEPS + 1) * dt   # one step over the limit

    payload = {"tf": tf, "dt": dt, "t0": 0.0, "speed": 1.0}

    async def collect():
        frames = []
        async for frame in TimeSimulationService().run(model, payload):
            frames.append(frame)
        return frames

    frames = asyncio.run(collect())

    error_frames = [f for f in frames if f.get("type") == "ERROR"]
    assert len(error_frames) >= 1, "Expected at least one ERROR frame when exceeding MAX_STEPS"

    # Must not contain any DATA frames — the loop must not have run
    data_frames = [f for f in frames if f.get("type") == "DATA"]
    assert len(data_frames) == 0, (
        f"Found {len(data_frames)} DATA frame(s); Newmark loop should not have started"
    )
