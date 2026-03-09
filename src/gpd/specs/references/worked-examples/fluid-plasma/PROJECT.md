# Kelvin-Helmholtz Instability in Compressible MHD

## Problem Statement

Study the Kelvin-Helmholtz (KH) instability at a shear interface in compressible magnetohydrodynamics. Determine how a magnetic field aligned with the shear flow stabilizes short-wavelength modes, map the stability boundary as a function of Alfvenic Mach number, and characterize the nonlinear saturation in 2D simulations.

## Physical Setup

- **Geometry:** 2D periodic box (x, y) with shear flow along x
- **Equilibrium:** v_x(y) = V_0 tanh(y/a), uniform density rho_0, uniform pressure p_0, uniform B = B_0 x-hat
- **Parameters:** Sonic Mach number M_s = V_0/c_s = 0.5 (subsonic), Alfvenic Mach number M_A = V_0/v_A varied from 0.5 to infinity

## Key Questions

1. What is the linear growth rate gamma(k) as a function of wavenumber and M_A?
2. At what M_A is the most unstable mode completely stabilized?
3. How does the nonlinear saturation amplitude depend on M_A?
4. What is the mixing layer width evolution delta(t) in the nonlinear regime?

## Success Criteria

- Linear growth rates match the analytic dispersion relation to within 1%
- Stabilization threshold matches Chandrasekhar (1961) prediction: M_A_crit = sqrt(2) for equal density
- Energy conservation maintained to < 10^{-6} relative error in ideal MHD
- Results compared with published 2D compressible MHD KH simulations

## Conventions

```
ASSERT_CONVENTION: units=SI, equation_of_state=adiabatic(gamma=5/3), mhd_model=ideal, normalization=alfven_units(L=a,V=v_A,rho=rho_0)
```

## Type

`fluid-plasma`

## Research Mode

`adaptive` — explore for stability analysis (Phases 1-4), exploit for simulation (Phases 5-7)
