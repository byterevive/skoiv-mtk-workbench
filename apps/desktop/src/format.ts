/** Small formatting helpers. */

export function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(n % 1024 ** 3 === 0 ? 0 : 1)} GiB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(n % 1024 ** 2 === 0 ? 0 : 1)} MiB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KiB`;
  return `${n} B`;
}

export function formatLba(n: number): string {
  return n.toLocaleString("en-US");
}

export function formatHex16(vid: number | null): string {
  return vid == null ? "—" : `0x${vid.toString(16).toUpperCase().padStart(4, "0")}`;
}
