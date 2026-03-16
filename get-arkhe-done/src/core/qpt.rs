use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize, Clone, Copy)]
pub enum PeirceCategory {
    Firstness,  // Quality, Possibility, Immediacy
    Secondness, // Reaction, Actuality, Brute Fact
    Thirdness,  // Mediation, Law, Structure
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy)]
pub enum McLuhanFace {
    Enhancement,
    Obsolescence,
    Retrieval,
    Reversal,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct QPTCell {
    pub category: PeirceCategory,
    pub face: McLuhanFace,
    pub identifier: String,
    pub character: String,
}

pub struct QPTMatrix {
    pub cells: Vec<QPTCell>,
}

impl QPTMatrix {
    pub fn new() -> Self {
        let mut cells = Vec::new();
        let categories = [PeirceCategory::Firstness, PeirceCategory::Secondness, PeirceCategory::Thirdness];
        let faces = [McLuhanFace::Enhancement, McLuhanFace::Obsolescence, McLuhanFace::Retrieval, McLuhanFace::Reversal];

        for &cat in &categories {
            for &face in &faces {
                let id = match (cat, face) {
                    (PeirceCategory::Firstness, McLuhanFace::Enhancement) => "1.ii",
                    (PeirceCategory::Secondness, McLuhanFace::Enhancement) => "2.ie",
                    (PeirceCategory::Thirdness, McLuhanFace::Retrieval) => "3.ci",
                    // ... and so on for all 12
                    _ => "X.X",
                };
                cells.push(QPTCell {
                    category: cat,
                    face,
                    identifier: id.to_string(),
                    character: "Phase-locked research node".to_string(),
                });
            }
        }

        Self { cells }
    }

    pub fn get_grounding_termini(&self) -> Vec<&QPTCell> {
        self.cells.iter().filter(|c| c.identifier == "1.ii" || c.identifier == "2.ie" || c.identifier == "2.ci").collect()
    }
}

pub enum CanonLoop {
    Operational,  // act, perceive, understand, adjust
    Coordination, // friction, negotiation, protocol
    Management,   // resource allocation
    Audit,        // verification
    Intelligence, // sensing, modeling
    Policy,       // identity, stability
    Knowledge,    // theory formation
    Grounding,    // foundational contact
    Legitimation, // shared meaning, norms
}

pub struct CollectiveIntelligence {
    pub active_loops: Vec<CanonLoop>,
    pub global_lambda2: f64,
}

impl CollectiveIntelligence {
    pub fn new() -> Self {
        Self {
            active_loops: Vec::new(),
            global_lambda2: 0.0618,
        }
    }

    pub fn entrain(&mut self, loop_type: CanonLoop) {
        println!("Collective Intelligence: Entraining loop...");
        self.active_loops.push(loop_type);
    }

    pub fn calculate_participation_mode(&self) -> &str {
        match self.active_loops.len() {
            0..=1 => "Operational Parallelism",
            2 => "Coordinative Coupling",
            3 => "Managerial Constraint",
            4 => "Intelligence Participation",
            _ => "Identificatory Participation",
        }
    }
}
