# Dynami-Learn — Test Suite Analysis

> **Last verified:** 2026-07-25 (no git history in this checkout)

---

## Overview

The test suite lives in `tests/test_core.py` and contains **14 tests** covering `SingleDOF`, `ShearBuilding`, `ModalAnalyzer`, `mass_matrix_lumped`, `stiffness_shear_structure`, `TimeIntegrator` (RK45), the Newmark-Beta integrator (production engine), `from_floor_data` construction, and the El Centro earthquake record. The analysis below evaluates each test for correctness, identifies wrong assertions, missing coverage, and structural issues.

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

**Additional issue:** The test passes a scalar `floor_load=20.0`, but the function also accepts arrays. Only the scalar path is tested.

---

### `test_stiffness_shear_structure_tridiagonal` ✅ Correct

**Claims:** `stiffness_shear_structure()` produces the correct tridiagonal shear-building K.

**Verdict:** The expected matrix is built correctly in the test and matches the implementation. Diagonal entries, off-diagonal coupling terms, and the base condition coefficient (12.0 for clamped) are all verified. This test replaced the former `test_stiffness_shear_structure_diag_like_matlab` which incorrectly asserted a diagonal result (Bug 5).

**Gaps:**
- Only `base=1` (clamped) is tested. The `base=0` (pinned, coefficient 3.0) path is not covered.
- Only uniform E, I, and H values are used. Non-uniform geometry is not tested.
- No test covers the SDOF (dofs=1) case where no off-diagonal entries exist.

---

### `test_shear_building_modal_consistency` ⚠️ Passes but too weak

**Claims:** `ShearBuilding.from_floor_data()` produces a model whose modal frequencies are all positive and finite.

**Verdict:** The test passes and the assertion is technically correct. However, it only checks that the result is numerically sane — it does not verify that the frequencies are actually correct for the given inputs. The test would pass even if K or M had a subtle construction error, as long as the result was non-NaN.

**Important discrepancy found:** The test passes `floor_mass=20.0` (scalar). Inside `from_floor_data()`, this is placed directly into M as `np.diag([20.0, 20.0, 20.0])`. Stiffness values for Ec=30e9 Pa and Ic=0.2 m⁴ at H=3m give k_story ≈ 2×(12×30e9×0.2)/27 ≈ 533 MN/m per story. With M diagonal entries of 20 (kg?), ω_n would be astronomically large (~5 MHz). This suggests a unit mismatch: floor_mass should be in kg (e.g. 50,000 kg for 50 tons), not a raw scalar of 20. The test does not expose this because it only checks `> 0` and `isfinite`.

---

### `test_time_history_single_dof_damped_decays` ✅ Correct (improved)

**Claims:** A damped SDOF (ζ=0.125) started from x=0.1 with no external force has final mechanical energy less than 5% of the initial energy at t=10 s.

**Verdict:** Correct and robust. The energy-ratio check (`E_final < 0.05 * E_init`) is independent of phase, so it cannot pass accidentally when the last sample lands near a zero-crossing. This replaced the earlier fragile single-displacement check.

---

### `test_single_dof_energy_conservation_without_damping` ✅ Correct

**Claims:** Free vibration with c=0 conserves total mechanical energy E = 0.5*k*x² + 0.5*m*v² to within 1% over 10 seconds.

**Verdict:** Well-written. Uses a tight integration step (dt=0.005) and a meaningful tolerance. RK45 should maintain energy conservation well within 1% for 10 seconds on this problem.

**Minor note:** Tests `TimeIntegrator` (dead production code). The Newmark-Beta method energy drift is separately tested in `test_newmark_beta_energy_conservation`.

---

### `test_modal_mass_orthogonality_for_shear_building` ✅ Correct (strengthened)

**Claims:** Mode shapes satisfy both mass and stiffness orthogonality; all modal masses are strictly positive.

**Verdict:** The three assertions (positive modal masses, M-orthogonality, K-orthogonality) are mathematically guaranteed for any well-formed generalized eigenvalue problem. The test does not detect errors in K or M construction directly, but the additional positive-modal-mass check will catch degenerate or complex-eigenvalue failure modes that the solver cannot silently suppress.

---

### `test_damping_increase_reduces_response_amplitude` ✅ Correct and meaningful

**Claims:** Higher damping reduces the maximum displacement under resonant harmonic excitation.

**Verdict:** Good behavioral test. The external force sin(2t) is exactly at resonance (ωₙ = √(k/m) = 2 rad/s). At resonance, steady-state amplitude = F₀/(c·ωₙ): with c=0.1 → 5 m, with c=2.0 → 0.25 m. The assertion `amp_high_damp < amp_low_damp` is robust.

---

### `test_random_single_dof_models_are_stable_enough` ✅ Correct (strengthened)

**Claims:** Five random SDOF systems (m, k > 0, c ≥ 0) produce the correct natural frequency (within 0.1%) and finite integration results.

**Verdict:** The added frequency assertion `np.isclose(modal.frequencies[0], sqrt(k/m), rtol=1e-3)` makes this test genuinely useful — it now validates the `ModalAnalyzer` computation on diverse inputs rather than only checking for finiteness. The fixed seed ensures deterministic coverage.

---

### `test_newmark_beta_sdof_free_vibration` ✅ Correct

**Claims:** Starting from x=0, v=ωₙ (so initial acceleration is exactly zero), the Newmark-Beta integrator reproduces sin(2t): x≈1 at T/4, x≈0 at T, peak amplitude ≥ 0.99 over 3 periods.

**Verdict:** This is the key integration accuracy test for the production engine. The initial condition choice (x=0, v=ωₙ) eliminates the first-step Newmark-Beta error that arises when a=0 is assumed but the true initial acceleration is nonzero. The atol=0.005 tolerance is tight but achievable at dt=0.005.

---

### `test_newmark_beta_energy_conservation` ✅ Correct

**Claims:** Newmark-Beta with no damping and no external force conserves mechanical energy to within 1% over 30 seconds.

**Verdict:** Uses the same initial condition trick as above for a clean baseline. The constant-average-acceleration method (β=0.25, γ=0.5) is unconditionally stable and has very low artificial damping; 1% over 30 seconds is a reasonable tolerance. This test would catch runaway energy growth or excessive artificial dissipation.

---

### `test_from_floor_data_stiffness_values` ✅ Correct

**Claims:** `from_floor_data()` assembles K whose diagonal and off-diagonal entries match the manual 12EI/H³ formula for a 2-DOF building with uniform geometry.

**Verdict:** Well-constructed. The use of uniform geometry avoids Bug 14 (col-0-only height) while still verifying the assembly logic. The expected tridiagonal K is derived from first principles and compared with `np.allclose`. Symmetry and negative off-diagonal signs are both asserted explicitly.

---

### `test_from_floor_data_per_floor_mass_array` ✅ Correct

**Claims:** Passing a per-floor mass array produces M with matching diagonal entries and zero off-diagonal entries.

**Verdict:** Directly exercises the `isinstance(raw_mass, list)` branch in `StructureFactory.create_shear_building()` and the array path in `from_floor_data()`. Clean and targeted.

---

### `test_earthquake_record_interpolation` ✅ Correct

**Claims:** The El Centro record loads correctly, interpolates to zero at t=0 and post-record, matches the manual formula at the peak, and scales linearly with the scaling factor.

**Verdict:** Comprehensive. The four assertions together verify the record shape, the inertia force formula (`F = -M × ag × g × scale`), the post-record clamp to zero, and the linearity of the scaling factor. The `t_peak=2.14` choice is documented as approximately the strongest ground motion sample.

---

## Summary: Wrong / Broken Assertions

| Test | Issue |
|------|-------|
| `test_stiffness_shear_structure_diag_like_matlab` | **Deleted (was Bug 5)** — asserted a diagonal matrix when the correct result is tridiagonal. Replaced by `test_stiffness_shear_structure_tridiagonal`. |
| `test_shear_building_modal_consistency` | No assertion on actual frequency values; unit mismatch in `floor_mass` is not caught. |
| `test_modal_mass_orthogonality_for_shear_building` | M/K-orthogonality is guaranteed by the solver; test does not validate actual physics or catch Bug 14. |

---

## Missing Test Coverage

### Critical gaps (production code that is entirely untested)

| What is missing | Why it matters |
|-----------------|----------------|
| `ModalService` and `StructureFactory` in `services.py` | The service layer that the API calls is untested. |
| Rayleigh damping matrix computation | The C matrix assembled in `TimeSimulationService` from `α·M + β·K` is untested. |
| The `/shear-building/modal` REST endpoint | No integration test verifies the API route end-to-end. |

### Significant gaps (untested code paths in tested modules)

| What is missing | Why it matters |
|-----------------|----------------|
| `stiffness_shear_structure` with `base=0` (pinned) | The coefficient changes from 12 to 3; the entire `coeff_simple` branch is dead in tests. |
| `from_floor_data` with non-uniform `Hc` (different column heights) | Bug 14 (only column 0 used) is undetectable with uniform inputs. |
| `ShearBuilding` SDOF (dofs=1) | The 1-story edge case skips the off-diagonal K assembly branch; never tested. |
| `mass_matrix_lumped` with a per-floor load array | Only scalar input is tested; the array path exists but is not exercised. |
| Pause/resume via `initial_conditions` | The WebSocket resume path (`x0`, `v0` initial conditions passed to simulation) is not tested. |
| Modal analysis of a 2-DOF system | Only 1-DOF and 3-DOF systems are tested; 2-DOF (the default in the UI) is skipped. |
| `ModalAnalyzer` with a near-singular or ill-conditioned system | `np.linalg.eig` returns complex eigenvalues for ill-conditioned input; the `np.real()` silencing is untested. |

---

## Redundancy and Structural Issues

1. **`TimeIntegrator` (RK45) is tested but is dead production code.** Four tests exercise `response.py`, which is never called by the application. Passing these tests gives a false sense of coverage for the actual simulation pipeline. The Newmark-Beta tests (`test_newmark_beta_*`) now cover the production engine.

2. **`mass_matrix_lumped` is tested but unused.** `from_floor_data()` builds M inline using a completely different formula (direct `np.diag(floor_mass)` vs. load/area/gravity). The test validates a diverging dead-code path.

3. **No parametrize usage.** Several tests repeat the same structure (e.g. `test_shear_building_modal_consistency` and `test_modal_mass_orthogonality_for_shear_building` both set up a 3-DOF `ShearBuilding`). Using `pytest.mark.parametrize` would remove duplication and test more configurations for the same effort.

4. **Hebrew comments in the test file** make the test output harder to parse in CI environments and are inconsistent with the English docstrings.

---

## Recommended Additions (Priority Order)

| Priority | New test to add | Status |
|----------|----------------|--------|
| High | `test_newmark_beta_sdof_free_vibration` — verify the Newmark-Beta integrator (not RK45) preserves correct frequency and decays correctly | ✅ Done |
| High | `test_newmark_beta_energy_conservation` — equivalent of the existing energy test but for the production integrator | ✅ Done |
| High | `test_from_floor_data_stiffness_values` — assert actual K diagonal/off-diagonal values match manual calculation (catches Bug 14) | ✅ Done |
| High | `test_from_floor_data_per_floor_mass_array` — pass a mass array and verify M entries individually | ✅ Done |
| High | `test_earthquake_record_interpolation` — verify El Centro data loads, interpolates correctly at known time points | ✅ Done |
| Medium | `test_stiffness_pinned_base` — `stiffness_shear_structure` with `base=0`, coefficient 3.0 | Pending |
| Medium | `test_modal_frequencies_known_2dof` — 2-DOF system with hand-computed eigenvalues | Pending |
| Medium | `test_rayleigh_damping_matrix` — verify C = αM + βK with computed α, β gives target ζ at the two reference frequencies | Pending |
| Low | `test_single_dof_shear_building_edge_case` — dofs=1 doesn't crash and gives same result as `SingleDOF` | Pending |
| Low | `test_mass_matrix_lumped_per_floor_array` — exercise the non-scalar path in `mass_matrix_lumped` | Pending |
