#!/usr/bin/env node
/**
 * GPD installer — sets up Get Physics Done in your coding agent.
 *
 * Usage:
 *   npx github:physicalsuperintelligence/get-physics-done
 *   npx github:physicalsuperintelligence/get-physics-done --claude --global
 *   npx github:physicalsuperintelligence/get-physics-done --opencode --global
 */

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

const RUNTIMES = {
  "claude-code": { name: "Claude Code" },
  "opencode": { name: "OpenCode" },
  "gemini": { name: "Gemini CLI" },
  "codex": { name: "Codex" },
};

function log(msg) {
  console.log(`\x1b[36m[GPD]\x1b[0m ${msg}`);
}

function error(msg) {
  console.error(`\x1b[31m[GPD]\x1b[0m ${msg}`);
}

function checkPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" }).trim();
      const match = version.match(/(\d+)\.(\d+)/);
      if (match && parseInt(match[1]) >= 3 && parseInt(match[2]) >= 11) {
        return cmd;
      }
    } catch {}
  }
  return null;
}

function checkUv() {
  try {
    execSync("uv --version 2>&1", { encoding: "utf-8" });
    return true;
  } catch {
    return false;
  }
}

async function prompt(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

async function main() {
  const args = process.argv.slice(2);

  console.log("");
  console.log("  \x1b[1m\x1b[36mGet Physics Done (GPD)\x1b[0m");
  console.log("  Autonomous physics research system");
  console.log("");

  // Check Python
  const python = checkPython();
  if (!python) {
    error("Python 3.11+ is required but not found.");
    error("Install from https://python.org or via your package manager.");
    process.exit(1);
  }
  log(`Found ${execSync(`${python} --version`, { encoding: "utf-8" }).trim()}`);

  // Check/install uv
  const hasUv = checkUv();
  if (!hasUv) {
    log("Installing uv (Python package manager)...");
    try {
      execSync("curl -LsSf https://astral.sh/uv/install.sh | sh", { stdio: "inherit" });
    } catch {
      error("Failed to install uv. Install manually: https://docs.astral.sh/uv/");
      process.exit(1);
    }
  }

  // Install the Python package
  log("Installing get-physics-done...");
  try {
    spawnSync("uv", ["pip", "install", "get-physics-done@git+https://github.com/physicalsuperintelligence/get-physics-done.git"], {
      stdio: "inherit",
    });
  } catch {
    // Fallback to pip
    spawnSync(python, ["-m", "pip", "install", "git+https://github.com/physicalsuperintelligence/get-physics-done.git"], {
      stdio: "inherit",
    });
  }

  // Determine runtime
  // Determine runtime from flags or interactive prompt
  const runtimeKeys = Object.keys(RUNTIMES);
  let runtime = null;
  for (const key of runtimeKeys) {
    if (args.includes(`--${key}`)) {
      runtime = key;
      break;
    }
  }
  // Also accept short aliases
  if (!runtime && args.includes("--claude")) runtime = "claude-code";

  if (!runtime) {
    console.log("");
    console.log("  Which coding agent do you use?");
    console.log("");
    runtimeKeys.forEach((key, i) => {
      console.log(`  ${i + 1}. ${RUNTIMES[key].name}`);
    });
    console.log("");
    const choice = await prompt("  Enter number (1-4): ");
    const idx = parseInt(choice) - 1;
    if (idx < 0 || idx >= runtimeKeys.length) {
      error("Invalid choice.");
      process.exit(1);
    }
    runtime = runtimeKeys[idx];
  }

  // Determine scope from flags or interactive prompt
  let scope = null;
  if (args.includes("--global")) scope = "global";
  if (args.includes("--local")) scope = "local";

  if (!scope) {
    console.log("");
    console.log("  Install location?");
    console.log("");
    console.log("  1. Global (available in all projects)");
    console.log("  2. Local (this project only)");
    console.log("");
    const choice = await prompt("  Enter number (1-2): ");
    scope = choice === "2" ? "local" : "global";
  }

  // Run gpd install <runtime> --global/--local
  log(`Installing GPD for ${RUNTIMES[runtime].name} (${scope})...`);

  // Suppress logfire warning during install
  const installEnv = { ...process.env, LOGFIRE_IGNORE_NO_CONFIG: "1" };

  // Try uv run gpd install first, fall back to gpd directly
  let result = spawnSync("uv", ["run", "gpd", "install", runtime, `--${scope}`], {
    stdio: "inherit",
    env: installEnv,
  });
  if (result.status !== 0) {
    // Fallback: try gpd directly (if installed globally)
    result = spawnSync("gpd", ["install", runtime, `--${scope}`], {
      stdio: "inherit",
      env: installEnv,
    });
  }
  if (result.status !== 0) {
    // Final fallback: run the Python module directly
    result = spawnSync(python, ["-m", "gpd.cli", "install", runtime, `--${scope}`], {
      stdio: "inherit",
      env: installEnv,
    });
  }

  if (result.status === 0) {
    console.log("");
    log("\x1b[32mInstalled successfully!\x1b[0m");
    console.log("");
    if (runtime === "claude-code" || runtime === "gemini") {
      console.log("  Start a new project:  /gpd:new-project");
    } else if (runtime === "opencode") {
      console.log("  Start a new project:  /gpd-new-project");
    } else {
      console.log("  Start a new project:  $gpd-new-project");
    }
    console.log("");
  } else {
    error("Installation failed. Check the output above for details.");
    process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
