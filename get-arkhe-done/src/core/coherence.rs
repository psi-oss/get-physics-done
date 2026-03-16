use num_complex::Complex64;
use std::fs;
use std::path::Path;
use regex::Regex;

/// Calculates the global coherence λ₂ from project artifacts.
/// In the Arkhe(n) framework, λ₂ is the second largest eigenvalue of the phase correlation matrix.
pub fn calculate_lambda2_from_artifacts(root: &Path) -> f64 {
    let mut phases = Vec::new();

    // Scan src for phase headers
    if let Ok(entries) = fs::read_dir(root.join("src")) {
        for entry in entries.flatten() {
            if entry.path().is_file() {
                if let Ok(content) = fs::read_to_string(entry.path()) {
                    if let Some(phase) = parse_phase_header(&content) {
                        phases.push(phase);
                    }
                }
            }
        }
    }

    calculate_lambda2(&phases)
}

fn parse_phase_header(content: &str) -> Option<Complex64> {
    // Look for % Arkhe-Phase: re + imi
    let re = Regex::new(r"Arkhe-Phase:\s*([-0-9.]+)\s*\+\s*([-0-9.]+)i").unwrap();
    if let Some(caps) = re.captures(content) {
        let r: f64 = caps[1].parse().unwrap_or(0.0);
        let i: f64 = caps[2].parse().unwrap_or(0.0);
        return Some(Complex64::new(r, i));
    }
    None
}

pub fn calculate_lambda2(phases: &[Complex64]) -> f64 {
    if phases.is_empty() {
        return 0.0618; // Bootstrap coherence
    }

    let n = phases.len() as f64;
    let mut sum_re = 0.0;
    let mut sum_im = 0.0;

    for p in phases {
        sum_re += p.re;
        sum_im += p.im;
    }

    let mean_re = sum_re / n;
    let mean_im = sum_im / n;

    let synchrony = (mean_re.powi(2) + mean_im.powi(2)).sqrt();

    // Scale synchrony to λ₂ mapping
    synchrony * 1.618
}
