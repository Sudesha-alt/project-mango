import { API_BASE } from "@/lib/apiBase";

export function buildPlayersDirectoryUrl({ limit = 200, skip = 0, teamShort = "", q = "" } = {}) {
  if (!API_BASE) return "";
  const p = new URLSearchParams();
  p.set("limit", String(Math.max(1, Math.min(Number(limit) || 2000, 5000))));
  p.set("skip", String(Math.max(0, Number(skip) || 0)));
  if (teamShort && String(teamShort).trim()) p.set("team_short", String(teamShort).trim());
  if (q && String(q).trim()) p.set("q", String(q).trim());
  return `${API_BASE}/players/directory?${p.toString()}`;
}
