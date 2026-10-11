export const pct = (p: number, digits = 0) => `${(p * 100).toFixed(digits)}%`;

export const num = (n: number) => n.toLocaleString("en-US");

/** Real durations at a readable precision: 0.005 s, 0.482 s, 3.27 s, 12.3 s, 2 min 5 s. */
export function duration(s: number | null | undefined): string {
  if (s == null) return "–";
  if (s < 10) return `${s < 1 ? s.toFixed(3) : s.toFixed(2)} s`;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${Math.round(s % 60)} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function ago(epochSeconds: number, now = Date.now()): string {
  const s = Math.max(0, Math.round(now / 1000 - epochSeconds));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

/** "loaded_language" -> "Loaded language"; "government agency" stays readable. */
export function humanize(key: string): string {
  const s = key.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** "1 analysis", "11 analyses": count + correctly inflected noun. */
export const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
