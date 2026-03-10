#!/usr/bin/env node
/**
 * GPD installer — sets up Get Physics Done in your AI agent.
 *
 * Usage:
 *   npx github:physicalsuperintelligence/get-physics-done
 *   npx github:physicalsuperintelligence/get-physics-done --claude --global
 *   npx github:physicalsuperintelligence/get-physics-done --gemini --global
 *   npx github:physicalsuperintelligence/get-physics-done --codex --local
 *   npx github:physicalsuperintelligence/get-physics-done --opencode --global
 */

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const readline = require("readline");
const { version: packageVersion, repository } = require("../package.json");

const PYTHON_PACKAGE_NAME = "get-physics-done";
const GPD_HOME_ENV = "GPD_HOME";
const GPD_HOME_DIRNAME = ".gpd";
const LAUNCHER_MARKER = "Managed by Get Physics Done";
const GITHUB_FALLBACK_BRANCH = "main";

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

function isWindows() {
  return process.platform === "win32";
}

function pythonVersionInfo(python) {
  const result = spawnSync(python, ["--version"], { encoding: "utf-8" });
  if (result.status !== 0) {
    return null;
  }

  const versionText = (result.stdout || result.stderr).trim();
  const match = versionText.match(/(\d+)\.(\d+)/);
  if (!match) {
    return null;
  }

  return {
    command: python,
    text: versionText,
    major: parseInt(match[1], 10),
    minor: parseInt(match[2], 10),
  };
}

function checkPython() {
  for (const cmd of ["python3", "python"]) {
    const info = pythonVersionInfo(cmd);
    if (!info) {
      continue;
    }
    if (info.major > 3 || (info.major === 3 && info.minor >= 11)) {
      return info;
    }
  }
  return null;
}

function hasVenvSupport(python) {
  const result = spawnSync(python, ["-m", "venv", "--help"], { stdio: "ignore" });
  return result.status === 0;
}

function checkPip(python) {
  const result = spawnSync(python, ["-m", "pip", "--version"], { encoding: "utf-8" });
  if (result.status !== 0) {
    return null;
  }
  return (result.stdout || result.stderr).trim();
}

function repositoryBaseUrl(repositoryField) {
  const raw = typeof repositoryField === "string"
    ? repositoryField
    : repositoryField && typeof repositoryField.url === "string"
      ? repositoryField.url
      : "";
  if (!raw) {
    return null;
  }

  let normalized = raw.trim();
  if (normalized.startsWith("git+")) {
    normalized = normalized.slice(4);
  }
  if (normalized.startsWith("git@github.com:")) {
    normalized = `https://github.com/${normalized.slice("git@github.com:".length)}`;
  }
  normalized = normalized.replace(/\.git$/i, "").replace(/\/+$/, "");
  return normalized || null;
}

function repositoryGitUrl(repositoryField) {
  const raw = typeof repositoryField === "string"
    ? repositoryField
    : repositoryField && typeof repositoryField.url === "string"
      ? repositoryField.url
      : "";
  if (!raw) {
    return null;
  }

  let normalized = raw.trim();
  if (normalized.startsWith("git+")) {
    normalized = normalized.slice(4);
  }
  if (normalized.startsWith("git@github.com:")) {
    normalized = `https://github.com/${normalized.slice("git@github.com:".length)}`;
  }
  normalized = normalized.replace(/\/+$/, "");
  if (!normalized.endsWith(".git")) {
    normalized = `${normalized}.git`;
  }
  return normalized || null;
}

function sourceInstallCandidates(version) {
  const repoBaseUrl = repositoryBaseUrl(repository);
  const repoGitUrl = repositoryGitUrl(repository);
  const candidates = [];

  if (repoBaseUrl) {
    candidates.push(
      {
        label: `GitHub source archive for v${version}`,
        spec: `${repoBaseUrl}/archive/refs/tags/v${version}.tar.gz`,
      },
      {
        label: `current ${GITHUB_FALLBACK_BRANCH} branch source archive`,
        spec: `${repoBaseUrl}/archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz`,
      }
    );
  }

  if (repoGitUrl) {
    candidates.push(
      {
        label: `GitHub git checkout for v${version}`,
        spec: `git+${repoGitUrl}@v${version}`,
      },
      {
        label: `authenticated git checkout of ${GITHUB_FALLBACK_BRANCH}`,
        spec: `git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}`,
      }
    );
  }

  return candidates;
}

function runPipInstall(python, spec, env) {
  const result = spawnSync(
    python,
    ["-m", "pip", "install", "--upgrade", spec],
    {
      encoding: "utf-8",
      env,
    }
  );

  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }

  return result;
}

function gpdHomeDir() {
  return process.env[GPD_HOME_ENV] || path.join(os.homedir(), GPD_HOME_DIRNAME);
}

function managedEnvDir(gpdHome) {
  return path.join(gpdHome, "venv");
}

function managedPythonPath(venvDir) {
  return path.join(venvDir, isWindows() ? "Scripts" : "bin", isWindows() ? "python.exe" : "python");
}

function launcherBasename() {
  return isWindows() ? "gpd.cmd" : "gpd";
}

function managedLauncherPath(gpdHome) {
  return path.join(gpdHome, "bin", launcherBasename());
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function launcherContents(pythonPath) {
  if (isWindows()) {
    return `@echo off\r\nREM ${LAUNCHER_MARKER}\r\n"${pythonPath}" -m gpd.cli %*\r\n`;
  }
  return `#!/bin/sh\n# ${LAUNCHER_MARKER}\nexec ${shellQuote(pythonPath)} -m gpd.cli "$@"\n`;
}

function writeLauncher(launcherPath, pythonPath) {
  fs.mkdirSync(path.dirname(launcherPath), { recursive: true });
  fs.writeFileSync(launcherPath, launcherContents(pythonPath), { encoding: "utf-8" });
  if (!isWindows()) {
    fs.chmodSync(launcherPath, 0o755);
  }
}

function isManagedLauncher(launcherPath) {
  try {
    return fs.readFileSync(launcherPath, "utf-8").includes(LAUNCHER_MARKER);
  } catch {
    return false;
  }
}

function preferredUserBinDirs(gpdHome) {
  const home = os.homedir();
  return [
    path.join(gpdHome, "bin"),
    path.join(home, ".local", "bin"),
    path.join(home, "bin"),
  ];
}

function pathEntrySet() {
  return new Set(
    (process.env.PATH || "")
      .split(path.delimiter)
      .filter(Boolean)
      .map((entry) => path.resolve(entry))
  );
}

function exposeLauncher(gpdHome, pythonPath) {
  const primaryLauncher = managedLauncherPath(gpdHome);
  writeLauncher(primaryLauncher, pythonPath);

  const pathEntries = pathEntrySet();
  let conflictPath = null;
  for (const candidateDir of preferredUserBinDirs(gpdHome)) {
    const resolvedDir = path.resolve(candidateDir);
    if (!pathEntries.has(resolvedDir)) {
      continue;
    }

    const candidateLauncher = path.join(resolvedDir, launcherBasename());
    if (path.resolve(candidateLauncher) === path.resolve(primaryLauncher)) {
      return { primaryLauncher, exposedLauncher: candidateLauncher, conflictPath: null };
    }

    fs.mkdirSync(resolvedDir, { recursive: true });
    if (fs.existsSync(candidateLauncher) && !isManagedLauncher(candidateLauncher)) {
      conflictPath = candidateLauncher;
      continue;
    }

    writeLauncher(candidateLauncher, pythonPath);
    return { primaryLauncher, exposedLauncher: candidateLauncher, conflictPath: null };
  }

  return { primaryLauncher, exposedLauncher: null, conflictPath };
}

function ensureManagedEnvironment(basePython) {
  const gpdHome = gpdHomeDir();
  const venvDir = managedEnvDir(gpdHome);
  const managedPython = managedPythonPath(venvDir);
  const existingManaged = pythonVersionInfo(managedPython);

  let shouldCreate = !existingManaged;
  if (
    existingManaged
    && (existingManaged.major < 3 || (existingManaged.major === 3 && existingManaged.minor < 11))
  ) {
    log(`Recreating managed environment at ${venvDir} (found ${existingManaged.text}).`);
    fs.rmSync(venvDir, { recursive: true, force: true });
    shouldCreate = true;
  }

  if (shouldCreate) {
    log(`Creating managed Python environment at ${venvDir}...`);
    fs.mkdirSync(gpdHome, { recursive: true });
    const venvResult = spawnSync(basePython.command, ["-m", "venv", venvDir], {
      stdio: "inherit",
    });
    if (venvResult.status !== 0) {
      error("Failed to create the managed Python environment.");
      error("Install Python 3.11+ with the standard library `venv` module, then rerun the bootstrap installer.");
      process.exit(1);
    }
  }

  let pipVersion = checkPip(managedPython);
  if (!pipVersion) {
    log("Bootstrapping pip inside the managed environment...");
    const ensurePipResult = spawnSync(managedPython, ["-m", "ensurepip", "--upgrade"], {
      stdio: "inherit",
    });
    if (ensurePipResult.status !== 0) {
      error("Managed Python environment is missing pip and could not be repaired.");
      process.exit(1);
    }
    pipVersion = checkPip(managedPython);
    if (!pipVersion) {
      error("Managed Python environment is missing pip.");
      process.exit(1);
    }
  }

  log(`Using managed environment at ${venvDir}`);
  log(`Found ${pipVersion}`);
  return { gpdHome, venvDir, python: managedPython };
}

function installManagedPackage(python, version) {
  const pythonPackageSpec = `${PYTHON_PACKAGE_NAME}==${version}`;
  const pipInstallEnv = { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: "1" };

  log(`Installing ${pythonPackageSpec} into the managed environment...`);
  let installResult = runPipInstall(python, pythonPackageSpec, pipInstallEnv);
  if (installResult.status === 0) {
    return { ok: true, pythonPackageSpec };
  }

  const fallbacks = sourceInstallCandidates(version);
  for (const [index, candidate] of fallbacks.entries()) {
    const previousLabel = index === 0 ? "PyPI install" : fallbacks[index - 1].label;
    log(`${previousLabel} failed. Falling back to ${candidate.label}...`);
    installResult = runPipInstall(python, candidate.spec, pipInstallEnv);
    if (installResult.status === 0) {
      return { ok: true, pythonPackageSpec, installedFrom: candidate.spec };
    }
  }

  return { ok: false, pythonPackageSpec };
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
  console.log("  Open-source AI copilot for physics research");
  console.log("");

  const basePython = checkPython();
  if (!basePython) {
    error("Python 3.11+ is required but not found.");
    error("Install from https://python.org or via your package manager.");
    process.exit(1);
  }
  log(`Found ${basePython.text}`);

  if (!hasVenvSupport(basePython.command)) {
    error(`Python 3.11+ with the standard library 'venv' module is required, but ${basePython.command} cannot create virtual environments.`);
    error("Install venv support for that interpreter, then rerun the bootstrap installer.");
    process.exit(1);
  }

  const managedEnv = ensureManagedEnvironment(basePython);
  const packageInstall = installManagedPackage(managedEnv.python, packageVersion);
  if (!packageInstall.ok) {
    error(`Failed to install ${packageInstall.pythonPackageSpec}.`);
    process.exit(1);
  }

  const launcherInfo = exposeLauncher(managedEnv.gpdHome, managedEnv.python);

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
  if (!runtime && (args.includes("--gemini") || args.includes("--gemini-cli"))) runtime = "gemini";

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

  // Run the installer through the managed Python interpreter.
  const result = spawnSync(managedEnv.python, ["-m", "gpd.cli", "install", runtime, `--${scope}`], {
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
    if (launcherInfo.exposedLauncher) {
      console.log("  Shell CLI:           gpd view");
    } else {
      console.log(`  Shell CLI path:      ${launcherInfo.primaryLauncher} view`);
      console.log(`  Add to PATH:         ${path.dirname(launcherInfo.primaryLauncher)}`);
      if (launcherInfo.conflictPath) {
        console.log(`  Existing launcher left untouched:  ${launcherInfo.conflictPath}`);
      }
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
