#!/usr/bin/env node
import { existsSync } from "node:fs";
import { platform } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const scriptArgs = process.argv.slice(2);

if (scriptArgs.length === 0) {
  console.error(
    "usage: node scripts/run_python.mjs <script-or-module> [args...]",
  );
  process.exit(2);
}

const candidates = pythonCandidates(process.cwd());
const python = candidates.find((candidate) => canRunPython(candidate));

if (!python) {
  console.error(
    "No Python interpreter found. Set MINIX_PYTHON or create the repo .venv.",
  );
  process.exit(127);
}

const result = spawnSync(
  python.command,
  [...python.prefixArgs, ...scriptArgs],
  {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
  },
);

if (result.error) {
  console.error(result.error.message);
  process.exit(127);
}

process.exit(result.status ?? 1);

function pythonCandidates(root) {
  const candidates = [];
  if (process.env.MINIX_PYTHON) {
    candidates.push({ command: process.env.MINIX_PYTHON, prefixArgs: [] });
  }

  const venvPython =
    platform() === "win32"
      ? join(root, ".venv", "Scripts", "python.exe")
      : join(root, ".venv", "bin", "python");
  if (existsSync(venvPython)) {
    candidates.push({ command: venvPython, prefixArgs: [] });
  }

  if (platform() === "win32") {
    candidates.push({ command: "python", prefixArgs: [] });
    candidates.push({ command: "py", prefixArgs: ["-3"] });
  } else {
    candidates.push({ command: "python3", prefixArgs: [] });
    candidates.push({ command: "python", prefixArgs: [] });
  }
  return candidates;
}

function canRunPython(candidate) {
  const result = spawnSync(
    candidate.command,
    [...candidate.prefixArgs, "--version"],
    {
      cwd: process.cwd(),
      env: process.env,
      stdio: "ignore",
    },
  );
  return !result.error && result.status === 0;
}
