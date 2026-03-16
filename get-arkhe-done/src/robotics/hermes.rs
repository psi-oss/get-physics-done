use crate::core::phase::Phase;

pub struct KuramotoController {
    pub omega_natural: f64,
    pub k_coupling: f64,
    pub phase: Phase,
}

impl KuramotoController {
    pub fn new(omega: f64, k: f64) -> Self {
        Self {
            omega_natural: omega,
            k_coupling: k,
            phase: Phase::new(0.0, 0.0),
        }
    }

    pub fn update(&mut self, target_phase: &Phase, dt: f64) -> f64 {
        let diff = target_phase.angle() - self.phase.angle();
        let dtheta = self.omega_natural + self.k_coupling * diff.sin();
        let new_angle = self.phase.angle() + dtheta * dt;
        self.phase = Phase::new(new_angle.cos(), new_angle.sin());

        // Return control effort (coherence)
        (self.phase.angle() - target_phase.angle()).cos()
    }
}

pub struct Hermes7 {
    pub joints: Vec<KuramotoController>,
}

impl Hermes7 {
    pub fn new() -> Self {
        Self { joints: Vec::new() }
    }
}
