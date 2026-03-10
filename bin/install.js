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
  },
  "opencode": {
    name: "OpenCode",
    configDirName: ".opencode",
  },
  "gemini": {
    name: "Gemini CLI",
    configDirName: ".gemini",
  },
  "codex": {
    name: "Codex",
    configDirName: ".codex",
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

function repositorySshGitUrl(repositoryField) {
  const httpsUrl = repositoryGitUrl(repositoryField);
  if (!httpsUrl) {
    return null;
  }
  const match = httpsUrl.match(/^https:\/\/github\.com\/(.+)$/);
  if (!match) {
    return null;
  }
  return `ssh://git@github.com/${match[1]}`;
}

function sourceInstallCandidates(version) {
  const repoBaseUrl = repositoryBaseUrl(repository);
  const repoGitUrl = repositoryGitUrl(repository);
  const repoSshUrl = repositorySshGitUrl(repository);
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
        noCache: true,
      }
    );
  }

  if (repoGitUrl) {
    candidates.push(
      {
        label: `GitHub HTTPS git checkout for v${version}`,
        spec: `git+${repoGitUrl}@v${version}`,
      },
      {
        label: `HTTPS git checkout of ${GITHUB_FALLBACK_BRANCH}`,
        spec: `git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}`,
        noCache: true,
      }
    );
  }

  if (repoSshUrl) {
    candidates.push(
      {
        label: `SSH git checkout for v${version}`,
        spec: `git+${repoSshUrl}@v${version}`,
      },
      {
        label: `SSH git checkout of ${GITHUB_FALLBACK_BRANCH}`,
        spec: `git+${repoSshUrl}@${GITHUB_FALLBACK_BRANCH}`,
        noCache: true,
      }
    );
  }

  return candidates;
}

function latestMainInstallCandidates() {
  const repoBaseUrl = repositoryBaseUrl(repository);
  const repoGitUrl = repositoryGitUrl(repository);
  const repoSshUrl = repositorySshGitUrl(repository);
  const candidates = [];

  if (repoBaseUrl) {
    candidates.push({
      label: `current ${GITHUB_FALLBACK_BRANCH} branch source archive`,
      spec: `${repoBaseUrl}/archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz`,
      noCache: true,
    });
  }

  if (repoGitUrl) {
    candidates.push({
      label: `HTTPS git checkout of ${GITHUB_FALLBACK_BRANCH}`,
      spec: `git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}`,
      noCache: true,
    });
  }

  if (repoSshUrl) {
    candidates.push({
      label: `SSH git checkout of ${GITHUB_FALLBACK_BRANCH}`,
      spec: `git+${repoSshUrl}@${GITHUB_FALLBACK_BRANCH}`,
      noCache: true,
    });
  }

  return candidates;
}

function runPipInstall(python, spec, env, options = {}) {
  const args = ["-m", "pip", "install", "--upgrade", "--quiet"];
  if (options.forceReinstall) {
    args.push("--force-reinstall");
  }
  if (options.noCache) {
    args.push("--no-cache-dir");
  }
  args.push(spec);
  return spawnSync(
    python,
    args,
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

function installManagedPackage(python, version, options = {}) {
  const { forceReinstall = false, preferMain = false } = options;
  const pythonPackageSpec = `${PYTHON_PACKAGE_NAME}==${version}`;
  const pipInstallEnv = { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: "1" };

  if (preferMain) {
    const upgradeCandidates = latestMainInstallCandidates();
    if (upgradeCandidates.length > 0) {
      log(`Upgrading GPD from the latest GitHub ${GITHUB_FALLBACK_BRANCH} branch into the managed environment...`);
      let installResult = runPipInstall(python, upgradeCandidates[0].spec, pipInstallEnv, {
        forceReinstall: true,
        noCache: upgradeCandidates[0].noCache,
      });
      if (installResult.status === 0) {
        return { ok: true, pythonPackageSpec, installedFrom: upgradeCandidates[0].spec };
      }
      flushCapturedOutput(installResult);

      for (const [index, candidate] of upgradeCandidates.entries()) {
        if (index === 0) {
          continue;
        }
        const previousLabel = upgradeCandidates[index - 1].label;
        log(`${previousLabel} failed. Falling back to ${candidate.label}...`);
        installResult = runPipInstall(python, candidate.spec, pipInstallEnv, {
          forceReinstall: true,
          noCache: candidate.noCache,
        });
        if (installResult.status === 0) {
          return { ok: true, pythonPackageSpec, installedFrom: candidate.spec };
        }
        flushCapturedOutput(installResult);
      }

      log(`GitHub ${GITHUB_FALLBACK_BRANCH} upgrade failed. Falling back to the matching ${pythonPackageSpec} release...`);
    }
  }

  const action = forceReinstall ? "Reinstalling" : "Installing";
  log(`${action} ${pythonPackageSpec} into the managed environment...`);
  let installResult = runPipInstall(python, pythonPackageSpec, pipInstallEnv, {
    forceReinstall,
  });
  if (installResult.status === 0) {
    return { ok: true, pythonPackageSpec };
  }
  flushCapturedOutput(installResult);

  const fallbacks = sourceInstallCandidates(version);
  for (const [index, candidate] of fallbacks.entries()) {
    const previousLabel = index === 0 ? "PyPI install" : fallbacks[index - 1].label;
    log(`${previousLabel} failed. Falling back to ${candidate.label}...`);
    installResult = runPipInstall(python, candidate.spec, pipInstallEnv, {
      forceReinstall,
      noCache: candidate.noCache,
    });
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

function runtimeCommandPrefix(runtime) {
  if (runtime === "codex") {
    return "$gpd-";
  }
  if (runtime === "opencode") {
    return "/gpd-";
  }
  return "/gpd:";
}

function formatRuntimeCommand(runtime, action) {
  const prefix = runtimeCommandPrefix(runtime);
  return prefix.endsWith(":") ? `${prefix}${action}` : `${prefix}${action}`;
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
  console.log(` ${cyan}--reinstall${reset}             Reinstall the matching Python release in ~/.gpd/venv`);
  console.log(` ${cyan}--upgrade${reset}               Upgrade ~/.gpd/venv from the latest GitHub main source`);
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
  console.log(` ${dim}# Reinstall the matching managed Python release${reset}`);
  console.log(` ${installCommand} --reinstall --claude --local`);
  console.log("");
  console.log(` ${dim}# Upgrade to the latest GitHub main source${reset}`);
  console.log(` ${installCommand} --upgrade --claude --local`);
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
  if (choice === "4" || choice === "opencode") {
    return ["opencode"];
  }
  if (choice === "3" || choice === "codex") {
    return ["codex"];
  }
  if (choice === "2" || choice === "gemini" || choice === "gemini cli") {
    return ["gemini"];
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

function printCompletionSummary(runtimes, scope) {
  console.log("");
  success(`Installed GPD for ${formatRuntimeList(runtimes)} (${scope}).`);
  console.log("");

  if (runtimes.length === 1) {
    const runtime = runtimes[0];
    console.log(`  Start a new project:  ${formatRuntimeCommand(runtime, "new-project")}`);
    console.log(`  Show commands:        ${formatRuntimeCommand(runtime, "help")}`);
  } else {
    const width = Math.max(...runtimes.map((runtime) => RUNTIMES[runtime].name.length));
    console.log("  Start a new project:");
    for (const runtime of runtimes) {
      console.log(`  ${RUNTIMES[runtime].name.padEnd(width)}  ${formatRuntimeCommand(runtime, "new-project")}`);
    }
  }
  console.log("");
}

async function main() {
  const args = process.argv.slice(2);
  const hasHelp = args.includes("--help") || args.includes("-h");
  const forceStatusline = args.includes("--force-statusline");
  const reinstallManagedPackage = args.includes("--reinstall");
  const upgradeManagedPackage = args.includes("--upgrade");

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
  const packageInstall = installManagedPackage(managedEnv.python, packageVersion, {
    forceReinstall: reinstallManagedPackage || upgradeManagedPackage,
    preferMain: upgradeManagedPackage,
  });
  if (!packageInstall.ok) {
    error(`Failed to install ${packageInstall.pythonPackageSpec}.`);
    process.exit(1);
  }

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
    printCompletionSummary(selectedRuntimes, scope);
  } else {
    error("Installation failed. Check the output above for details.");
    process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
