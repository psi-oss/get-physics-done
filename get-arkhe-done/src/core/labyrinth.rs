/// Labyrinth Transform using the Sacks spiral for retrocausal pathfinding.
pub fn labyrinth_transform(current_prime: u32, target_prime: u32) -> Vec<u32> {
    let mut path = Vec::new();
    path.push(current_prime);

    let mut current = current_prime;
    while current < target_prime {
        current = next_prime(current);
        if current <= target_prime {
            path.push(current);
        }
    }

    path
}

pub fn next_prime(n: u32) -> u32 {
    let mut p = n + 1;
    while !is_prime(p) {
        p += 1;
    }
    p
}

pub fn is_prime(n: u32) -> bool {
    if n <= 1 { return false; }
    if n <= 3 { return true; }
    if n % 2 == 0 || n % 3 == 0 { return false; }
    let mut i = 5;
    while i * i <= n {
        if n % i == 0 || n % (i + 2) == 0 { return false; }
        i += 6;
    }
    true
}
