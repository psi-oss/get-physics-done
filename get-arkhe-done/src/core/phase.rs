use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Phase {
    pub re: f64,
    pub im: f64,
}

impl Phase {
    pub fn new(re: f64, im: f64) -> Self {
        Self { re, im }
    }

    pub fn from_phi() -> Self {
        Self::new(1.618033988749895, 0.0)
    }

    pub fn magnitude(&self) -> f64 {
        (self.re.powi(2) + self.im.powi(2)).sqrt()
    }

    pub fn angle(&self) -> f64 {
        self.im.atan2(self.re)
    }
}
