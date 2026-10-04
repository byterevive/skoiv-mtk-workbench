#!/usr/bin/env node
/**
 * Create a stub skoiv-worker sidecar for the host target triple if none
 * exists. tauri-build validates `bundle.externalBin` at compile time, so the
 * file must be present for `cargo check` / `tauri dev` before the frozen
 * worker has been built (CI release builds copy the real PyInstaller exe).
 *
 * The stub exits immediately; set SKOIV_WORKER_BIN/SKOIV_WORKER_ARGS to point
 * the desktop shell at a real worker during development.
 */
import { chmodSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const binDir = join(here, "..", "src-tauri", "binaries");

function hostTriple() {
  const arch = process.arch === "x64" ? "x86_64" : process.arch === "arm64" ? "aarch64" : process.arch;
  if (process.platform === "linux") return `${arch}-unknown-linux-gnu`;
  if (process.platform === "darwin") return `${arch}-apple-darwin`;
  if (process.platform === "win32") return `${arch}-pc-windows-msvc`;
  return `${arch}-unknown`;
}

const name = `skoiv-worker-${hostTriple()}${process.platform === "win32" ? ".exe" : ""}`;
const target = join(binDir, name);

if (existsSync(target)) {
  console.log(`sidecar present: ${target}`);
  process.exit(0);
}

mkdirSync(binDir, { recursive: true });
if (process.platform === "win32") {
  console.error(
    "Windows stubs are not supported. Build the frozen worker and copy it to\n" +
      `  ${target}\n` +
      "or run the release-windows workflow (see docs/development/release.md).",
  );
  process.exit(1);
}

writeFileSync(
  target,
  `#!/bin/sh\necho '{"v":1,"type":"event","event":"worker-health","data":{"status":"error","message":"stub sidecar: set SKOIV_WORKER_BIN to a real worker"}}' >&2\nexit 0\n`,
);
chmodSync(target, 0o755);
console.log(`stub sidecar created: ${target}`);
