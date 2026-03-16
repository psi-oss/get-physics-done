use crate::core::phase::Phase;

#[derive(Debug)]
pub enum AgentRole {
    Theorist,
    Numericist,
    Librarian,
    Verifier,
    Researcher, // PentAGI Role
    Developer,  // PentAGI Role
    Executor,   // PentAGI Role
}

#[derive(Debug)]
pub struct KuramotoAgent {
    pub id: String,
    pub role: AgentRole,
    pub frequency: f64,
    pub phase: Phase,
}

impl KuramotoAgent {
    pub fn new(id: &str, role: AgentRole, frequency: f64) -> Self {
        Self {
            id: id.to_string(),
            role,
            frequency,
            phase: Phase::new(0.0, 0.0),
        }
    }

    pub fn synchronize(&mut self, global_phase: &Phase, coupling_k: f64) {
        let diff = global_phase.angle() - self.phase.angle();
        let new_angle = self.phase.angle() + self.frequency + coupling_k * diff.sin();
        self.phase = Phase::new(new_angle.cos(), new_angle.sin());
    }
}
