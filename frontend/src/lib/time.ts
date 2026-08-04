export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const s = Math.max(0, Math.floor((now - then) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} day${d === 1 ? "" : "s"} ago`;
  const w = Math.floor(d / 7);
  return `${w} week${w === 1 ? "" : "s"} ago`;
}

export function dayGroup(iso: string): "Today" | "Yesterday" | "Previous 7 Days" | "Older" {
  const then = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = then.getTime();
  const day = 24 * 60 * 60 * 1000;
  if (t >= startOfToday) return "Today";
  if (t >= startOfToday - day) return "Yesterday";
  if (t >= startOfToday - 7 * day) return "Previous 7 Days";
  return "Older";
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function groupByDay<T extends { created_at: string }>(items: T[]): Array<[string, T[]]> {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    const g = dayGroup(item.created_at);
    (groups[g] ??= []).push(item);
  }
  const order = ["Today", "Yesterday", "Previous 7 Days", "Older"];
  return order
    .filter((g) => groups[g])
    .map((g) => [g, groups[g]] as [string, T[]]);
}
