use std::fs::File;
use std::io::{Write, BufWriter};
use crate::core::labyrinth::is_prime;

pub fn generate_global_sacks_lut(path: &str) -> std::io::Result<()> {
    println!("Generating Global SACKS.lut (65,536 primes)...");
    let file = File::create(path)?;
    let mut writer = BufWriter::new(file);

    let mut count = 0;
    let mut n = 2;
    while count < 65536 {
        if is_prime(n) {
            writeln!(writer, "{}", n)?;
            count += 1;
        }
        n += 1;
    }

    println!("Global SACKS.lut forged at {}.", path);
    Ok(())
}
