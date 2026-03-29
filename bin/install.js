#!/usr/bin/env node
/**
 * GPD bootstrap installer — installs or uninstalls Get Physics Done.
 *
 * Usage:
 *   npx -y get-physics-done
 *   npx -y get-physics-done --<runtime-flag> --global
 *   npx -y get-physics-done --<runtime-flag> --local
 *   npx -y get-physics-done --all --global
 *   npx -y get-physics-done --uninstall
 *   npx -y get-physics-done --uninstall --<runtime-flag> --global
 *   npx -y get-physics-done uninstall --all --local
 */

const fs = require("fs");
const http = require("http");
const https = require("https");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const readline = require("readline");
const {
  version: packageVersion,
  repository,
  gpdPythonVersion: rawPythonPackageVersion,
} = require("../package.json");
const RUNTIME_CATALOG = require("../src/gpd/adapters/runtime_catalog.json");

const pythonPackageVersion = typeof rawPythonPackageVersion === "string" ? rawPythonPackageVersion.trim() : "";
const GPD_HOME_ENV = "GPD_HOME";
const GPD_HOME_DIRNAME = "GPD";
const GITHUB_MAIN_BRANCH = "main";
const BOOTSTRAP_TEST_PROBES_ENV = "GPD_BOOTSTRAP_TEST_PROBES";
const BOOTSTRAP_DISABLE_NETWORK_PROBES_ENV = "GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES";
const INSTALL_CANDIDATE_PROBE_TIMEOUT_MS = 5000;
const INSTALL_CANDIDATE_PROBE_REDIRECT_LIMIT = 5;
const MIN_SUPPORTED_PYTHON_MAJOR = 3;
const MIN_SUPPORTED_PYTHON_MINOR = 11;
const PREFERRED_VERSIONED_PYTHON_MINORS = [13, 12, 11];

const red = "\x1b[31m";
const green = "\x1b[32m";
const yellow = "\x1b[33m";
const cyan = "\x1b[36m";
const dim = "\x1b[2m";
const bold = "\x1b[1m";
const reset = "\x1b[0m";
const brandLogo = "\x1b[38;2;243;240;232m";
const brandTitle = "\x1b[38;2;247;244;237m";
const brandMeta = "\x1b[38;2;158;152;140m";
const brandAccent = "\x1b[38;2;216;199;163m";
const brandDisplayName = "Get Physics Done";
const brandOwner = "Physical Superintelligence PBC";
const brandOwnerShort = "PSI";
const brandCopyrightYear = 2026;
const productPositioning = "Open-source AI copilot for physics research";

let bootstrapProbeOverridesCache = undefined;

const ALL_RUNTIMES = RUNTIME_CATALOG.map((runtime) => runtime.runtime_name);
const RUNTIME_BY_NAME = Object.fromEntries(RUNTIME_CATALOG.map((runtime) => [runtime.runtime_name, runtime]));

function runtimeRecord(runtime) {
  const record = RUNTIME_BY_NAME[runtime];
  if (!record) {
    throw new Error(`Unknown runtime: ${runtime}`);
  }
  return record;
}

function runtimeDisplayName(runtime) {
  return runtimeRecord(runtime).display_name;
}

function runtimeConfigDirName(runtime) {
  return runtimeRecord(runtime).config_dir_name;
}

function runtimeInstallFlag(runtime) {
  return runtimeRecord(runtime).install_flag;
}

function runtimeSelectionFlags(runtime) {
  return runtimeRecord(runtime).selection_flags || [];
}

function runtimeSelectionFlagList(runtime) {
  return [...new Set([runtimeInstallFlag(runtime), ...runtimeSelectionFlags(runtime)])];
}

function runtimeSelectionAliases(runtime) {
  return runtimeRecord(runtime).selection_aliases || [];
}

function runtimeCommandPrefix(runtime) {
  return runtimeRecord(runtime).command_prefix || "";
}

function runtimeSurfaceCommand(runtime, commandName) {
  return `${runtimeCommandPrefix(runtime)}${commandName}`;
}

const DEFAULT_PUBLIC_SURFACE_TEXT = Object.freeze({
  settingsCommandSentence:
    "After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture.",
  settingsRecommendationSentence: "The safest starting point is `review` plus runtime defaults.",
});

function readOptionalUtf8(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return null;
  }
}

function extractConcatenatedDoubleQuotedString(source, marker) {
  if (typeof source !== "string" || !source.includes(marker)) {
    return null;
  }

  const groupedStrings = /((?:"(?:[^"\\]|\\.)*"\s*)+)/g;
  for (const match of source.matchAll(groupedStrings)) {
    const group = match[1];
    if (!group.includes(marker)) {
      continue;
    }

    const literals = group.match(/"(?:[^"\\]|\\.)*"/g);
    if (!literals) {
      continue;
    }

    return literals
      .map((literal) => {
        try {
          return JSON.parse(literal);
        } catch {
          return literal.slice(1, -1);
        }
      })
      .join("");
  }

  return null;
}

function loadSharedPublicSurfaceText() {
  const cliSource = readOptionalUtf8(path.join(__dirname, "..", "src", "gpd", "cli.py"));
  const settingsCombined = extractConcatenatedDoubleQuotedString(
    cliSource,
    DEFAULT_PUBLIC_SURFACE_TEXT.settingsCommandSentence,
  );
  if (!settingsCombined) {
    return DEFAULT_PUBLIC_SURFACE_TEXT;
  }

  const recommendationMarker = ` ${DEFAULT_PUBLIC_SURFACE_TEXT.settingsRecommendationSentence}`;
  const splitIndex = settingsCombined.indexOf(recommendationMarker);
  if (splitIndex < 0) {
    return {
      settingsCommandSentence: settingsCombined.trim(),
      settingsRecommendationSentence: DEFAULT_PUBLIC_SURFACE_TEXT.settingsRecommendationSentence,
    };
  }

  return {
    settingsCommandSentence: settingsCombined.slice(0, splitIndex).trim(),
    settingsRecommendationSentence: settingsCombined.slice(splitIndex + 1).trim(),
  };
}

const SHARED_PUBLIC_SURFACE_TEXT = loadSharedPublicSurfaceText();
const SETTINGS_COMMAND_PREFIX = "After startup, use the runtime `settings` command ";

function settingsCommandTail() {
  const { settingsCommandSentence } = SHARED_PUBLIC_SURFACE_TEXT;
  if (settingsCommandSentence.startsWith(SETTINGS_COMMAND_PREFIX)) {
    return settingsCommandSentence.slice(SETTINGS_COMMAND_PREFIX.length);
  }
  return "to review autonomy, workflow defaults, and model-cost posture.";
}

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

function isSupportedPython(info) {
  if (!info) {
    return false;
  }
  return info.major > MIN_SUPPORTED_PYTHON_MAJOR
    || (info.major === MIN_SUPPORTED_PYTHON_MAJOR && info.minor >= MIN_SUPPORTED_PYTHON_MINOR);
}

function preferredPythonCommands() {
  return [
    ...PREFERRED_VERSIONED_PYTHON_MINORS.map((minor) => `python3.${minor}`),
    "python3",
    "python",
  ];
}

function checkPython() {
  // Prefer explicit, known-good minor versions before generic aliases so a
  // too-new `python3` does not mask an installed compatible interpreter.
  for (const cmd of preferredPythonCommands()) {
    const info = pythonVersionInfo(cmd);
    if (isSupportedPython(info)) {
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

function normalizedRepositoryUrl(repositoryField) {
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
  return normalized.replace(/\/+$/, "") || null;
}

function repositoryBaseUrl(repositoryField) {
  const normalized = normalizedRepositoryUrl(repositoryField);
  if (!normalized) {
    return null;
  }
  return normalized.replace(/\.git$/i, "") || null;
}

function repositoryGitUrl(repositoryField) {
  let normalized = normalizedRepositoryUrl(repositoryField);
  if (!normalized) {
    return null;
  }
  if (!normalized.endsWith(".git")) {
    normalized = `${normalized}.git`;
  }
  return normalized || null;
}

function releaseInstallCandidates(version) {
  const repoBaseUrl = repositoryBaseUrl(repository);
  const repoGitUrl = repositoryGitUrl(repository);
  const candidates = [];

  if (repoBaseUrl) {
    candidates.push(
      {
        label: `GitHub source archive for v${version}`,
        spec: `${repoBaseUrl}/archive/refs/tags/v${version}.tar.gz`,
        probe: {
          kind: "http",
        },
      }
    );
  }

  // Release installs stay pinned to the matching tagged GitHub source.
  if (repoGitUrl) {
    candidates.push(
      {
        label: `HTTPS git checkout for v${version}`,
        spec: `git+${repoGitUrl}@v${version}`,
        probe: {
          kind: "git",
          repoUrl: repoGitUrl,
          ref: `v${version}`,
          refNamespace: "tags",
        },
      }
    );
  }

  return candidates;
}

function mainBranchInstallCandidates() {
  const repoBaseUrl = repositoryBaseUrl(repository);
  const repoGitUrl = repositoryGitUrl(repository);
  const candidates = [];

  if (repoBaseUrl) {
    candidates.push({
      label: `current ${GITHUB_MAIN_BRANCH} branch source archive`,
      spec: `${repoBaseUrl}/archive/refs/heads/${GITHUB_MAIN_BRANCH}.tar.gz`,
      noCache: true,
      probe: {
        kind: "http",
      },
    });
  }

  if (repoGitUrl) {
    candidates.push({
      label: `HTTPS git checkout of ${GITHUB_MAIN_BRANCH}`,
      spec: `git+${repoGitUrl}@${GITHUB_MAIN_BRANCH}`,
      noCache: true,
      probe: {
        kind: "git",
        repoUrl: repoGitUrl,
        ref: GITHUB_MAIN_BRANCH,
        refNamespace: "heads",
      },
    });
  }

  return candidates;
}

function bootstrapProbeOverrides() {
  if (bootstrapProbeOverridesCache !== undefined) {
    return bootstrapProbeOverridesCache;
  }

  const raw = process.env[BOOTSTRAP_TEST_PROBES_ENV];
  if (!raw) {
    bootstrapProbeOverridesCache = {};
    return bootstrapProbeOverridesCache;
  }

  try {
    const parsed = JSON.parse(raw);
    bootstrapProbeOverridesCache = parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    warn(`Ignoring invalid ${BOOTSTRAP_TEST_PROBES_ENV} JSON.`);
    bootstrapProbeOverridesCache = {};
  }

  return bootstrapProbeOverridesCache;
}

function normalizeProbeStatus(value) {
  if (value === true) {
    return { status: "available", reason: "test override" };
  }
  if (value === false) {
    return { status: "unavailable", reason: "test override" };
  }
  if (value === null || value === "unknown") {
    return { status: "unknown", reason: "test override" };
  }
  if (value === "available" || value === "unavailable") {
    return { status: value, reason: "test override" };
  }
  if (typeof value === "object" && value !== null) {
    const status = value.status || value.availability;
    if (status === "available" || status === "unavailable" || status === "unknown") {
      return { status, reason: value.reason || "test override" };
    }
  }
  return null;
}

function probeOverrideForCandidate(candidate) {
  const overrides = bootstrapProbeOverrides();
  return normalizeProbeStatus(overrides[candidate.spec]);
}

function formatProbeReason(reason) {
  if (!reason) {
    return "";
  }
  const trimmedReason = reason.trim();
  if (!trimmedReason) {
    return "";
  }
  const normalizedReason = trimmedReason.replace(/[.?!]+$/u, "") || trimmedReason;
  return `: ${normalizedReason}`;
}

function probeHttpCandidate(urlString, redirectCount = 0) {
  return new Promise((resolve) => {
    let targetUrl;
    try {
      targetUrl = new URL(urlString);
    } catch (err) {
      resolve({ status: "unknown", reason: err.message });
      return;
    }

    const transport = targetUrl.protocol === "http:" ? http : https;
    const request = transport.request(
      targetUrl,
      {
        method: "HEAD",
        headers: {
          "User-Agent": `get-physics-done-bootstrap/${packageVersion}`,
        },
      },
      (response) => {
        const { statusCode = 0, headers } = response;
        response.resume();

        if ([301, 302, 303, 307, 308].includes(statusCode) && headers.location) {
          if (redirectCount >= INSTALL_CANDIDATE_PROBE_REDIRECT_LIMIT) {
            resolve({ status: "unknown", reason: "too many redirects" });
            return;
          }
          const nextUrl = new URL(headers.location, targetUrl).toString();
          resolve(probeHttpCandidate(nextUrl, redirectCount + 1));
          return;
        }

        if (statusCode >= 200 && statusCode < 400) {
          resolve({ status: "available", reason: `HTTP ${statusCode}` });
          return;
        }
        if (statusCode >= 400 && statusCode < 500) {
          resolve({ status: "unavailable", reason: `HTTP ${statusCode}` });
          return;
        }
        resolve({ status: "unknown", reason: `HTTP ${statusCode}` });
      }
    );

    request.on("error", (err) => {
      resolve({ status: "unknown", reason: err.message });
    });

    request.setTimeout(INSTALL_CANDIDATE_PROBE_TIMEOUT_MS, () => {
      request.destroy(new Error("timed out"));
    });

    request.end();
  });
}

function probeGitCandidate(repoUrl, ref, refNamespace) {
  const gitArgs = ["ls-remote", "--exit-code", refNamespace === "tags" ? "--tags" : "--heads", repoUrl, ref];
  const gitEnv = { ...process.env, GIT_TERMINAL_PROMPT: "0" };

  const result = spawnSync("git", gitArgs, {
    encoding: "utf-8",
    env: gitEnv,
    timeout: INSTALL_CANDIDATE_PROBE_TIMEOUT_MS,
  });

  if (result.error) {
    if (result.error.code === "ENOENT") {
      return { status: "unavailable", reason: "git is not installed" };
    }
    return { status: "unknown", reason: result.error.message };
  }
  if (result.status === 0) {
    return { status: "available", reason: "git ls-remote succeeded" };
  }

  const detail = (result.stderr || result.stdout || "").trim().split("\n")[0] || `git exit ${result.status}`;
  if (
    result.status === 2
    || /authentication failed|repository not found|access denied|not found|permission denied|could not read from remote repository/i.test(detail)
  ) {
    return { status: "unavailable", reason: detail };
  }

  return { status: "unknown", reason: detail };
}

async function probeInstallCandidate(candidate) {
  const override = probeOverrideForCandidate(candidate);
  if (override) {
    return override;
  }

  if (process.env[BOOTSTRAP_DISABLE_NETWORK_PROBES_ENV] === "1") {
    return { status: "unknown", reason: "network probes disabled" };
  }

  if (!candidate.probe) {
    return { status: "unknown", reason: "no preflight probe configured" };
  }
  if (candidate.probe.kind === "http") {
    return probeHttpCandidate(candidate.probe.url || candidate.spec);
  }
  if (candidate.probe.kind === "git") {
    return probeGitCandidate(candidate.probe.repoUrl, candidate.probe.ref, candidate.probe.refNamespace);
  }
  return { status: "unknown", reason: "unsupported preflight probe" };
}

async function resolveInstallCandidates(candidates) {
  const skipped = [];

  for (const [index, candidate] of candidates.entries()) {
    const probe = await probeInstallCandidate(candidate);
    if (probe.status === "unavailable") {
      skipped.push({ candidate, probe });
      continue;
    }
    return {
      candidates: [candidate, ...candidates.slice(index + 1)],
      skipped,
    };
  }

  return { candidates: [], skipped };
}

function logUnavailableCandidates(skipped) {
  for (const { candidate, probe } of skipped) {
    log(`Detected that ${candidate.label} is unavailable${formatProbeReason(probe.reason)}.`);
  }
}

function installFromCandidates(python, candidates, env, options = {}) {
  const { forceReinstall = false, firstAttemptMessage = null } = options;
  if (candidates.length === 0) {
    return { ok: false };
  }

  if (typeof firstAttemptMessage === "function") {
    const message = firstAttemptMessage(candidates[0]);
    if (message) {
      log(message);
    }
  }

  let installResult = runPipInstall(python, candidates[0].spec, env, {
    forceReinstall,
    noCache: candidates[0].noCache,
  });
  if (installResult.status === 0) {
    return { ok: true, installedFrom: candidates[0].spec };
  }
  flushCapturedOutput(installResult);

  for (const [index, candidate] of candidates.entries()) {
    if (index === 0) {
      continue;
    }
    const previousLabel = candidates[index - 1].label;
    log(`${previousLabel} failed. Falling back to ${candidate.label}...`);
    installResult = runPipInstall(python, candidate.spec, env, {
      forceReinstall,
      noCache: candidate.noCache,
    });
    if (installResult.status === 0) {
      return { ok: true, installedFrom: candidate.spec };
    }
    flushCapturedOutput(installResult);
  }

  return { ok: false };
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
    && (
      !isSupportedPython(existingManaged)
      || existingManaged.major > basePython.major
      || (existingManaged.major === basePython.major && existingManaged.minor > basePython.minor)
    )
  ) {
    log(
      `Recreating managed environment at ${venvDir} `
      + `(found ${existingManaged.text}; switching to ${basePython.text}).`
    );
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

async function installManagedPackage(python, pythonVersion, options = {}) {
  const { forceReinstall = false, preferMain = false, purpose = "install" } = options;
  const requestedVersion = pythonVersion;
  const pipInstallEnv = { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: "1" };

  if (preferMain) {
    const resolution = await resolveInstallCandidates(mainBranchInstallCandidates());
    const upgradeCandidates = resolution.candidates;
    if (upgradeCandidates.length > 0) {
      log(`Upgrading GPD from the latest GitHub ${GITHUB_MAIN_BRANCH} branch into the managed environment...`);
      logUnavailableCandidates(resolution.skipped);
      if (resolution.skipped.length > 0) {
        log(`Using ${upgradeCandidates[0].label} for the ${GITHUB_MAIN_BRANCH}-branch upgrade.`);
      }
      const installAttempt = installFromCandidates(python, upgradeCandidates, pipInstallEnv, {
        forceReinstall: true,
      });
      if (installAttempt.ok) {
        return { ok: true, requestedVersion, installedFrom: installAttempt.installedFrom };
      }

      log(`GitHub ${GITHUB_MAIN_BRANCH} upgrade failed across all main-branch candidates.`);
      return { ok: false, requestedVersion };
    } else if (resolution.skipped.length > 0) {
      logUnavailableCandidates(resolution.skipped);
      log(`No accessible GitHub ${GITHUB_MAIN_BRANCH} source candidate was detected for the upgrade.`);
      return { ok: false, requestedVersion };
    }
  }

  const action = purpose === "uninstall"
    ? "Preparing managed GPD CLI"
    : forceReinstall
      ? "Reinstalling GPD"
      : "Installing GPD";

  // 1. Try PyPI first — fast, reliable, no auth needed.
  const pypiSpec = `get-physics-done==${pythonVersion}`;
  log(`${action} from PyPI (${pypiSpec}) into the managed environment...`);
  const pypiResult = runPipInstall(python, pypiSpec, pipInstallEnv, { forceReinstall });
  if (pypiResult.status === 0) {
    return { ok: true, requestedVersion, installedFrom: pypiSpec };
  }
  flushCapturedOutput(pypiResult);
  log(`PyPI install failed. Falling back to GitHub source...`);

  // 2. Fall back to tagged GitHub release candidates.
  const resolution = await resolveInstallCandidates(releaseInstallCandidates(pythonVersion));
  const releaseCandidates = resolution.candidates;
  logUnavailableCandidates(resolution.skipped);

  if (releaseCandidates.length > 0) {
    const installAttempt = installFromCandidates(python, releaseCandidates, pipInstallEnv, {
      forceReinstall,
      firstAttemptMessage: (candidate) => `${action} from ${candidate.label} into the managed environment...`,
    });
    if (installAttempt.ok) {
      return { ok: true, requestedVersion, installedFrom: installAttempt.installedFrom };
    }
  } else if (resolution.skipped.length > 0) {
    log("No accessible tagged GitHub release source candidate was detected.");
  }

  return { ok: false, requestedVersion };
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
  const policy = runtimeRecord(runtime).global_config;
  if (policy.strategy === "env_or_home") {
    if (policy.env_var && process.env[policy.env_var]) {
      return expandTilde(process.env[policy.env_var]);
    }
    return path.join(os.homedir(), policy.home_subpath);
  }

  if (policy.strategy === "xdg_app") {
    if (policy.env_dir_var && process.env[policy.env_dir_var]) {
      return expandTilde(process.env[policy.env_dir_var]);
    }
    if (policy.env_file_var && process.env[policy.env_file_var]) {
      return path.dirname(expandTilde(process.env[policy.env_file_var]));
    }
    if (process.env.XDG_CONFIG_HOME && policy.xdg_subdir) {
      return path.join(expandTilde(process.env.XDG_CONFIG_HOME), policy.xdg_subdir);
    }
    return path.join(os.homedir(), policy.home_subpath);
  }

  throw new Error(`Unsupported config policy for runtime ${runtime}`);
}

function targetDirMatchesGlobal(runtime, targetDir) {
  const resolvedTargetDir = path.resolve(expandTilde(targetDir));
  const resolvedGlobalDir = path.resolve(expandTilde(runtimeGlobalConfigDir(runtime)));
  return resolvedTargetDir === resolvedGlobalDir;
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
  const names = runtimes.map((runtime) => runtimeDisplayName(runtime));
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

function formatLocationExample(runtimes, scope) {
  if (runtimes.length !== 1) {
    return "one config dir per runtime";
  }

  const runtime = runtimes[0];
  if (scope === "global") {
    return formatDisplayPath(runtimeGlobalConfigDir(runtime));
  }
  return `./${runtimeConfigDirName(runtime)}`;
}

function stripAnsi(text) {
  return String(text || "").replace(/\x1B\[[0-?]*[ -/]*[@-~]/g, "");
}

function parseJsonText(text) {
  const cleaned = stripAnsi(text).trim();
  if (!cleaned) {
    return null;
  }
  try {
    return JSON.parse(cleaned);
  } catch {
    return null;
  }
}

function shellQuote(arg) {
  const text = String(arg);
  if (text === "") {
    return "''";
  }
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(text)) {
    return text;
  }
  return `'${text.replace(/'/g, `'\\''`)}'`;
}

function formatShellCommand(argv) {
  return argv.map((arg) => shellQuote(arg)).join(" ");
}

function runtimeDoctorHint(runtime, scope, targetDir = null) {
  const parts = ["gpd", "doctor", "--runtime", runtime, `--${scope}`];
  if (targetDir) {
    parts.push("--target-dir", targetDir);
  }
  return formatShellCommand(parts);
}

function runtimePermissionsHint(action, runtime, autonomy = "balanced", targetDir = null) {
  const parts = ["gpd", "permissions", action, "--runtime", runtime, "--autonomy", autonomy];
  if (targetDir) {
    parts.push("--target-dir", targetDir);
  }
  return formatShellCommand(parts);
}

function runtimeUnattendedReadinessHint(runtime, autonomy = "balanced", targetDir = null) {
  const parts = ["gpd", "validate", "unattended-readiness", "--runtime", runtime, "--autonomy", autonomy];
  if (targetDir) {
    parts.push("--target-dir", targetDir);
  }
  return formatShellCommand(parts);
}

function buildRuntimeDoctorArgs(runtime, scope, targetDir = null) {
  const args = ["-m", "gpd.cli", "--raw", "doctor", "--runtime", runtime, `--${scope}`];
  if (targetDir) {
    args.push("--target-dir", targetDir);
  }
  return args;
}

function doctorCheckMessages(check, field) {
  if (!check || typeof check !== "object") {
    return [];
  }
  const messages = Array.isArray(check[field]) ? check[field] : [];
  const label = typeof check.label === "string" && check.label.trim() ? check.label.trim() : "Readiness Check";
  return messages
    .filter((message) => typeof message === "string" && message.trim())
    .map((message) => `${label}: ${message.trim()}`);
}

function collectDoctorAdvisories(report) {
  const advisories = [];
  const seen = new Set();
  const checks = Array.isArray(report && report.checks) ? report.checks : [];

  for (const check of checks) {
    for (const message of doctorCheckMessages(check, "warnings")) {
      if (!seen.has(message)) {
        seen.add(message);
        advisories.push(message);
      }
    }
    if ((check && check.status) === "warn") {
      for (const message of doctorCheckMessages(check, "issues")) {
        if (!seen.has(message)) {
          seen.add(message);
          advisories.push(message);
        }
      }
    }
  }

  return advisories;
}

function collectDoctorBlockers(report) {
  const blockers = [];
  const seen = new Set();
  const checks = Array.isArray(report && report.checks) ? report.checks : [];

  for (const check of checks) {
    if ((check && check.status) !== "fail") {
      continue;
    }
    const messages = [
      ...doctorCheckMessages(check, "issues"),
      ...doctorCheckMessages(check, "warnings"),
    ];
    if (messages.length === 0) {
      const label = typeof check.label === "string" && check.label.trim() ? check.label.trim() : "Readiness Check";
      messages.push(`${label}: readiness check failed.`);
    }
    for (const message of messages) {
      if (!seen.has(message)) {
        seen.add(message);
        blockers.push(message);
      }
    }
  }

  return blockers;
}

function extractDoctorErrorMessage(result) {
  const stderrJson = parseJsonText(result.stderr);
  if (stderrJson && typeof stderrJson.error === "string" && stderrJson.error.trim()) {
    return stderrJson.error.trim();
  }

  const stdoutJson = parseJsonText(result.stdout);
  if (stdoutJson && typeof stdoutJson.error === "string" && stdoutJson.error.trim()) {
    return stdoutJson.error.trim();
  }

  const stderrText = stripAnsi(result.stderr).trim();
  if (stderrText) {
    return stderrText;
  }

  const stdoutText = stripAnsi(result.stdout).trim();
  if (stdoutText) {
    return stdoutText;
  }

  return `managed doctor exited with status ${result.status}`;
}

function runManagedDoctorReadinessCheck(managedPython, runtime, scope, targetDir = null) {
  const result = spawnSync(managedPython, buildRuntimeDoctorArgs(runtime, scope, targetDir), {
    encoding: "utf-8",
    env: process.env,
  });

  if (result.error) {
    return {
      ok: false,
      errorMessage: result.error.message,
    };
  }

  if (result.status !== 0) {
    return {
      ok: false,
      errorMessage: extractDoctorErrorMessage(result),
    };
  }

  const report = parseJsonText(result.stdout);
  if (!report || typeof report !== "object" || !Array.isArray(report.checks)) {
    return {
      ok: false,
      errorMessage: "managed doctor did not return a valid readiness report.",
    };
  }

  return {
    ok: true,
    report,
  };
}

function runInstallReadinessPreflight(managedPython, runtimes, scope, targetDir = null) {
  console.log(` ${bold}${brandTitle}Runtime launcher/target preflight${reset}`);
  console.log("");

  const blockers = [];

  for (const runtime of runtimes) {
    const displayName = runtimeDisplayName(runtime);
    const doctorCheck = runManagedDoctorReadinessCheck(managedPython, runtime, scope, targetDir);
    if (!doctorCheck.ok) {
      blockers.push(`${displayName}: ${doctorCheck.errorMessage}`);
      continue;
    }

    const report = doctorCheck.report;
    const reportBlockers = collectDoctorBlockers(report);
    if (reportBlockers.length > 0 || report.overall === "fail") {
      const messages = reportBlockers.length > 0
        ? reportBlockers
        : ["Runtime readiness reported a failure without blocking details."];
      blockers.push(...messages.map((message) => `${displayName}: ${message}`));
      continue;
    }

    const advisories = collectDoctorAdvisories(report);
    success(`${displayName}: launcher/target preflight passed${advisories.length > 0 ? " with advisories" : ""}.`);
    advisories.forEach((message) => warn(`${displayName}: ${message}`));
  }

  if (blockers.length > 0) {
    console.log("");
    error("Runtime launcher/target preflight failed.");
    [...new Set(blockers)].forEach((message) => error(message));
    const doctorHints = runtimes.map((runtime) => `\`${runtimeDoctorHint(runtime, scope, targetDir)}\``).join(", ");
    log(`Fix the blocking readiness issue(s) above, then rerun the bootstrap installer. Inspect directly with ${doctorHints}.`);
    return false;
  }

  console.log("");
  success(`Runtime launcher/target preflight passed for ${formatRuntimeList(runtimes)}.`);
  const doctorHints = runtimes.map((runtime) => `\`${runtimeDoctorHint(runtime, scope, targetDir)}\``).join(", ");
  log(`For the full runtime-target doctor report after install, use ${doctorHints}.`);
  log("Use `gpd doctor` for install and runtime-local readiness, `gpd validate unattended-readiness` for the unattended or overnight verdict, and `gpd permissions ...` for runtime-owned permission alignment and sync.");
  log(
    "Workflow presets: if you plan paper/manuscript workflows, rerun "
    + `${doctorHints} after install and check whether \`Workflow Presets\` is \`ready\` or \`degraded\`. `
    + "Without LaTeX, the paper/manuscript and full research presets remain usable for `write-paper` and `peer-review`, but `paper-build` and "
    + "`arxiv-submission` require the `LaTeX Toolchain`."
  );
  console.log("");
  return true;
}

function printUnattendedConfigurationReminder(runtimes, targetDir = null) {
  console.log("");
  console.log(` ${bold}${brandTitle}Unattended configuration${reset}`);
  console.log("");
  log("Recommended unattended default: Balanced autonomy (`balanced`).");
  if (runtimes.length === 1) {
    const runtime = runtimes[0];
    log(
      `Inside ${runtimeDisplayName(runtime)}, use \`${runtimeSurfaceCommand(runtime, "settings")}\` `
      + settingsCommandTail()
    );
    log(SHARED_PUBLIC_SURFACE_TEXT.settingsRecommendationSentence);
    log(`Check the unattended or overnight verdict with \`${runtimeUnattendedReadinessHint(runtime, "balanced", targetDir)}\`.`);
    log(`If it reports \`not-ready\`, run \`${runtimePermissionsHint("sync", runtime, "balanced", targetDir)}\`.`);
    warn("If it reports `relaunch-required`, the runtime is not ready for unattended use until you exit and relaunch it.");
  } else {
    log(`Inside each runtime, use \`settings\` ${settingsCommandTail()}`);
    log(SHARED_PUBLIC_SURFACE_TEXT.settingsRecommendationSentence);
    for (const runtime of runtimes) {
      log(
        `${runtimeDisplayName(runtime)}: \`${runtimeSurfaceCommand(runtime, "settings")}\`, then `
        + `\`${runtimeUnattendedReadinessHint(runtime)}\`.`
      );
    }
    log("If any runtime reports `not-ready`, rerun the matching `gpd permissions sync --runtime <runtime> --autonomy balanced` command.");
    warn("If any runtime reports `relaunch-required`, treat its unattended readiness as not ready until that runtime is relaunched.");
  }
  console.log("");
}

function formatMenuOption(index, label, details = [], options = {}) {
  const { labelWidth = label.length } = options;
  const filteredDetails = details.filter(Boolean);
  const detailText = filteredDetails.length === 0
    ? ""
    : `  ${filteredDetails.map((detail) => `${bold}${brandAccent}·${reset} ${dim}${brandMeta}${detail}${reset}`).join(" ")}`;
  return ` ${bold}${brandAccent}[${index}]${reset} ${bold}${brandTitle}${label.padEnd(labelWidth, " ")}${reset}${detailText}`;
}

function documentedRuntimeFlags() {
  return RUNTIME_CATALOG.flatMap((runtime) => runtimeSelectionFlagList(runtime.runtime_name));
}

function findRuntime(predicate, fallback = ALL_RUNTIMES[0]) {
  const match = RUNTIME_CATALOG.find(predicate);
  return match ? match.runtime_name : fallback;
}

function printBanner() {
  console.log("");
  console.log(`${bold}${brandLogo} ██████╗ ██████╗ ██████╗${reset}`);
  console.log(`${bold}${brandLogo}██╔════╝ ██╔══██╗██╔══██╗${reset}`);
  console.log(`${bold}${brandLogo}██║  ███╗██████╔╝██║  ██║${reset}`);
  console.log(`${bold}${brandLogo}██║   ██║██╔═══╝ ██║  ██║${reset}`);
  console.log(`${bold}${brandLogo}╚██████╔╝██║     ██████╔╝${reset}`);
  console.log(`${bold}${brandLogo} ╚═════╝ ╚═╝     ╚═════╝${reset}`);
  console.log("");
  console.log(` ${bold}${brandTitle}GPD v${packageVersion} - ${brandDisplayName}${reset}`);
  console.log(` ${dim}${brandMeta}© ${brandCopyrightYear} ${brandOwner} (${brandOwnerShort})${reset}`);
  console.log("");
}

function printHelp() {
  const installCommand = "npx -y get-physics-done";
  const primaryRuntime = ALL_RUNTIMES[0];
  const dollarCommandRuntime = findRuntime((runtime) => runtime.command_prefix.startsWith("$"), primaryRuntime);
  const primaryFlag = runtimeInstallFlag(primaryRuntime);
  const dollarCommandFlag = runtimeInstallFlag(dollarCommandRuntime);
  const targetDirExample = `/path/to/${runtimeConfigDirName(dollarCommandRuntime)}`;
  const repoBaseUrl = repositoryBaseUrl(repository) || "https://github.com/psi-oss/get-physics-done";
  const beginnerOnboardingHubUrl = `${repoBaseUrl}/blob/main/docs/README.md`;
  console.log(` ${yellow}Usage:${reset} ${installCommand} [install|uninstall] [options]`);
  console.log("");
  console.log(` ${dim}${productPositioning}${reset}`);
  console.log("");
  console.log(` ${yellow}Options:${reset}`);
  console.log(` ${cyan}-l, --local${reset}             Use the current project only`);
  console.log(` ${cyan}-g, --global${reset}            Use the global runtime config dir`);
  console.log(` ${cyan}--uninstall${reset}             Uninstall from selected runtime config`);
  console.log(` ${cyan}--reinstall${reset}             Reinstall the matching tagged GitHub source in ~/GPD/venv`);
  console.log(` ${cyan}--upgrade${reset}               Upgrade ~/GPD/venv from the latest GitHub main source`);
  for (const runtime of ALL_RUNTIMES) {
    const flags = runtimeSelectionFlagList(runtime).join(", ");
    const padding = " ".repeat(Math.max(0, 24 - flags.length));
    console.log(` ${cyan}${flags}${reset}${padding}Select ${runtimeDisplayName(runtime)} only`);
  }
  console.log(` ${cyan}--all${reset}                  Select all supported runtimes`);
  console.log(` ${cyan}--target-dir <path>${reset}    Override the runtime config directory (defaults to local scope unless it resolves to the runtime's canonical global config dir)`);
  console.log(` ${cyan}--force-statusline${reset}     Replace an existing runtime statusline`);
  console.log(` ${cyan}-h, --help${reset}              Show this help message`);
  console.log("");
  console.log(` ${yellow}Examples:${reset}`);
  console.log(` ${dim}# Interactive install${reset}`);
  console.log(` ${installCommand}`);
  console.log("");
  console.log(` ${dim}# Install for ${runtimeDisplayName(primaryRuntime)} globally${reset}`);
  console.log(` ${installCommand} ${primaryFlag} --global`);
  console.log("");
  console.log(` ${dim}# Install for ${runtimeDisplayName(dollarCommandRuntime)} locally${reset}`);
  console.log(` ${installCommand} ${dollarCommandFlag} --local`);
  console.log("");
  console.log(` ${dim}# Reinstall the matching managed GitHub source${reset}`);
  console.log(` ${installCommand} --reinstall ${primaryFlag} --local`);
  console.log("");
  console.log(` ${dim}# Upgrade to the latest GitHub main source${reset}`);
  console.log(` ${installCommand} --upgrade ${primaryFlag} --local`);
  console.log("");
  console.log(` ${dim}# Install for all runtimes globally${reset}`);
  console.log(` ${installCommand} --all --global`);
  console.log("");
  console.log(` ${dim}# Install into an explicit local target directory${reset}`);
  console.log(` ${installCommand} ${dollarCommandFlag} --local --target-dir ${targetDirExample}`);
  console.log("");
  console.log(` ${dim}# Interactive uninstall${reset}`);
  console.log(` ${installCommand} --uninstall`);
  console.log("");
  console.log(` ${dim}# Uninstall from ${runtimeDisplayName(primaryRuntime)} globally${reset}`);
  console.log(` ${installCommand} --uninstall ${primaryFlag} --global`);
  console.log("");
  console.log(` ${dim}# Uninstall from all runtimes globally${reset}`);
  console.log(` ${installCommand} --uninstall --all --global`);
  console.log("");
  console.log(` ${dim}# Equivalent uninstall subcommand form${reset}`);
  console.log(` ${installCommand} uninstall ${primaryRuntime} --local`);
  console.log("");
  console.log(` ${yellow}After install:${reset}`);
  console.log(` ${dim}# Recommended unattended configuration${reset}`);
  console.log(" Bootstrap preflight checks runtime launcher/target blockers only; configure unattended behavior after startup.");
  console.log(` Beginner Onboarding Hub: ${beginnerOnboardingHubUrl}`);
  console.log(" Open your runtime, run its help command first, then use `start` if you are not sure what fits this folder. Use `tour` for a read-only walkthrough first. Then use your runtime's `new-project` command for new work or `map-research` for existing work.");
  console.log(` Recommended unattended default: Balanced autonomy (\`balanced\`). ${SHARED_PUBLIC_SURFACE_TEXT.settingsRecommendationSentence}`);
  console.log(` Use the runtime-specific \`settings\` command after startup ${settingsCommandTail()}`);
  console.log(
    " For returning work, use `gpd resume` for the current-workspace read-only recovery snapshot. "
    + "If that is the wrong workspace, use `gpd resume --recent` to find the workspace first, then continue inside that workspace with your runtime-specific `resume-work` command. "
    + "After resuming, your runtime-specific `suggest-next` command is the fastest next command. "
    + "Before stepping away mid-phase, run your runtime-specific `pause-work` command so that ladder has an explicit handoff to restore."
  );
  console.log(
    " Workflow presets: if you plan paper/manuscript workflows, rerun `gpd doctor --runtime <runtime> --local|--global` "
    + "and check whether `Workflow Presets` is `ready` or `degraded`. Without LaTeX, the paper/manuscript and full research presets remain usable for `write-paper` and `peer-review`, "
    + "but `paper-build` and `arxiv-submission` require the `LaTeX Toolchain`."
  );
  console.log(" Then run `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced`.");
  console.log(" If it reports `not-ready`, run `gpd permissions sync --runtime <runtime> --autonomy balanced`.");
  console.log(" If it reports `relaunch-required`, exit and relaunch the runtime before unattended use.");
  console.log("");
}

function parseTargetDirArg(args) {
  const inline = args.find((arg) => arg.startsWith("--target-dir="));
  if (inline) {
    const value = inline.slice("--target-dir=".length).trim();
    if (!value) {
      error("Missing value for --target-dir.");
      process.exit(1);
    }
    return value;
  }

  const index = args.indexOf("--target-dir");
  if (index === -1) {
    return null;
  }

  const value = args[index + 1];
  if (!value || value.startsWith("-")) {
    error("Missing value for --target-dir.");
    process.exit(1);
  }
  return value;
}

function runtimeTokenFlagMap() {
  const mapping = new Map();
  for (const runtime of ALL_RUNTIMES) {
    const aliases = new Set([
      runtime,
      runtimeDisplayName(runtime).toLowerCase(),
      ...runtimeSelectionAliases(runtime),
      ...runtimeSelectionFlagList(runtime).map((flag) => flag.replace(/^--/, "")),
    ]);
    for (const alias of aliases) {
      mapping.set(alias.toLowerCase(), runtimeInstallFlag(runtime));
    }
  }
  return mapping;
}

function normalizeBootstrapArgs(args) {
  if (args.length === 0) {
    return [];
  }

  const normalized = [];
  const firstArg = String(args[0]).toLowerCase();
  const usesSubcommandSyntax = firstArg === "install" || firstArg === "uninstall";
  const runtimeFlagsByToken = runtimeTokenFlagMap();
  let index = usesSubcommandSyntax ? 1 : 0;

  if (firstArg === "uninstall" && !args.includes("--uninstall")) {
    normalized.push("--uninstall");
  }

  while (index < args.length) {
    const arg = args[index];
    if (arg === "--target-dir") {
      normalized.push(arg);
      if (index + 1 < args.length) {
        normalized.push(args[index + 1]);
      }
      index += 2;
      continue;
    }
    if (typeof arg === "string" && arg.startsWith("--target-dir=")) {
      normalized.push(arg);
      index += 1;
      continue;
    }
    if (usesSubcommandSyntax && typeof arg === "string" && !arg.startsWith("-")) {
      const bareToken = arg.trim().toLowerCase();
      if (bareToken === "all") {
        normalized.push("--all");
        index += 1;
        continue;
      }
      const runtimeFlag = runtimeFlagsByToken.get(bareToken);
      if (runtimeFlag) {
        normalized.push(runtimeFlag);
        index += 1;
        continue;
      }
    }
    normalized.push(arg);
    index += 1;
  }

  return normalized;
}

function parseSelectedRuntimes(args) {
  const selected = [];
  const seen = new Set();

  if (args.includes("--all")) {
    return [...ALL_RUNTIMES];
  }

  for (const runtime of ALL_RUNTIMES) {
    const flags = runtimeSelectionFlagList(runtime);
    if (flags.some((flag) => args.includes(flag)) && !seen.has(runtime)) {
      selected.push(runtime);
      seen.add(runtime);
    }
  }

  return selected;
}

async function selectRuntimes(args, action = "install") {
  const selected = parseSelectedRuntimes(args);
  if (selected.length > 0) {
    return selected;
  }

  if (!process.stdin.isTTY) {
    const mode = action === "uninstall" ? "--uninstall " : "";
    error(
      `Specify a runtime with ${documentedRuntimeFlags().join("/")} or use --all when running ${mode}non-interactively.`
    );
    process.exit(1);
  }

  const optionLabelWidth = Math.max(
    ...ALL_RUNTIMES.map((runtime) => runtimeDisplayName(runtime).length),
    "All runtimes".length
  );
  const sectionTitle = action === "uninstall" ? "Select runtime(s) to uninstall" : "Select runtime(s) to install";
  console.log(` ${bold}${brandTitle}${sectionTitle}${reset}`);
  console.log("");
  ALL_RUNTIMES.forEach((runtime, index) => {
    console.log(formatMenuOption(index + 1, runtimeDisplayName(runtime), [runtime], { labelWidth: optionLabelWidth }));
  });
  console.log(formatMenuOption(ALL_RUNTIMES.length + 1, "All runtimes", [], { labelWidth: optionLabelWidth }));
  console.log("");

  const choice = ((await prompt(` ${bold}${brandTitle}Enter choice${reset} ${dim}[1]${reset}: `)) || "1").toLowerCase();
  if (choice === String(ALL_RUNTIMES.length + 1) || choice === "all" || choice === "all runtimes") {
    return [...ALL_RUNTIMES];
  }

  const numericIndex = Number.parseInt(choice, 10);
  if (Number.isInteger(numericIndex) && numericIndex >= 1 && numericIndex <= ALL_RUNTIMES.length) {
    return [ALL_RUNTIMES[numericIndex - 1]];
  }

  for (const runtime of ALL_RUNTIMES) {
    const aliases = new Set([runtime, runtimeDisplayName(runtime).toLowerCase(), ...runtimeSelectionAliases(runtime)]);
    if (aliases.has(choice)) {
      return [runtime];
    }
  }

  error(`Invalid runtime selection: ${choice}`);
  process.exit(1);
}

async function selectInstallScope(args, runtimes, targetDir, action = "install") {
  if (targetDir) {
    if (args.includes("--global") || args.includes("-g")) {
      return "global";
    }
    if (args.includes("--local") || args.includes("-l")) {
      return "local";
    }
    return targetDirMatchesGlobal(runtimes[0], targetDir) ? "global" : "local";
  }
  if (args.includes("--global") || args.includes("-g")) {
    return "global";
  }
  if (args.includes("--local") || args.includes("-l")) {
    return "local";
  }

  if (!process.stdin.isTTY) {
    const mode = action === "uninstall" ? "--uninstall " : "";
    error(`Specify --global or --local when running ${mode}non-interactively.`);
    process.exit(1);
  }

  const globalExample = formatLocationExample(runtimes, "global");
  const localExample = formatLocationExample(runtimes, "local");
  const optionLabelWidth = Math.max("Local".length, "Global".length);
  const sectionTitle = action === "uninstall" ? "Uninstall location" : "Install location";

  console.log(` ${bold}${brandTitle}${sectionTitle}${reset}`);
  console.log("");
  console.log(formatMenuOption(1, "Local", ["current project only", localExample], { labelWidth: optionLabelWidth }));
  console.log(formatMenuOption(2, "Global", ["all projects", globalExample], { labelWidth: optionLabelWidth }));
  console.log("");

  const choice = ((await prompt(` ${bold}${brandTitle}Enter choice${reset} ${dim}[1]${reset}: `)) || "1").toLowerCase();
  if (choice === "1" || choice === "local") {
    return "local";
  }
  if (choice === "2" || choice === "global") {
    return "global";
  }

  error(`Invalid location selection: ${choice}`);
  process.exit(1);
}

function buildRuntimeCommandArgs(command, runtimes, scope, targetDir = null, options = {}) {
  const { forceStatusline = false } = options;
  const cliArgs = ["-m", "gpd.cli", command];
  if (runtimes.length === ALL_RUNTIMES.length) {
    cliArgs.push("--all");
  } else {
    cliArgs.push(...runtimes);
  }
  cliArgs.push(`--${scope}`);
  if (targetDir) {
    cliArgs.push("--target-dir", targetDir);
  }
  if (forceStatusline && command === "install") {
    cliArgs.push("--force-statusline");
  }
  return cliArgs;
}

async function main() {
  const args = normalizeBootstrapArgs(process.argv.slice(2));
  const hasHelp = args.includes("--help") || args.includes("-h");
  const isUninstall = args.includes("--uninstall");
  const forceStatusline = args.includes("--force-statusline");
  const reinstallManagedPackage = args.includes("--reinstall");
  const upgradeManagedPackage = args.includes("--upgrade");
  const targetDir = parseTargetDirArg(args);
  const parsedRuntimes = parseSelectedRuntimes(args);

  printBanner();

  if (hasHelp) {
    printHelp();
    return;
  }

  if (!pythonPackageVersion) {
    error("Bootstrap package is missing its companion Python release metadata.");
    process.exit(1);
  }

  if ((args.includes("--global") || args.includes("-g")) && (args.includes("--local") || args.includes("-l"))) {
    error("Cannot specify both --global and --local.");
    process.exit(1);
  }
  if (isUninstall && reinstallManagedPackage) {
    error("Cannot combine --uninstall with --reinstall.");
    process.exit(1);
  }
  if (isUninstall && upgradeManagedPackage) {
    error("Cannot combine --uninstall with --upgrade.");
    process.exit(1);
  }
  if (reinstallManagedPackage && upgradeManagedPackage) {
    error("Cannot combine --reinstall with --upgrade.");
    process.exit(1);
  }
  if (isUninstall && forceStatusline) {
    error("Cannot combine --uninstall with --force-statusline.");
    process.exit(1);
  }
  if (targetDir && parsedRuntimes.length === 0 && !process.stdin.isTTY) {
    error(`Specify exactly one runtime with ${documentedRuntimeFlags().join("/")} when using --target-dir non-interactively.`);
    process.exit(1);
  }

  const action = isUninstall ? "uninstall" : "install";
  const selectedRuntimes = await selectRuntimes(args, action);
  if (targetDir && selectedRuntimes.length !== 1) {
    error("Cannot combine --target-dir with --all or multiple runtimes. Select exactly one runtime.");
    process.exit(1);
  }
  const scope = await selectInstallScope(args, selectedRuntimes, targetDir, action);

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

  const packageInstall = await installManagedPackage(managedEnv.python, pythonPackageVersion, {
    forceReinstall: reinstallManagedPackage || upgradeManagedPackage,
    preferMain: upgradeManagedPackage,
    purpose: isUninstall ? "uninstall" : "install",
  });
  if (!packageInstall.ok) {
    error(`Failed to install GPD v${packageInstall.requestedVersion} from GitHub sources.`);
    process.exit(1);
  }

  if (!isUninstall) {
    const readinessOk = runInstallReadinessPreflight(managedEnv.python, selectedRuntimes, scope, targetDir);
    if (!readinessOk) {
      process.exit(1);
    }
  }

  if (isUninstall) {
    log(`Uninstalling GPD from ${formatRuntimeList(selectedRuntimes)} (${scope})...`);
  }

  const cliArgs = buildRuntimeCommandArgs(action, selectedRuntimes, scope, targetDir, { forceStatusline });

  // Run the installer/uninstaller through the managed Python interpreter.
  const result = spawnSync(managedEnv.python, cliArgs, {
    stdio: "inherit",
    env: process.env,
  });

  if (result.status === 0) {
    if (!isUninstall) {
      printUnattendedConfigurationReminder(selectedRuntimes, targetDir);
    }
    return;
  } else {
    error(`${isUninstall ? "Uninstall" : "Installation"} failed. Check the output above for details.`);
    process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
