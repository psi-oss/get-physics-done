#!/usr/bin/env node
/**
 * GPD installer — sets up Get Physics Done in your AI agent.
 *
 * Usage:
 *   npx -y github:physicalsuperintelligence/get-physics-done
 *   npx -y github:physicalsuperintelligence/get-physics-done --claude --global
 *   npx -y github:physicalsuperintelligence/get-physics-done --gemini --global
 *   npx -y github:physicalsuperintelligence/get-physics-done --codex --local
 *   npx -y github:physicalsuperintelligence/get-physics-done --opencode --global
 *   npx -y github:physicalsuperintelligence/get-physics-done --all --global
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

const red = "\x1b[31m";
const green = "\x1b[32m";
const yellow = "\x1b[33m";
const cyan = "\x1b[36m";
const dim = "\x1b[2m";
const bold = "\x1b[1m";
const reset = "\x1b[0m";

const ALL_RUNTIMES = ["claude-code", "opencode", "gemini", "codex"];
const RUNTIMES = {
  "claude-code": {
    name: "Claude Code",
    configDirName: ".claude",
    helpCommand: "/gpd:help",
    startCommand: "/gpd:new-project",
  },
  "opencode": {
    name: "OpenCode",
    configDirName: ".opencode",
    helpCommand: "/gpd-help",
    startCommand: "/gpd-new-project",
  },
  "gemini": {
    name: "Gemini CLI",
    configDirName: ".gemini",
    helpCommand: "/gpd:help",
    startCommand: "/gpd:new-project",
  },
  "codex": {
    name: "Codex",
    configDirName: ".codex",
    helpCommand: "$gpd-help",
    startCommand: "$gpd-new-project",
  },
};

function log(msg) {
  console.log(` ${cyan}i${reset} ${msg}`);
}

function success(msg) {
  console.log(` ${green}✓${reset} ${msg}`);
}

function warn(msg) {
  console.log(` ${yellow}⚠${reset} ${msg}`);
}

function error(msg) {
  console.error(` ${red}✗${reset} ${msg}`);
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
  return spawnSync(
    python,
    ["-m", "pip", "install", "--upgrade", "--quiet", spec],
    {
      encoding: "utf-8",
      env,
    }
  );
}

function flushCapturedOutput(result) {
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
  if (result.error) {
    process.stderr.write(`${result.error.message}\n`);
  }
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
  flushCapturedOutput(installResult);

  const fallbacks = sourceInstallCandidates(version);
  for (const [index, candidate] of fallbacks.entries()) {
    const previousLabel = index === 0 ? "PyPI install" : fallbacks[index - 1].label;
    log(`${previousLabel} failed. Falling back to ${candidate.label}...`);
    installResult = runPipInstall(python, candidate.spec, pipInstallEnv);
    if (installResult.status === 0) {
      return { ok: true, pythonPackageSpec, installedFrom: candidate.spec };
    }
    flushCapturedOutput(installResult);
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

function expandTilde(value) {
  if (value === "~") {
    return os.homedir();
  }
  if (value && value.startsWith("~/")) {
    return path.join(os.homedir(), value.slice(2));
  }
  return value;
}

function runtimeGlobalConfigDir(runtime) {
  if (runtime === "opencode") {
    if (process.env.OPENCODE_CONFIG_DIR) {
      return expandTilde(process.env.OPENCODE_CONFIG_DIR);
    }
    if (process.env.OPENCODE_CONFIG) {
      return path.dirname(expandTilde(process.env.OPENCODE_CONFIG));
    }
    if (process.env.XDG_CONFIG_HOME) {
      return path.join(expandTilde(process.env.XDG_CONFIG_HOME), "opencode");
    }
    return path.join(os.homedir(), ".config", "opencode");
  }

  if (runtime === "gemini") {
    return expandTilde(process.env.GEMINI_CONFIG_DIR || path.join(os.homedir(), ".gemini"));
  }

  if (runtime === "codex") {
    return expandTilde(process.env.CODEX_CONFIG_DIR || path.join(os.homedir(), ".codex"));
  }

  return expandTilde(process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude"));
}

function formatDisplayPath(filePath) {
  const home = os.homedir().replace(/\\/g, "/");
  const normalized = String(filePath).replace(/\\/g, "/");
  if (normalized === home) {
    return "~";
  }
  if (normalized.startsWith(`${home}/`)) {
    return `~${normalized.slice(home.length)}`;
  }
  return normalized;
}

function formatRuntimeList(runtimes) {
  const names = runtimes.map((runtime) => RUNTIMES[runtime].name);
  if (names.length === 0) {
    return "no runtimes";
  }
  if (names.length === 1) {
    return names[0];
  }
  if (names.length === 2) {
    return `${names[0]} and ${names[1]}`;
  }
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

function printBanner() {
  console.log("");
  console.log(`${cyan} ██████╗ ██████╗ ██████╗`);
  console.log(`██╔════╝ ██╔══██╗██╔══██╗`);
  console.log(`██║  ███╗██████╔╝██║  ██║`);
  console.log(`██║   ██║██╔═══╝ ██║  ██║`);
  console.log(`╚██████╔╝██║     ██████╔╝`);
  console.log(` ╚═════╝ ╚═╝     ╚═════╝${reset}`);
  console.log("");
  console.log(` ${bold}Get Physics Done${reset} ${dim}v${packageVersion}${reset}`);
  console.log(" Open-source AI copilot for physics research");
  console.log(" for Claude Code, Gemini CLI, Codex, and OpenCode.");
  console.log("");
}

function printHelp() {
  const installCommand = "npx -y github:physicalsuperintelligence/get-physics-done";
  console.log(` ${yellow}Usage:${reset} ${installCommand} [options]`);
  console.log("");
  console.log(` ${yellow}Options:${reset}`);
  console.log(` ${cyan}-g, --global${reset}            Install globally (runtime config dir)`);
  console.log(` ${cyan}-l, --local${reset}             Install locally (current project only)`);
  console.log(` ${cyan}--claude${reset}                Install for Claude Code only`);
  console.log(` ${cyan}--opencode${reset}              Install for OpenCode only`);
  console.log(` ${cyan}--gemini${reset}               Install for Gemini CLI only`);
  console.log(` ${cyan}--codex${reset}                Install for Codex only`);
  console.log(` ${cyan}--all${reset}                  Install for all supported runtimes`);
  console.log(` ${cyan}--force-statusline${reset}     Replace an existing runtime statusline`);
  console.log(` ${cyan}-h, --help${reset}              Show this help message`);
  console.log("");
  console.log(` ${yellow}Examples:${reset}`);
  console.log(` ${dim}# Interactive install${reset}`);
  console.log(` ${installCommand}`);
  console.log("");
  console.log(` ${dim}# Install for Claude Code globally${reset}`);
  console.log(` ${installCommand} --claude --global`);
  console.log("");
  console.log(` ${dim}# Install for Codex locally${reset}`);
  console.log(` ${installCommand} --codex --local`);
  console.log("");
  console.log(` ${dim}# Install for all runtimes globally${reset}`);
  console.log(` ${installCommand} --all --global`);
  console.log("");
}

function parseSelectedRuntimes(args) {
  const selected = [];
  const seen = new Set();

  if (args.includes("--all")) {
    return [...ALL_RUNTIMES];
  }

  for (const key of ALL_RUNTIMES) {
    if (args.includes(`--${key}`)) {
      selected.push(key);
      seen.add(key);
    }
  }

  if (args.includes("--claude") && !seen.has("claude-code")) {
    selected.push("claude-code");
    seen.add("claude-code");
  }
  if ((args.includes("--gemini") || args.includes("--gemini-cli")) && !seen.has("gemini")) {
    selected.push("gemini");
    seen.add("gemini");
  }
  if (args.includes("--codex") && !seen.has("codex")) {
    selected.push("codex");
    seen.add("codex");
  }
  if (args.includes("--opencode") && !seen.has("opencode")) {
    selected.push("opencode");
    seen.add("opencode");
  }

  return selected;
}

async function selectRuntimes(args) {
  const selected = parseSelectedRuntimes(args);
  if (selected.length > 0) {
    return selected;
  }

  if (!process.stdin.isTTY) {
    warn("Non-interactive terminal detected, defaulting to Claude Code.");
    return ["claude-code"];
  }

  console.log(` ${yellow}Which runtime(s) would you like to install for?${reset}`);
  console.log("");
  console.log(
    ` ${cyan}1${reset}) ${RUNTIMES["claude-code"].name} ${dim}(${formatDisplayPath(runtimeGlobalConfigDir("claude-code"))})${reset}`
  );
  console.log(` ${cyan}2${reset}) ${RUNTIMES.gemini.name} ${dim}(${formatDisplayPath(runtimeGlobalConfigDir("gemini"))})${reset}`);
  console.log(` ${cyan}3${reset}) ${RUNTIMES.codex.name} ${dim}(${formatDisplayPath(runtimeGlobalConfigDir("codex"))})${reset}`);
  console.log(` ${cyan}4${reset}) ${RUNTIMES.opencode.name} ${dim}(${formatDisplayPath(runtimeGlobalConfigDir("opencode"))})${reset}`);
  console.log(` ${cyan}5${reset}) All runtimes`);
  console.log("");

  const choice = ((await prompt(` Choice ${dim}[1]${reset}: `)) || "1").toLowerCase();
  if (choice === "5" || choice === "all" || choice === "all runtimes") {
    return [...ALL_RUNTIMES];
  }
  if (choice === "4" || choice === "codex") {
    return ["codex"];
  }
  if (choice === "3" || choice === "gemini" || choice === "gemini cli") {
    return ["gemini"];
  }
  if (choice === "2" || choice === "opencode") {
    return ["opencode"];
  }
  if (choice === "1" || choice === "claude" || choice === "claude code" || choice === "claude-code") {
    return ["claude-code"];
  }

  error(`Invalid runtime selection: ${choice}`);
  process.exit(1);
}

async function selectInstallScope(args, runtimes) {
  if (args.includes("--global") || args.includes("-g")) {
    return "global";
  }
  if (args.includes("--local") || args.includes("-l")) {
    return "local";
  }

  if (!process.stdin.isTTY) {
    warn("Non-interactive terminal detected, defaulting to global install.");
    return "global";
  }

  const globalExamples = runtimes.map((runtime) => formatDisplayPath(runtimeGlobalConfigDir(runtime))).join(", ");
  const localExamples = runtimes.map((runtime) => `./${RUNTIMES[runtime].configDirName}`).join(", ");

  console.log(` ${yellow}Where would you like to install?${reset}`);
  console.log("");
  console.log(` ${cyan}1${reset}) Global ${dim}(${globalExamples})${reset} - available in all projects`);
  console.log(` ${cyan}2${reset}) Local ${dim}(${localExamples})${reset} - this project only`);
  console.log("");

  const choice = ((await prompt(` Choice ${dim}[1]${reset}: `)) || "1").toLowerCase();
  if (choice === "1" || choice === "global") {
    return "global";
  }
  if (choice === "2" || choice === "local") {
    return "local";
  }

  error(`Invalid install location: ${choice}`);
  process.exit(1);
}

function buildRuntimeInstallArgs(runtimes, scope, forceStatusline) {
  const installArgs = ["-m", "gpd.cli", "install"];
  if (runtimes.length === ALL_RUNTIMES.length) {
    installArgs.push("--all");
  } else {
    installArgs.push(...runtimes);
  }
  installArgs.push(`--${scope}`);
  if (forceStatusline) {
    installArgs.push("--force-statusline");
  }
  return installArgs;
}

function printCompletionSummary(runtimes, scope, launcherInfo) {
  console.log("");
  success(`Installed GPD for ${formatRuntimeList(runtimes)} (${scope}).`);
  console.log("");

  if (runtimes.length === 1) {
    const runtime = runtimes[0];
    console.log(`  Start a new project:  ${RUNTIMES[runtime].startCommand}`);
    console.log(`  Show commands:        ${RUNTIMES[runtime].helpCommand}`);
  } else {
    const width = Math.max(...runtimes.map((runtime) => RUNTIMES[runtime].name.length));
    console.log("  Start a new project:");
    for (const runtime of runtimes) {
      console.log(`  ${RUNTIMES[runtime].name.padEnd(width)}  ${RUNTIMES[runtime].startCommand}`);
    }
  }

  if (!launcherInfo.exposedLauncher) {
    console.log(`  Shell CLI path:      ${launcherInfo.primaryLauncher}`);
    console.log(`  Add to PATH:         ${path.dirname(launcherInfo.primaryLauncher)}`);
    if (launcherInfo.conflictPath) {
      console.log(`  Existing launcher left untouched:  ${launcherInfo.conflictPath}`);
    }
  }
  console.log("");
}

async function main() {
  const args = process.argv.slice(2);
  const hasHelp = args.includes("--help") || args.includes("-h");
  const forceStatusline = args.includes("--force-statusline");

  printBanner();

  if (hasHelp) {
    printHelp();
    return;
  }

  if ((args.includes("--global") || args.includes("-g")) && (args.includes("--local") || args.includes("-l"))) {
    error("Cannot specify both --global and --local.");
    process.exit(1);
  }

  const selectedRuntimes = await selectRuntimes(args);
  const scope = await selectInstallScope(args, selectedRuntimes);

  const basePython = checkPython();
  if (!basePython) {
    error("Python 3.11+ is required but not found.");
    error("Install from https://python.org or via your package manager.");
    process.exit(1);
  }
  success(`Found ${basePython.text}`);

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
  log(`Installing GPD for ${formatRuntimeList(selectedRuntimes)} (${scope})...`);

  // Suppress logfire warning during install
  const installEnv = { ...process.env, LOGFIRE_IGNORE_NO_CONFIG: "1" };
  const installArgs = buildRuntimeInstallArgs(selectedRuntimes, scope, forceStatusline);

  // Run the installer through the managed Python interpreter.
  const result = spawnSync(managedEnv.python, installArgs, {
    stdio: "inherit",
    env: installEnv,
  });

  if (result.status === 0) {
    printCompletionSummary(selectedRuntimes, scope, launcherInfo);
  } else {
    error("Installation failed. Check the output above for details.");
    process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
