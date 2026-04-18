import { API_BASE } from "@/lib/apiBase";

const FORMULAS = new Set(["br_bor_v1", "classic_bpr_csa"]);

export function buildPlayersDirectoryUrl({
  limit = 200,
  skip = 0,
  teamShort = "",
  q = "",
  formula = "br_bor_v1",
  cacheBust = "",
} = {}) {
  if (!API_BASE) return "";
  const p = new URLSearchParams();
  p.set("limit", String(Math.max(1, Math.min(Number(limit) || 2000, 5000))));
  p.set("skip", String(Math.max(0, Number(skip) || 0)));
  if (teamShort && String(teamShort).trim()) p.set("team_short", String(teamShort).trim());
  if (q && String(q).trim()) p.set("q", String(q).trim());
  const f = FORMULAS.has(String(formula)) ? String(formula) : "br_bor_v1";
  p.set("formula", f);
  if (cacheBust) p.set("_", String(cacheBust));
  return `${API_BASE}/players/directory?${p.toString()}`;
}

/** GET — full CSA/BPR step-by-step for one player (`q` substring or exact `name` / `playerId`). */
export function buildPlayerCsaExplainUrl({
  playerId,
  name,
  q,
  formula = "br_bor_v1",
  battingPosition,
} = {}) {
  if (!API_BASE) return "";
  const p = new URLSearchParams();
  if (playerId != null && String(playerId).trim() !== "") p.set("player_id", String(playerId));
  if (name != null && String(name).trim()) p.set("name", String(name).trim());
  if (q != null && String(q).trim()) p.set("q", String(q).trim());
  const f = FORMULAS.has(String(formula)) ? String(formula) : "br_bor_v1";
  p.set("formula", f);
  if (battingPosition != null && String(battingPosition).trim() !== "") {
    p.set("batting_position", String(battingPosition));
  }
  return `${API_BASE}/player-impact/csa-explain?${p.toString()}`;
}
