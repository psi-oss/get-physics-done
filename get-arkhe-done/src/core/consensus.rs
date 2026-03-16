use serde::{Serialize, Deserialize};
use crate::core::phase::Phase;
use crate::runtime::pentagi::{AdversarialRedTeam, PentAGIResult};
use crate::core::coherence::calculate_lambda2_from_artifacts;
use std::path::Path;

#[derive(Debug, Serialize, Deserialize)]
pub struct CoherenceBlock {
    pub index: u64,
    pub timestamp: u64,
    pub author_phase: Phase,
    pub research_phase: f64, // λ₂
    pub security_score: f64,
    pub dixon_signature: String,
    pub previous_hash: String,
}

pub struct SecurityValidator {
    pub red_team: AdversarialRedTeam,
}

impl SecurityValidator {
    pub async fn validate_consensus(&self, foundation_id: &str, lambda2: f64) -> bool {
        let result = self.red_team.launch_coherence_attack(foundation_id).await;
        println!("PentAGI Security Score: {}", result.coherence_stress_score);
        // Consensus requires λ₂ ≥ φ (1.618) AND security score ≥ 0.8
        lambda2 >= 1.618 && result.coherence_stress_score >= 0.8
    }
}

pub struct TeknetChain {
    pub blocks: Vec<CoherenceBlock>,
    pub validator: SecurityValidator,
}

impl TeknetChain {
    pub fn new(validator: SecurityValidator) -> Self {
        Self {
            blocks: Vec::new(),
            validator,
        }
    }

    pub async fn validate_project_coherence(&self, root: &Path, foundation_id: &str) -> bool {
        let lambda2 = calculate_lambda2_from_artifacts(root);
        self.validator.validate_consensus(foundation_id, lambda2).await
    }

    pub async fn submit_phase(&mut self, foundation_id: &str, block: CoherenceBlock) -> bool {
        if self.validator.validate_consensus(foundation_id, block.research_phase).await {
            println!("Phase validated by ASI + PentAGI Security. Committing to TeknetChain.");
            self.blocks.push(block);
            true
        } else {
            println!("Phase rejected: failed coherence or security check.");
            false
        }
    }
}
