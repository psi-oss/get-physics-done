#!/usr/bin/env node
/**
 * GPD bootstrap installer — installs or uninstalls Get Physics Done.
 *
 * Usage:
 *   npx -y get-physics-done@latest
 *   npx -y get-physics-done@latest --<runtime-flag> --global
 *   npx -y get-physics-done@latest --<runtime-flag> --local
 *   npx -y get-physics-done@latest --all --global
 *   npx -y get-physics-done@latest --uninstall
 *   npx -y get-physics-done@latest --uninstall --<runtime-flag> --global
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

const PYTHON_PACKAGE_NAME = "get-physics-done";
const pythonPackageVersion = typeof rawPythonPackageVersion === "string" ? rawPythonPackageVersion.trim() : "";
const GPD_HOME_ENV = "GPD_HOME";
const GPD_HOME_DIRNAME = ".gpd";
const GITHUB_FALLBACK_BRANCH = "main";
const BOOTSTRAP_TEST_PROBES_ENV = "GPD_BOOTSTRAP_TEST_PROBES";
const BOOTSTRAP_DISABLE_NETWORK_PROBES_ENV = "GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES";
const PYPI_RELEASE_PROBE_BASE_URL = "https://pypi.org/pypi";
const INSTALL_CANDIDATE_PROBE_TIMEOUT_MS = 5000;
const INSTALL_CANDIDATE_PROBE_REDIRECT_LIMIT = 5;

const red = "\x1b[31m";
const green = "\x1b[32m";
const yellow = "\x1b[33m";
const cyan = "\x1b[36m";
const dim = "\x1b[2m";
const bold = "\x1b[1m";
const reset = "\x1b[0m";

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

function runtimeSelectionAliases(runtime) {
  return runtimeRecord(runtime).selection_aliases || [];
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
        probe: {
          kind: "http",
        },
      },
      {
        label: `current ${GITHUB_FALLBACK_BRANCH} branch source archive`,
        spec: `${repoBaseUrl}/archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz`,
        noCache: true,
        probe: {
          kind: "http",
        },
      }
    );
  }

  // SSH git candidates first — uses existing SSH keys without prompting for credentials.
  if (repoSshUrl) {
    candidates.push(
      {
        label: `SSH git checkout for v${version}`,
        spec: `git+${repoSshUrl}@v${version}`,
        probe: {
          kind: "git",
          repoUrl: repoSshUrl,
          ref: `v${version}`,
          refNamespace: "tags",
        },
      },
      {
        label: `SSH git checkout of ${GITHUB_FALLBACK_BRANCH}`,
        spec: `git+${repoSshUrl}@${GITHUB_FALLBACK_BRANCH}`,
        noCache: true,
        probe: {
          kind: "git",
          repoUrl: repoSshUrl,
          ref: GITHUB_FALLBACK_BRANCH,
          refNamespace: "heads",
        },
      }
    );
  }

  // HTTPS git candidates last — may prompt for username/password if no credential helper.
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
      },
      {
        label: `HTTPS git checkout of ${GITHUB_FALLBACK_BRANCH}`,
        spec: `git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}`,
        noCache: true,
        probe: {
          kind: "git",
          repoUrl: repoGitUrl,
          ref: GITHUB_FALLBACK_BRANCH,
          refNamespace: "heads",
        },
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
      probe: {
        kind: "http",
      },
    });
  }

  if (repoSshUrl) {
    candidates.push({
      label: `SSH git checkout of ${GITHUB_FALLBACK_BRANCH}`,
      spec: `git+${repoSshUrl}@${GITHUB_FALLBACK_BRANCH}`,
      noCache: true,
      probe: {
        kind: "git",
        repoUrl: repoSshUrl,
        ref: GITHUB_FALLBACK_BRANCH,
        refNamespace: "heads",
      },
    });
  }

  if (repoGitUrl) {
    candidates.push({
      label: `HTTPS git checkout of ${GITHUB_FALLBACK_BRANCH}`,
      spec: `git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}`,
      noCache: true,
      probe: {
        kind: "git",
        repoUrl: repoGitUrl,
        ref: GITHUB_FALLBACK_BRANCH,
        refNamespace: "heads",
      },
    });
  }

  return candidates;
}

function matchingPythonReleaseInstallCandidate(version) {
  const spec = `${PYTHON_PACKAGE_NAME}==${version}`;
  return {
    label: `PyPI release ${spec}`,
    spec,
    probe: {
      kind: "http",
      url: `${PYPI_RELEASE_PROBE_BASE_URL}/${encodeURIComponent(PYTHON_PACKAGE_NAME)}/${encodeURIComponent(version)}/json`,
    },
  };
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
  return reason ? ` (${reason})` : "";
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
  if (repoUrl.startsWith("ssh://") && !gitEnv.GIT_SSH_COMMAND) {
    gitEnv.GIT_SSH_COMMAND = "ssh -o BatchMode=yes -o ConnectTimeout=5";
  }

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

  // All probes said "unavailable" — but probes can be wrong for private repos
  // (e.g., unauthenticated HTTP HEAD returns 404, but pip with credential helper
  // can still clone). Return all candidates so the actual install is attempted.
  if (skipped.length > 0) {
    return { candidates: skipped.map(({ candidate }) => candidate), skipped };
  }

  return { candidates: [], skipped };
}

function logUnavailableCandidates(skipped) {
  for (const { candidate, probe } of skipped) {
    log(`Detected that ${candidate.label} is unavailable${formatProbeReason(probe.reason)}.`);
  }
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

async function installManagedPackage(python, pythonVersion, options = {}) {
  const { forceReinstall = false, preferMain = false } = options;
  const pypiCandidate = matchingPythonReleaseInstallCandidate(pythonVersion);
  const pythonPackageSpec = pypiCandidate.spec;
  const pipInstallEnv = { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: "1" };

  if (preferMain) {
    const resolution = await resolveInstallCandidates(latestMainInstallCandidates());
    const upgradeCandidates = resolution.candidates;
    if (upgradeCandidates.length > 0) {
      log(`Upgrading GPD from the latest GitHub ${GITHUB_FALLBACK_BRANCH} branch into the managed environment...`);
      logUnavailableCandidates(resolution.skipped);
      if (resolution.skipped.length > 0) {
        log(`Using ${upgradeCandidates[0].label} for the ${GITHUB_FALLBACK_BRANCH}-branch upgrade.`);
      }
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
    } else if (resolution.skipped.length > 0) {
      logUnavailableCandidates(resolution.skipped);
      log(`No accessible GitHub ${GITHUB_FALLBACK_BRANCH} source candidate was detected. Falling back to the matching ${pythonPackageSpec} release...`);
    }
  }

  const action = forceReinstall ? "Reinstalling" : "Installing";

  // Try GitHub source candidates first (SSH then HTTPS).
  const resolution = await resolveInstallCandidates(sourceInstallCandidates(pythonVersion));
  const sourceCandidates = resolution.candidates;
  logUnavailableCandidates(resolution.skipped);

  let installResult = null;
  if (sourceCandidates.length > 0) {
    log(`${action} GPD from ${sourceCandidates[0].label} into the managed environment...`);
    installResult = runPipInstall(python, sourceCandidates[0].spec, pipInstallEnv, {
      forceReinstall,
      noCache: sourceCandidates[0].noCache,
    });
    if (installResult.status === 0) {
      return { ok: true, pythonPackageSpec, installedFrom: sourceCandidates[0].spec };
    }
    flushCapturedOutput(installResult);

    for (const [index, candidate] of sourceCandidates.entries()) {
      if (index === 0) {
        continue;
      }
      const previousLabel = sourceCandidates[index - 1].label;
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
  }

  // Final fallback: PyPI (if the package is published there).
  const pypiProbe = await probeInstallCandidate(pypiCandidate);
  if (pypiProbe.status !== "unavailable") {
    log(`GitHub source failed. Trying PyPI ${pythonPackageSpec}...`);
    installResult = runPipInstall(python, pythonPackageSpec, pipInstallEnv, {
      forceReinstall,
    });
    if (installResult.status === 0) {
      return { ok: true, pythonPackageSpec };
    }
    flushCapturedOutput(installResult);
  } else {
    logUnavailableCandidates([{ candidate: pypiCandidate, probe: pypiProbe }]);
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

function runtimeCommandPrefix(runtime) {
  return runtimeRecord(runtime).command_prefix;
}

function formatRuntimeCommand(runtime, action) {
  const prefix = runtimeCommandPrefix(runtime);
  return `${prefix}${action}`;
}

function documentedRuntimeFlags() {
  return RUNTIME_CATALOG.map((runtime) => runtime.install_flag);
}

function findRuntime(predicate, fallback = ALL_RUNTIMES[0]) {
  const match = RUNTIME_CATALOG.find(predicate);
  return match ? match.runtime_name : fallback;
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
  console.log(` for ${formatRuntimeList(ALL_RUNTIMES)}.`);
  console.log("");
}

function printHelp() {
  const installCommand = "npx -y get-physics-done@latest";
  const primaryRuntime = ALL_RUNTIMES[0];
  const dollarCommandRuntime = findRuntime((runtime) => runtime.command_prefix.startsWith("$"), primaryRuntime);
  const primaryFlag = runtimeInstallFlag(primaryRuntime);
  const dollarCommandFlag = runtimeInstallFlag(dollarCommandRuntime);
  const targetDirExample = `/path/to/${runtimeConfigDirName(dollarCommandRuntime)}`;
  console.log(` ${yellow}Usage:${reset} ${installCommand} [options]`);
  console.log("");
  console.log(` ${yellow}Options:${reset}`);
  console.log(` ${cyan}-g, --global${reset}            Use the global runtime config dir`);
  console.log(` ${cyan}-l, --local${reset}             Use the current project only`);
  console.log(` ${cyan}--uninstall${reset}             Uninstall from selected runtime config`);
  console.log(` ${cyan}--reinstall${reset}             Reinstall the matching Python release in ~/.gpd/venv`);
  console.log(` ${cyan}--upgrade${reset}               Upgrade ~/.gpd/venv from the latest GitHub main source`);
  for (const runtime of ALL_RUNTIMES) {
    const flag = runtimeInstallFlag(runtime);
    const padding = " ".repeat(Math.max(0, 24 - flag.length));
    console.log(` ${cyan}${flag}${reset}${padding}Select ${runtimeDisplayName(runtime)} only`);
  }
  console.log(` ${cyan}--all${reset}                  Select all supported runtimes`);
  console.log(` ${cyan}--target-dir <path>${reset}    Override the runtime config directory (implies local scope)`);
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
  console.log(` ${dim}# Reinstall the matching managed Python release${reset}`);
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

function parseSelectedRuntimes(args) {
  const selected = [];
  const seen = new Set();

  if (args.includes("--all")) {
    return [...ALL_RUNTIMES];
  }

  for (const runtime of ALL_RUNTIMES) {
    const flags = new Set([`--${runtime}`, ...runtimeSelectionFlags(runtime)]);
    if ([...flags].some((flag) => args.includes(flag)) && !seen.has(runtime)) {
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
    if (action === "uninstall") {
      error(`Specify a runtime with ${documentedRuntimeFlags().join("/")} or use --all when running --uninstall non-interactively.`);
      process.exit(1);
    }
    const defaultRuntime = ALL_RUNTIMES[0];
    warn(`Non-interactive terminal detected, defaulting to ${runtimeDisplayName(defaultRuntime)}.`);
    return [defaultRuntime];
  }

  const actionPrompt = action === "uninstall" ? "uninstall from" : "install for";
  console.log(` ${yellow}Which runtime(s) would you like to ${actionPrompt}?${reset}`);
  console.log("");
  ALL_RUNTIMES.forEach((runtime, index) => {
    console.log(
      ` ${cyan}${index + 1}${reset}) ${runtimeDisplayName(runtime)} ${dim}(${formatDisplayPath(runtimeGlobalConfigDir(runtime))})${reset}`
    );
  });
  console.log(` ${cyan}${ALL_RUNTIMES.length + 1}${reset}) All runtimes`);
  console.log("");

  const choice = ((await prompt(` Choice ${dim}[1]${reset}: `)) || "1").toLowerCase();
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
    return "local";
  }
  if (args.includes("--global") || args.includes("-g")) {
    return "global";
  }
  if (args.includes("--local") || args.includes("-l")) {
    return "local";
  }

  if (!process.stdin.isTTY) {
    if (action === "uninstall") {
      error("Specify --global or --local when running --uninstall non-interactively.");
      process.exit(1);
    }
    warn("Non-interactive terminal detected, defaulting to global install.");
    return "global";
  }

  const globalExamples = runtimes.map((runtime) => formatDisplayPath(runtimeGlobalConfigDir(runtime))).join(", ");
  const localExamples = runtimes.map((runtime) => `./${runtimeConfigDirName(runtime)}`).join(", ");
  const actionPrompt = action === "uninstall" ? "uninstall from" : "install";
  const globalDescription = action === "uninstall" ? "remove it from all projects" : "available in all projects";
  const localDescription = action === "uninstall" ? "remove it from this project only" : "this project only";

  console.log(` ${yellow}Where would you like to ${actionPrompt}?${reset}`);
  console.log("");
  console.log(` ${cyan}1${reset}) Global ${dim}(${globalExamples})${reset} - ${globalDescription}`);
  console.log(` ${cyan}2${reset}) Local ${dim}(${localExamples})${reset} - ${localDescription}`);
  console.log("");

  const choice = ((await prompt(` Choice ${dim}[1]${reset}: `)) || "1").toLowerCase();
  if (choice === "1" || choice === "global") {
    return "global";
  }
  if (choice === "2" || choice === "local") {
    return "local";
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

function printCompletionSummary(runtimes, scope) {
  console.log("");
  success(`Installed GPD for ${formatRuntimeList(runtimes)} (${scope}).`);
  console.log("");

  if (runtimes.length === 1) {
    const runtime = runtimes[0];
    console.log(`  Start a new project:  ${formatRuntimeCommand(runtime, "new-project")}`);
    console.log(`  Show commands:        ${formatRuntimeCommand(runtime, "help")}`);
  } else {
    const width = Math.max(...runtimes.map((runtime) => runtimeDisplayName(runtime).length));
    console.log("  Start a new project:");
    for (const runtime of runtimes) {
      console.log(`  ${runtimeDisplayName(runtime).padEnd(width)}  ${formatRuntimeCommand(runtime, "new-project")}`);
    }
  }
  console.log("");
}

async function main() {
  const args = process.argv.slice(2);
  const hasHelp = args.includes("--help") || args.includes("-h");
  const isUninstall = args.includes("--uninstall");
  const forceStatusline = args.includes("--force-statusline");
  const reinstallManagedPackage = args.includes("--reinstall");
  const upgradeManagedPackage = args.includes("--upgrade");
  const targetDir = parseTargetDirArg(args);

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
  if (isUninstall && forceStatusline) {
    error("Cannot combine --uninstall with --force-statusline.");
    process.exit(1);
  }
  if (targetDir && (args.includes("--global") || args.includes("-g"))) {
    error("Cannot combine --target-dir with --global. Use --local semantics for explicit target directories.");
    process.exit(1);
  }

  const action = isUninstall ? "uninstall" : "install";
  const selectedRuntimes = await selectRuntimes(args, action);
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
  });
  if (!packageInstall.ok) {
    error(`Failed to install ${packageInstall.pythonPackageSpec}.`);
    process.exit(1);
  }

  const actionMessage = isUninstall ? "Uninstalling GPD from" : "Installing GPD for";
  log(`${actionMessage} ${formatRuntimeList(selectedRuntimes)} (${scope})...`);

  const cliArgs = buildRuntimeCommandArgs(action, selectedRuntimes, scope, targetDir, { forceStatusline });

  // Run the installer/uninstaller through the managed Python interpreter.
  const result = spawnSync(managedEnv.python, cliArgs, {
    stdio: "inherit",
    env: process.env,
  });

  if (result.status === 0) {
    if (!isUninstall) {
      printCompletionSummary(selectedRuntimes, scope);
    }
  } else {
    error(`${isUninstall ? "Uninstall" : "Installation"} failed. Check the output above for details.`);
    process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
