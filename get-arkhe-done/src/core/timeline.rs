use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Timeline {
    pub branches: Vec<String>,
    pub active_branch: String,
}

impl Timeline {
    pub fn new(initial_branch: &str) -> Self {
        Self {
            branches: vec![initial_branch.to_string()],
            active_branch: initial_branch.to_string(),
        }
    }

    pub fn branch(&mut self, name: &str) {
        self.branches.push(name.to_string());
        self.active_branch = name.to_string();
    }
}
