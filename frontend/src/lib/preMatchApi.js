import { API_BASE } from "@/lib/apiBase";

/**
 * Build POST URL for pre-match prediction with optional cache bust and live SportMonks perf.
 * @param {object} opts
 * @param {boolean} [opts.force]
 * @param {boolean} [opts.livePlayerPerf]
 * @param {"br_bor_v1"|"classic_bpr_csa"} [opts.formula] — team-strength BatIP/BowlIP model */
export function buildPreMatchPredictUrl(
  matchId,
  { force = false, livePlayerPerf = false, formula } = {},
) {
  if (!API_BASE || !matchId) return "";
  const p = new URLSearchParams();
  if (force) p.set("force", "true");
  if (livePlayerPerf) p.set("live_player_perf", "true");
  if (formula && formula !== "br_bor_v1") p.set("formula", formula);
  const q = p.toString();
  return `${API_BASE}/matches/${matchId}/pre-match-predict${q ? `?${q}` : ""}`;
}

/**
 * POST URL for Claude XI roles + full re-predict (force).
 */
export function buildFetchXiRolesAndPredictUrl(matchId, { livePlayerPerf = false, formula } = {}) {
  if (!API_BASE || !matchId) return "";
  const p = new URLSearchParams();
  if (livePlayerPerf) p.set("live_player_perf", "true");
  if (formula && formula !== "br_bor_v1") p.set("formula", formula);
  const q = p.toString();
  return `${API_BASE}/matches/${matchId}/fetch-playing-xi-roles-and-predict${q ? `?${q}` : ""}`;
}

export function formatPlayerPerformanceSource(src) {
  if (src === "mongodb_player_performance") return "MongoDB (synced IPL aggregates)";
  if (src === "sportmonks_recent_matches") return "SportMonks (last 5 matches / team)";
  return src || "—";
}

/** POST — background job; returns immediately. */
export function buildSyncCareerProfilesUrl(limit = 500) {
  if (!API_BASE) return "";
  const lim = Math.max(1, Math.min(Number(limit) || 500, 2000));
  return `${API_BASE}/sync-player-career-profiles?limit=${lim}`;
}

/** GET — one Mongo `player_performance` row (`meta` + normalized `perf`). Query: player_id and/or name. */
export function buildGetPlayerPerformanceUrl({ playerId, name } = {}) {
  if (!API_BASE) return "";
  const p = new URLSearchParams();
  if (playerId != null && String(playerId).trim() !== "") p.set("player_id", String(playerId));
  if (name != null && String(name).trim() !== "") p.set("name", String(name).trim());
  const q = p.toString();
  if (!q) return "";
  return `${API_BASE}/player-performance?${q}`;
}
