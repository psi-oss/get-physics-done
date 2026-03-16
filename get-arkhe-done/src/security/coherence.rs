use crate::core::phase::Phase;

pub struct CoherenceSecurity {
    pub threshold: f64,
}

impl CoherenceSecurity {
    pub fn new(threshold: f64) -> Self {
        Self { threshold }
    }

    pub fn verify_integrity(&self, lambda2: f64) -> bool {
        lambda2 >= self.threshold
    }
}
