pub struct AceMiroWorkflow {
    pub workflow_id: String,
}

impl AceMiroWorkflow {
    pub fn trigger_sync(&self) {
        println!("Triggering ACE -> MiroFish synchronisation...");
    }
}
