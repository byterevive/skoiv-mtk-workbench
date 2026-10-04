/** IPC v1 message shapes (see schemas/ipc/v1/message-envelope.schema.json). */

export type Risk = "green" | "yellow" | "red";

export interface GptPartition {
  index: number;
  name: string;
  type_guid: string;
  type_name: string;
  unique_guid: string;
  first_lba: number;
  last_lba: number;
  sectors: number;
  size_bytes: number;
  attributes: number;
  risk: Risk;
}

export interface GptResult {
  sector_size: number;
  disk_guid: string;
  current_lba: number;
  backup_lba: number;
  first_usable_lba: number;
  last_usable_lba: number;
  num_partition_entries: number;
  size_of_partition_entry: number;
  header_crc32_ok: boolean;
  entries_crc32_ok: boolean;
  partitions: GptPartition[];
  raw_sha256: string;
  raw_size: number;
  source: string;
  meta: Record<string, unknown>;
}

export interface DetectedDevice {
  port: string;
  description: string;
  chip_hint: string | null;
  mode: string | null;
  vid: number | null;
  pid: number | null;
}

export interface DetectResult {
  adapter: string;
  devices: DetectedDevice[];
  hint: string | null;
}

export interface PingResult {
  pong: boolean;
  worker_version: string;
  protocol_version: number;
  python: string;
  uptime_s: number;
  platform: string;
}

export interface AdapterInfo {
  name: string;
  mode: string;
  read_only: boolean;
  description: string;
  mtkclient_version?: string | null;
}

export interface WorkerEventMsg {
  v: number;
  type: string;
  event: string;
  data: Record<string, unknown>;
}

export interface LogEntry {
  id: number;
  ts: number;
  level: string;
  message: string;
}
