pub struct TzinorManager {
    pub next_id: u64,
}

impl TzinorManager {
    pub fn new() -> Self {
        Self { next_id: 1 }
    }

    pub fn establish_channel(&mut self, source: u64, dest: u64) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        println!("Tzinor channel {} established: source={}, dest={}", id, source, dest);
        id
    }
}
