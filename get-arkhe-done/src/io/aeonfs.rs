use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Debug, Serialize, Deserialize)]
pub struct AeonFile {
    pub path: String,
    pub timelines: HashMap<String, Vec<u8>>, // branch_name -> content
}

impl AeonFile {
    pub fn new(path: &str) -> Self {
        Self {
            path: path.to_string(),
            timelines: HashMap::new(),
        }
    }

    pub fn commit_to_timeline(&mut self, timeline: &str, content: Vec<u8>) {
        self.timelines.insert(timeline.to_string(), content);
    }

    pub fn resolve_state(&self, timeline: &str) -> Option<&Vec<u8>> {
        self.timelines.get(timeline)
    }

    pub fn save_to_disk(&self, root: &Path) -> std::io::Result<()> {
        let storage_path = root.join(".gtd/aeonfs").join(&self.path);
        fs::create_dir_all(storage_path.parent().unwrap())?;
        let encoded = serde_json::to_string(self).unwrap();
        fs::write(storage_path, encoded)
    }

    pub fn load_from_disk(root: &Path, rel_path: &str) -> std::io::Result<Self> {
        let storage_path = root.join(".gtd/aeonfs").join(rel_path);
        let content = fs::read_to_string(storage_path)?;
        Ok(serde_json::from_str(&content).unwrap())
    }
}
