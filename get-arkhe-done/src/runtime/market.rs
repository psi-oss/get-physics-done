use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct PredictionMarket {
    pub bids: Vec<PredictionBid>,
    pub outcome: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PredictionBid {
    pub agent_id: String,
    pub claim: String,
    pub stake: f64,
    pub phase_alignment: f64,
}

impl PredictionMarket {
    pub fn new() -> Self {
        Self { bids: Vec::new(), outcome: None }
    }

    pub fn place_bid(&mut self, agent_id: &str, claim: &str, stake: f64, alignment: f64) {
        self.bids.push(PredictionBid {
            agent_id: agent_id.to_string(),
            claim: claim.to_string(),
            stake,
            phase_alignment: alignment,
        });
    }

    pub fn resolve(&mut self) -> String {
        // Multi-agent consensus logic
        "Phase Coherence Confirmed".to_string()
    }
}
