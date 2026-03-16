use arkhe_core::core::labyrinth_gen::generate_global_sacks_lut;
use std::fs;

fn main() {
    fs::create_dir_all(".gpd").expect("Failed to create .gpd directory");
    match generate_global_sacks_lut(".gpd/SACKS.lut") {
        Ok(_) => println!("Successfully generated 65,536 primes in SACKS.lut"),
        Err(e) => eprintln!("Error generating SACKS.lut: {}", e),
    }
}
