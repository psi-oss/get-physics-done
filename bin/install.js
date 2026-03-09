#!/usr/bin/env node
/**
 * GPD installer — sets up Get Physics Done in your AI agent.
 *
 * Usage:
 *   npx github:physicalsuperintelligence/get-physics-done
 *   npx github:physicalsuperintelligence/get-physics-done --claude --global
 *   npx github:physicalsuperintelligence/get-physics-done --opencode --global
 */

const { execSync, spawnSync } = require("child_process");
const readline = require("readline");
const { version: packageVersion } = require("../package.json");

const PYTHON_PACKAGE_NAME = "get-physics-done";

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
      if (!match) {
        continue;
      }
      const major = parseInt(match[1], 10);
      const minor = parseInt(match[2], 10);
      if (major > 3 || (major === 3 && minor >= 11)) {
        return cmd;
      }
    } catch {}
  }
  return null;
}

function checkPip(python) {
  const result = spawnSync(python, ["-m", "pip", "--version"], { encoding: "utf-8" });
  if (result.status !== 0) {
    return null;
  }
  return (result.stdout || result.stderr).trim();
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

  const pipVersion = checkPip(python);
  if (!pipVersion) {
    error(`Python 3.11+ with pip is required, but ${python} does not have pip available.`);
    error("Install pip for that interpreter, then rerun the bootstrap installer.");
    process.exit(1);
  }
  log(`Found ${pipVersion}`);

  // Install the version-matched Python package release.
  const pythonPackageSpec = `${PYTHON_PACKAGE_NAME}==${packageVersion}`;

  log(`Installing ${pythonPackageSpec} from PyPI...`);
  const packageResult = spawnSync(
    python,
    ["-m", "pip", "install", "--upgrade", pythonPackageSpec],
    { stdio: "inherit" }
  );
  if (packageResult.status !== 0) {
    error(`Failed to install ${pythonPackageSpec}.`);
    process.exit(1);
  }

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
  if (!runtime && args.includes("--gemini-cli")) runtime = "gemini";

  if (!runtime) {
    console.log("");
    console.log("  Which AI agent do you use?");
    console.log("");
    runtimeKeys.forEach((key, i) => {
      console.log(`  ${i + 1}. ${RUNTIMES[key].name}`);
    });
    console.log("");
    const choice = await prompt(`  Enter number (1-${runtimeKeys.length}): `);
    const idx = parseInt(choice, 10) - 1;
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

  log(`Installing GPD for ${RUNTIMES[runtime].name} (${scope})...`);

  // Suppress logfire warning during install
  const installEnv = { ...process.env, LOGFIRE_IGNORE_NO_CONFIG: "1" };

  // Run the installer through the same Python interpreter that installed GPD.
  const result = spawnSync(python, ["-m", "gpd.cli", "install", runtime, `--${scope}`], {
    stdio: "inherit",
    env: installEnv,
  });

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
