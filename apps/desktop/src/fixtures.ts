/** Browser-mode fixture data mirroring worker/src/skoiv_worker/adapters/mock.py. */

import type { DetectResult, GptPartition, GptResult, Risk } from "./types";

const RED_EXACT = new Set([
  "preloader", "pgpt", "sgpt", "lk", "lk2", "boot", "recovery", "vbmeta",
  "vbmeta_system", "vbmeta_vendor", "tee1", "tee2", "sspm_1", "sspm_2",
  "spmfw", "gz1", "gz2", "mcupm_1", "mcupm_2", "md1img", "spm",
]);
const RED_PREFIXES = ["preloader", "lk", "tee", "sspm", "spmfw", "gz", "mcupm", "md1"];
const YELLOW_EXACT = new Set([
  "nvram", "nvcfg", "proinfo", "protect1", "protect2", "persist", "seccfg",
  "expdb", "frp", "metadata", "para", "flashinfo", "otp", "efuse",
]);
const GREEN_EXACT = new Set([
  "system", "system_ext", "vendor", "product", "cache", "userdata", "intsd",
  "logo", "odmdtbo",
]);

export function classifyRisk(name: string): Risk {
  const n = name.trim().toLowerCase();
  if (RED_EXACT.has(n) || RED_PREFIXES.some((p) => n.startsWith(p))) return "red";
  if (YELLOW_EXACT.has(n)) return "yellow";
  if (GREEN_EXACT.has(n)) return "green";
  return "yellow";
}

const LAYOUT: Array<[string, string, number]> = [
  ["preloader", "Android Bootloader", 4],
  ["pgpt", "EFI System", 2],
  ["proinfo", "Microsoft Basic Data", 3],
  ["nvram", "Microsoft Basic Data", 64],
  ["protect1", "Microsoft Basic Data", 8],
  ["protect2", "Microsoft Basic Data", 8],
  ["seccfg", "Microsoft Basic Data", 4],
  ["persist", "Microsoft Basic Data", 64],
  ["expdb", "Microsoft Basic Data", 64],
  ["frp", "Microsoft Basic Data", 1],
  ["nvcfg", "Microsoft Basic Data", 20],
  ["metadata", "Android Metadata", 32],
  ["para", "Microsoft Basic Data", 8],
  ["md1img", "Microsoft Basic Data", 64],
  ["spmfw", "Microsoft Basic Data", 4],
  ["scp1", "Microsoft Basic Data", 8],
  ["sspm_1", "Microsoft Basic Data", 8],
  ["gz1", "Microsoft Basic Data", 16],
  ["lk", "Android Bootloader", 2],
  ["lk2", "Android Bootloader", 2],
  ["boot", "Android Boot", 64],
  ["recovery", "Android Recovery", 64],
  ["vbmeta", "EFI System", 8],
  ["logo", "Microsoft Basic Data", 16],
  ["odmdtbo", "Microsoft Basic Data", 16],
  ["super", "Android Super / Metadata", 4096],
  ["cache", "Microsoft Basic Data", 256],
  ["userdata", "Microsoft Basic Data", 2048],
  ["flashinfo", "Microsoft Basic Data", 4],
];

function buildPartitions(): GptPartition[] {
  const out: GptPartition[] = [];
  let lba = 34;
  LAYOUT.forEach(([name, typeName, sizeMib], i) => {
    const sectors = (sizeMib * 1024 * 1024) / 512;
    out.push({
      index: i,
      name,
      type_guid: "00000000-0000-0000-0000-000000000000",
      type_name: typeName,
      unique_guid: "00000000-0000-0000-0000-000000000000",
      first_lba: lba,
      last_lba: lba + sectors - 1,
      sectors,
      size_bytes: sectors * 512,
      attributes: 0,
      risk: classifyRisk(name),
    });
    lba += sectors;
  });
  return out;
}

export function fixtureGpt(): GptResult {
  return {
    sector_size: 512,
    disk_guid: "9f2c1a4e-7b3d-4c2a-9e10-5d8f6b1c2a70",
    current_lba: 1,
    backup_lba: 15269887,
    first_usable_lba: 34,
    last_usable_lba: 15269853,
    num_partition_entries: 128,
    size_of_partition_entry: 128,
    header_crc32_ok: true,
    entries_crc32_ok: true,
    partitions: buildPartitions(),
    raw_sha256:
      "3f786850e387550fdab836ed7e6dc881de23001b3f786850e387550fdab836ed",
    raw_size: 17408,
    source: "browser:fixture",
    meta: { adapter: "browser-mock" },
  };
}

export function fixtureDetect(): DetectResult {
  return {
    adapter: "browser-mock",
    devices: [
      {
        port: "mock:001",
        description: "Skoiv fixture device (browser mock)",
        chip_hint: "MT6768",
        mode: "brom",
        vid: 0x0e8d,
        pid: 0x0003,
      },
    ],
    hint: null,
  };
}
