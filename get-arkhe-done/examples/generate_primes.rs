use arkhe_core::core::labyrinth_gen::generate_global_sacks_lut;
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: generate_primes <path>");
        std::process::exit(1);
    }
    let path = &args[1];
    if let Err(e) = generate_global_sacks_lut(path) {
        eprintln!("Error generating primes: {}", e);
        std::process::exit(1);
    }
}
