# Dynami-Learn — Test Suite Analysis

---

## Overview

The test suite lives in `tests/test_core.py` and contains **8 tests** covering `SingleDOF`, `ShearBuilding`, `ModalAnalyzer`, `mass_matrix_lumped`, `stiffness_shear_structure`, and `TimeIntegrator` (RK45). The analysis below evaluates each test for correctness, identifies wrong assertions, missing coverage, and structural issues.

---

## Per-Test Analysis

---

### `test_single_dof_modal` ✅ Correct

**Claims:** m=1, k=4 → ω=2 rad/s, T=π s, mode shape = 1.0.

**Verdict:** Correct. `ModalAnalyzer` computes M⁻¹K, whose only eigenvalue is k/m=4, giving ω=√4=2. The c=0.1 argument is passed to the model constructor but `ModalAnalyzer` ignores C (correct physics — modal analysis yields undamped natural frequencies).

**Minor issue:** The assertion `modal.modes[0, 0] == 1.0` only coincidentally passes for a 1×1 system. `np.linalg.eig` normalises eigenvectors to unit Euclidean norm; for a 1×1 system that happens to be 1.0, but the test gives the impression it is asserting a known normalisation convention which does not exist here.

---

### `test_mass_matrix_lumped_matches_manual` ⚠️ Tests dead code

**Claims:** M(i,i) = Area(i) × floor_load / 9.807.

**Verdict:** The assertion is correct for the `mass_matrix_lumped()` function in `matrices.py`. However, this function is **no longer called anywhere in the application**. After the `floor_mass` refactor, `ShearBuilding.from_floor_data()` builds M inline as `np.diag(floor_mass)` (direct mass in kg/tons, no area/gravity conversion). The tested function and the production code compute M from completely different inputs and formulas, silently diverging.

**Additional issue:** The test passes a scalar `floor_load=20.0`, but the function now also accepts arrays (the per-floor support added during refactor). Only the scalar path is tested.

---

### `test_stiffness_shear_structure_tridiagonal` ✅ Correct (this is the fixed Bug 5)

**Claims:** `stiffness_shear_structure()` produces the correct tridiagonal shear-building K.

**Verdict:** The expected matrix is built correctly in the test and matches the implementation. Diagonal entries, off-diagonal coupling terms, and the base condition coefficient (12.0 for clamped) are all verified.

**Gaps:**
- Only `base=1` (clamped) is tested. The `base=0` (pinned, coefficient 3.0) path is not covered.
- Only uniform E, I, and H values are used. Non-uniform geometry is not tested.
- No test covers the SDOF (dofs=1) case where no off-diagonal entries exist.

---

### `test_shear_building_modal_consistency` ⚠️ Passes but too weak

**Claims:** `ShearBuilding.from_floor_data()` produces a model whose modal frequencies are all positive and finite.

**Verdict:** The test passes and the assertion is technically correct. However, it only checks that the result is numerically sane — it does not verify that the frequencies are actually correct for the given inputs. The test would pass even if K or M had a subtle construction error, as long as the result was non-NaN.

**Important discrepancy found:** The test passes `floor_mass=20.0` (scalar). Inside `from_floor_data()`, this is placed directly into M as `np.diag([20.0, 20.0, 20.0])`. Stiffness values for Ec=30e9 Pa and Ic=0.2 m⁴ at H=3m give k_story ≈ 2×(12×30e9×0.2)/27 ≈ 533 MN/m per story. With M diagonal entries of 20 (kg?), ω_n would be astronomically large (~5 MHz). This suggests a unit mismatch: floor_mass should be in kg (e.g. 50,000 kg for 50 tons), not a raw scalar of 20. The test does not expose this because it only checks `> 0` and `isfinite`.

**Hidden Bug 14 not caught:** `from_floor_data()` uses only `Hc[i, 0]` (column 0) for stiffness, silently ignoring column 1's height. The test uses uniform Hc, so this bug has no effect here and goes undetected.

---

### `test_time_history_single_dof_damped_decays` ⚠️ Logically weak assertion

**Claims:** A damped SDOF started from x=0.1 with no external force decays to |x| < 0.01 in 10 seconds.

**Verdict:** The physics is correct (ζ = c/(2mωₙ) = 0.5/(2×1×2) = 0.125; decay envelope e^{-ζωₙt} = e^{-0.25×10} ≈ 0.082; final amplitude ≈ 0.0082). The assertion `abs(x_final) < 0.01` will pass.

**Structural issue:** `x_final` is the displacement value at the last time step, not the envelope amplitude. If the oscillation is in-phase and the last sample happens near a zero-crossing, the test would pass even without any decay. Checking the maximum displacement in the last 20% of the time window would be a more robust assertion.

**Separate concern:** The test uses `TimeIntegrator` (RK45 from `response.py`), which is dead code in production. The Newmark-Beta integrator in `TimeSimulationService` is not tested at all.

---

### `test_single_dof_energy_conservation_without_damping` ✅ Correct

**Claims:** Free vibration with c=0 conserves total mechanical energy to within 1%.

**Verdict:** Well-written. Uses a tight integration step (dt=0.005) and a meaningful tolerance. RK45 should maintain energy conservation well within 1% for 10 seconds on this problem. E₀ = 0.5 × 4 × 0.01 = 0.02 J (non-zero, so the relative error denominator is safe).

**Minor note:** Tests `TimeIntegrator` (dead production code). The Newmark-Beta method (constant average acceleration, β=0.25, γ=0.5) is unconditionally stable but not energy-conserving in the same sense — its energy drift behaviour is untested.

---

### `test_modal_mass_orthogonality_for_shear_building` ⚠️ Passes for wrong reasons

**Claims:** Mode shapes are M-orthogonal (Φᵀ M Φ is nearly diagonal).

**Verdict:** The assertion is mathematically valid — for any generalized eigenvalue problem K Φ = λ M Φ, the eigenvectors are M-orthogonal by construction, so this should always pass regardless of specific input values. The test does not detect errors in K or M construction because M-orthogonality is a consequence of the solver, not the physics.

**Bug 14 not caught:** The test uses non-uniform `Hc` (columns have heights 3.0 and 4.0–6.0), but `from_floor_data()` only reads `Hc[i, 0]`. The second column's height is silently ignored. The test never verifies that the computed frequencies match the expected values for the given geometry.

**Missing:** No assertion on the diagonal of Φᵀ M Φ (modal masses) — e.g. they should all be strictly positive.

---

### `test_damping_increase_reduces_response_amplitude` ✅ Correct and meaningful

**Claims:** Higher damping reduces the maximum displacement under resonant harmonic excitation.

**Verdict:** Good behavioral test. The external force sin(2t) is exactly at resonance (ωₙ = √(k/m) = 2 rad/s). At resonance, steady-state amplitude = F₀/(c·ωₙ): with c=0.1 → 5 m, with c=2.0 → 0.25 m. The assertion `amp_high_damp < amp_low_damp` is robust.

**Minor note:** The helper function `run_with_c` is defined inline and not reusable. No assertion on the actual numerical values — adding a sanity bound (e.g. `amp_low_damp > 1.0`) would guard against degenerate results.

---

### `test_random_single_dof_models_are_stable_enough` ⚠️ Too weak to be useful

**Claims:** Five random SDOF systems (m, k > 0, c ≥ 0) produce finite, stable integration results.

**Verdict:** For any system with positive m and k, the RK45 integrator on a stable ODE will always produce finite results over 5 seconds. The assertion can never fail unless the integrator itself has a bug. The test has a fixed seed (good), but the 5-iteration loop provides minimal additional coverage over a single well-chosen case.

**Improvement opportunity:** These random cases could instead assert that the computed frequency matches √(k/m) within tolerance, or that decay actually occurs for each damped case. As written, the test would pass even if the time history contained pure noise that happened to be finite.

---

## Summary: Wrong / Broken Assertions

| Test | Issue |
|------|-------|
| `test_stiffness_shear_structure_diag_like_matlab` | **Deleted (was Bug 5)** — asserted a diagonal matrix when the correct result is tridiagonal. Now replaced by `test_stiffness_shear_structure_tridiagonal`. |
| `test_shear_building_modal_consistency` | No assertion on actual frequency values; unit mismatch in `floor_mass` is not caught. |
| `test_time_history_single_dof_damped_decays` | Checks final displacement value, not envelope amplitude — fragile to phase. |
| `test_modal_mass_orthogonality_for_shear_building` | M-orthogonality is guaranteed by the solver; test does not validate actual physics or catch Bug 14. |
| `test_random_single_dof_models_are_stable_enough` | Assertion is trivially true for any positive-definite system; adds no real coverage. |

---

## Missing Test Coverage

### Critical gaps (production code that is entirely untested)

| What is missing | Why it matters |
|-----------------|----------------|
| `TimeSimulationService.run()` (Newmark-Beta integrator in `services.py`) | This is the actual simulation engine used in production. It is completely untested. |
| `ModalService` and `StructureFactory` in `services.py` | The service layer that the API calls is untested. |
| `earthquakes.py` — El Centro record loading and interpolation | The earthquake force function is never verified. |
| Rayleigh damping matrix computation | The C matrix assembled in `TimeSimulationService` from `α·M + β·K` is untested. |
| The `/shear-building/modal` REST endpoint | No integration test verifies the API route end-to-end. |

### Significant gaps (untested code paths in tested modules)

| What is missing | Why it matters |
|-----------------|----------------|
| `stiffness_shear_structure` with `base=0` (pinned) | The coefficient changes from 12 to 3; the entire `coeff_simple` branch is dead in tests. |
| `from_floor_data` with a **per-floor mass array** | Only scalar `floor_mass` is tested; the `np.isscalar` branch that handles arrays is not exercised. |
| `from_floor_data` with non-uniform `Hc` (different column heights) | Bug 14 (only column 0 used) is undetectable with uniform inputs. |
| `ShearBuilding` SDOF (dofs=1) | The 1-story edge case skips the off-diagonal K assembly branch; never tested. |
| `mass_matrix_lumped` with a per-floor load array | Only scalar input is tested; the array path exists but is not exercised. |
| Pause/resume via `initial_conditions` | The WebSocket resume path (`x0`, `v0` initial conditions passed to simulation) is not tested. |
| Newmark-Beta energy / stability properties | The integrator used in production has no stability or accuracy test. |
| Modal analysis of a 2-DOF system | Only 1-DOF and 3-DOF systems are tested; 2-DOF (the default in the UI) is skipped. |
| `ModalAnalyzer` with a near-singular or ill-conditioned system | `np.linalg.eig` returns complex eigenvalues for ill-conditioned input; the `np.real()` silencing is untested. |

---

## Redundancy and Structural Issues

1. **`TimeIntegrator` (RK45) is tested but is dead production code.** Five of eight tests exercise `response.py`, which is never called by the application. Passing these tests gives a false sense of coverage for the actual simulation pipeline.

2. **`mass_matrix_lumped` is tested but unused.** `from_floor_data()` builds M inline using a completely different formula (direct `np.diag(floor_mass)` vs. load/area/gravity). The test validates a diverging dead-code path.

3. **`test_random_single_dof_models_are_stable_enough` is redundant.** Its assertions are a strict subset of what `test_time_history_single_dof_damped_decays` already implies for a deterministic case. It should either be removed or strengthened with quantitative physics checks.

4. **No parametrize usage.** Several tests repeat the same structure (e.g. `test_shear_building_modal_consistency` and `test_modal_mass_orthogonality_for_shear_building` both set up a 3-DOF `ShearBuilding`). Using `pytest.mark.parametrize` would remove duplication and test more configurations for the same effort.

5. **Hebrew comments in the test file** make the test output harder to parse in CI environments and are inconsistent with the English docstrings.

---

## Recommended Additions (Priority Order)

| Priority | New test to add |
|----------|----------------|
| High | `test_newmark_beta_sdof_free_vibration` — verify the Newmark-Beta integrator (not RK45) preserves correct frequency and decays correctly |
| High | `test_newmark_beta_energy_conservation` — equivalent of the existing energy test but for the production integrator |
| High | `test_from_floor_data_stiffness_values` — assert actual K diagonal/off-diagonal values match manual calculation (catches Bug 14) |
| High | `test_from_floor_data_per_floor_mass_array` — pass a mass array and verify M entries individually |
| High | `test_earthquake_record_interpolation` — verify El Centro data loads, interpolates correctly at known time points |
| Medium | `test_stiffness_pinned_base` — `stiffness_shear_structure` with `base=0`, coefficient 3.0 |
| Medium | `test_modal_frequencies_known_2dof` — 2-DOF system with hand-computed eigenvalues |
| Medium | `test_rayleigh_damping_matrix` — verify C = αM + βK with computed α, β gives target ζ at the two reference frequencies |
| Low | `test_single_dof_shear_building_edge_case` — dofs=1 doesn't crash and gives same result as `SingleDOF` |
| Low | `test_mass_matrix_lumped_per_floor_array` — exercise the non-scalar path in `mass_matrix_lumped` |
