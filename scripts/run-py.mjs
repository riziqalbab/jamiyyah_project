import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const PYTHON_PACKAGES = [
  "packages/schema",
  "packages/normalizer",
  "packages/parsers",
  "packages/rag-engine",
];

function resolvePython() {
  const venvCandidates =
    process.platform === "win32"
      ? [path.join(repoRoot, ".venv", "Scripts", "python.exe")]
      : [path.join(repoRoot, ".venv", "bin", "python")];

  for (const candidate of venvCandidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return process.platform === "win32" ? "python" : "python3";
}

function buildPythonPath() {
  const pkgPaths = PYTHON_PACKAGES.map((p) => path.resolve(repoRoot, p));
  if (process.env.PYTHONPATH) {
    pkgPaths.push(process.env.PYTHONPATH);
  }
  return pkgPaths.join(path.delimiter);
}

function runPython(pythonBin, args, env) {
  const result = spawnSync(pythonBin, args, {
    cwd: repoRoot,
    env,
    stdio: "inherit",
  });
  if (result.error) {
    console.error(`Failed to start Python (${pythonBin}):`, result.error.message);
    process.exit(1);
  }
  return result.status ?? 1;
}

function runTests(pythonBin, env) {
  const packagesDir = path.join(repoRoot, "packages");
  const testDirs = fs
    .readdirSync(packagesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(packagesDir, entry.name, "tests"))
    .filter((dir) => fs.existsSync(dir));

  for (const dir of testDirs) {
    const status = runPython(
      pythonBin,
      ["-m", "unittest", "discover", "-s", dir, "-p", "test_*.py", "-v"],
      env,
    );
    if (status !== 0) {
      process.exit(status);
    }
  }
  process.exit(0);
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("Usage: node scripts/run-py.mjs [--test | <python args...>]");
  process.exit(1);
}

const pythonBin = resolvePython();
const env = { ...process.env, PYTHONPATH: buildPythonPath() };

if (args[0] === "--test") {
  runTests(pythonBin, env);
} else {
  process.exit(runPython(pythonBin, args, env));
}
