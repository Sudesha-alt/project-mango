import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Spinner, Lightning, TrendUp, TrendDown, Minus, UsersThree, ChatDots } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

export default function PlayingXIPerformance({ matchId, team1, team2 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [impactSaving, setImpactSaving] = useState(null);
  const [impactMsg, setImpactMsg] = useState(null);
  const [repredicting, setRepredicting] = useState(false);

  const [t1Query, setT1Query] = useState("");
  const [t1Results, setT1Results] = useState([]);
  const [t1Selected, setT1Selected] = useState(null);
  const [t1Searching, setT1Searching] = useState(false);
  const [t2Query, setT2Query] = useState("");
  const [t2Results, setT2Results] = useState([]);
  const [t2Selected, setT2Selected] = useState(null);
  const [t2Searching, setT2Searching] = useState(false);
  const [t1SwapOut, setT1SwapOut] = useState("");
  const [t2SwapOut, setT2SwapOut] = useState("");

  const [t1FillQuery, setT1FillQuery] = useState("");
  const [t1FillResults, setT1FillResults] = useState([]);
  const [t1FillSelected, setT1FillSelected] = useState(null);
  const [t1FillSearching, setT1FillSearching] = useState(false);
  const [t2FillQuery, setT2FillQuery] = useState("");
  const [t2FillResults, setT2FillResults] = useState([]);
  const [t2FillSelected, setT2FillSelected] = useState(null);
  const [t2FillSearching, setT2FillSearching] = useState(false);
  const [fillSaving, setFillSaving] = useState(null);

  const refreshPlayingXiData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/predictions/upcoming`);
      const pred = (res.data.predictions || []).find((p) => p.matchId === matchId);
      if (pred?.playing_xi && (pred.playing_xi.team1_xi?.length > 0 || pred.playing_xi.team2_xi?.length > 0)) {
        setData(pred.playing_xi);
        return;
      }
    } catch (e) {
      /* ignore */
    }
    try {
      const st = await axios.get(`${API}/matches/${matchId}/playing-xi/status`);
      if (st.data?.status === "running") return;
      if (st.data?.team1_xi?.length > 0 || st.data?.team2_xi?.length > 0) {
        setData(st.data);
      }
    } catch (e) {
      /* ignore */
    }
  }, [matchId]);

  useEffect(() => {
    refreshPlayingXiData();
  }, [refreshPlayingXiData]);

  useEffect(() => {
    const m1 = data?.team1_manual_impact_player;
    if (m1?.name) {
      setT1Selected({ name: m1.name, role: m1.role, isOverseas: m1.isOverseas });
      setT1Query(m1.name);
    } else {
      setT1Selected(null);
      setT1Query("");
    }
    const m2 = data?.team2_manual_impact_player;
    if (m2?.name) {
      setT2Selected({ name: m2.name, role: m2.role, isOverseas: m2.isOverseas });
      setT2Query(m2.name);
    } else {
      setT2Selected(null);
      setT2Query("");
    }
    const s1 = data?.team1_manual_impact_swap_out;
    setT1SwapOut(typeof s1 === "string" && s1.trim() ? s1.trim() : "");
    const s2 = data?.team2_manual_impact_swap_out;
    setT2SwapOut(typeof s2 === "string" && s2.trim() ? s2.trim() : "");
  }, [
    data?.team1_manual_impact_player,
    data?.team2_manual_impact_player,
    data?.team1_manual_impact_swap_out,
    data?.team2_manual_impact_swap_out,
  ]);

  useEffect(() => {
    if (!matchId) return;
    const t = t1Query.trim();
    if (t.length < 2) {
      setT1Results([]);
      return;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      setT1Searching(true);
      try {
        const res = await axios.get(`${API}/matches/${matchId}/playing-xi/impact-search`, {
          params: { team: "team1", q: t },
        });
        if (!cancelled) setT1Results(res.data?.matches || []);
      } catch {
        if (!cancelled) setT1Results([]);
      } finally {
        if (!cancelled) setT1Searching(false);
      }
    }, 320);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [matchId, t1Query]);

  useEffect(() => {
    if (!matchId) return;
    const t = t2Query.trim();
    if (t.length < 2) {
      setT2Results([]);
      return;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      setT2Searching(true);
      try {
        const res = await axios.get(`${API}/matches/${matchId}/playing-xi/impact-search`, {
          params: { team: "team2", q: t },
        });
        if (!cancelled) setT2Results(res.data?.matches || []);
      } catch {
        if (!cancelled) setT2Results([]);
      } finally {
        if (!cancelled) setT2Searching(false);
      }
    }, 320);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [matchId, t2Query]);

  useEffect(() => {
    if (!matchId) return;
    const t = t1FillQuery.trim();
    if (t.length < 2) {
      setT1FillResults([]);
      return;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      setT1FillSearching(true);
      try {
        const res = await axios.get(`${API}/matches/${matchId}/playing-xi/impact-search`, {
          params: { team: "team1", q: t },
        });
        if (!cancelled) setT1FillResults(res.data?.matches || []);
      } catch {
        if (!cancelled) setT1FillResults([]);
      } finally {
        if (!cancelled) setT1FillSearching(false);
      }
    }, 320);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [matchId, t1FillQuery]);

  useEffect(() => {
    if (!matchId) return;
    const t = t2FillQuery.trim();
    if (t.length < 2) {
      setT2FillResults([]);
      return;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      setT2FillSearching(true);
      try {
        const res = await axios.get(`${API}/matches/${matchId}/playing-xi/impact-search`, {
          params: { team: "team2", q: t },
        });
        if (!cancelled) setT2FillResults(res.data?.matches || []);
      } catch {
        if (!cancelled) setT2FillResults([]);
      } finally {
        if (!cancelled) setT2FillSearching(false);
      }
    }, 320);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [matchId, t2FillQuery]);

  /** Named rows in Expected ``team*_xi`` only (not impact subs) — for10/11 incomplete-XI UI. */
  const xiNamedCount = (side) => {
    if (!data) return 0;
    const xiKey = side === "team1" ? "team1_xi" : "team2_xi";
    let n = 0;
    for (const p of data[xiKey] || []) {
      if (typeof p !== "object" || !p) continue;
      if (String(p.name || p.fullname || "").trim()) n += 1;
    }
    return n;
  };

  /**
   * First 11 logical starters for the swap-out dropdown — must match backend
   * ``_union_xi_and_subs_rows`` + ``_xi_starter_names_for_side`` (XI rows first, then impact subs).
   * Uses name || fullname so Team B is not stuck with a disabled swap when only fullname is set.
   */
  const xiStarterNames = (side) => {
    if (!data) return [];
    const xiKey = side === "team1" ? "team1_xi" : "team2_xi";
    const subsKey = side === "team1" ? "team1_impact_subs" : "team2_impact_subs";
    const norm = (s) => String(s || "").trim().toLowerCase().replace(/\s+/g, " ");
    const out = [];
    const seen = new Set();
    const pushNm = (nm) => {
      const t = String(nm || "").trim();
      if (!t) return;
      const k = norm(t);
      if (seen.has(k)) return;
      seen.add(k);
      out.push(t);
    };
    for (const p of data[xiKey] || []) {
      if (typeof p !== "object" || !p) continue;
      pushNm(p.name || p.fullname);
      if (out.length >= 11) return out;
    }
    for (const p of data[subsKey] || []) {
      if (typeof p === "string") pushNm(p);
      else if (p && typeof p === "object") pushNm(p.name || p.fullname);
      if (out.length >= 11) return out;
    }
    return out;
  };

  const saveCompleteXiSlot = async (side, playerName) => {
    setFillSaving(side);
    setImpactMsg(null);
    setError(null);
    try {
      await axios.put(`${API}/matches/${matchId}/playing-xi/complete-xi-slot`, {
        team: side,
        player_name: playerName || "",
      });
      await refreshPlayingXiData();
      if (side === "team1") {
        setT1FillQuery("");
        setT1FillSelected(null);
        setT1FillResults([]);
      } else {
        setT2FillQuery("");
        setT2FillSelected(null);
        setT2FillResults([]);
      }
      setImpactMsg(
        "Starter saved to Expected XI (Mongo + pre-match cache). Add IPL Impact below if needed, then Apply to model and refresh Claude."
      );
    } catch (e) {
      const msg = e.response?.data?.detail?.message || e.response?.data?.detail || e.message || "Save failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setFillSaving(null);
    }
  };

  const saveManualImpact = async (side, playerName, swapOutName) => {
    setImpactSaving(side);
    setImpactMsg(null);
    setError(null);
    try {
      const body = {
        team: side,
        player_name: playerName || "",
      };
      if (playerName && playerName.trim()) {
        body.swap_out_player_name = swapOutName && swapOutName.trim() ? swapOutName.trim() : "";
      }
      await axios.put(`${API}/matches/${matchId}/playing-xi/manual-impact`, body);
      await refreshPlayingXiData();
      setImpactMsg(
        playerName
          ? "Impact player saved. Run “Apply to model” then run or refresh Claude analysis so the 7-layer pre-match uses this pick (BPR/CSA cards + impact subs)."
          : "Manual impact cleared."
      );
    } catch (e) {
      const msg = e.response?.data?.detail?.message || e.response?.data?.detail || e.message || "Save failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setImpactSaving(null);
    }
  };

  const applyPreMatchModel = async () => {
    setRepredicting(true);
    setImpactMsg(null);
    setError(null);
    try {
      await axios.post(`${API}/matches/${matchId}/pre-match-predict?force=true`);
      await refreshPlayingXiData();
      setImpactMsg("Pre-match model refreshed with current XI + manual impact.");
    } catch (e) {
      const d = e.response?.data?.detail;
      const msg =
        typeof d === "string"
          ? d
          : d?.message || e.message || "Pre-match predict failed";
      setError(msg);
    } finally {
      setRepredicting(false);
    }
  };

  const handleFetch = async () => {
    setLoading(true);
    setError(null);
    try {
      // Start background fetch
      const startRes = await axios.post(`${API}/matches/${matchId}/playing-xi`);
      if (startRes.data?.error) {
        setError(startRes.data.error);
        setLoading(false);
        return;
      }
      
      // Poll for results
      let attempts = 0;
      const maxAttempts = 40; // 40 * 3s = 120s max
      const poll = async () => {
        attempts++;
        try {
          const statusRes = await axios.get(`${API}/matches/${matchId}/playing-xi/status`);
          const d = statusRes.data;
          
          if (d.status === "running") {
            if (attempts < maxAttempts) {
              setTimeout(poll, 3000);
            } else {
              setError("Playing XI fetch timed out after 2 minutes. Try again.");
              setLoading(false);
            }
            return;
          }
          
          if (d.error) {
            setError(d.error);
            setLoading(false);
            return;
          }
          
          if ((d.team1_xi?.length || 0) > 0 || (d.team2_xi?.length || 0) > 0) {
            setData((prev) => ({ ...d, fetched_at: d.fetched_at || prev?.fetched_at }));
          } else {
            setError("No Playing XI data returned. Try again.");
          }
          setLoading(false);
        } catch {
          if (attempts < maxAttempts) {
            setTimeout(poll, 3000);
          } else {
            setError("Lost connection during fetch. Check if data loaded.");
            setLoading(false);
          }
        }
      };
      
      // Start polling after 3s initial delay
      setTimeout(poll, 3000);
    } catch (e) {
      setError("Failed to start Playing XI fetch. Try again.");
      setLoading(false);
    }
  };

  const roleColor = (role) => {
    if (!role) return "#737373";
    const r = role.toLowerCase();
    if (r.includes("bat")) return "#007AFF";
    if (r.includes("bowl")) return "#FF3B30";
    if (r.includes("all")) return "#34C759";
    if (r.includes("keeper")) return "#FFCC00";
    return "#737373";
  };

  const luckLabel = (factor) => {
    if (!factor) return null;
    if (factor > 1.05) return { icon: TrendUp, color: "#34C759", label: "Lucky" };
    if (factor < 0.95) return { icon: TrendDown, color: "#FF3B30", label: "Unlucky" };
    return { icon: Minus, color: "#737373", label: "Neutral" };
  };

  const buzzDisplay = (player) => {
    const score = player.buzz_score;
    // Support both new buzz_score (-100 to +100) and legacy buzz_confidence (0-100)
    if (score === undefined && player.buzz_confidence !== undefined) {
      // Legacy: treat as positive-only
      const bc = player.buzz_confidence;
      return {
        value: bc,
        label: `+${bc}`,
        color: bc >= 60 ? "#34C759" : bc >= 30 ? "#FFCC00" : "#FF3B30",
        bgColor: bc >= 60 ? "rgba(52,199,89,0.12)" : bc >= 30 ? "rgba(234,179,8,0.12)" : "rgba(255,59,48,0.12)",
        isPositive: bc >= 30,
        reason: player.buzz_reason || "",
      };
    }
    const s = score || 0;
    const abs = Math.abs(s);
    const isPositive = s >= 0;
    return {
      value: s,
      label: isPositive ? `+${abs}` : `-${abs}`,
      color: s >= 40 ? "#34C759" : s >= 10 ? "#8BC34A" : s >= -10 ? "#737373" : s >= -40 ? "#FF9800" : "#FF3B30",
      bgColor: s >= 40 ? "rgba(52,199,89,0.12)" : s >= 10 ? "rgba(139,195,58,0.12)" : s >= -10 ? "rgba(115,115,115,0.12)" : s >= -40 ? "rgba(255,152,0,0.12)" : "rgba(255,59,48,0.12)",
      isPositive,
      reason: player.buzz_reason || "",
    };
  };

  const PlayerRow = ({ player, idx }) => {
    const luck = luckLabel(player.luck_factor);
    const buzz = buzzDisplay(player);
    const venueStats = player.venue_stats;
    const [showReason, setShowReason] = useState(false);
    const posLabel = typeof idx === "number" ? idx + 1 : idx;
    return (
      <div className={`py-1.5 ${idx > 0 ? "border-t border-[#1E1E1E]" : ""}`}>
        <div className="flex items-center gap-2">
          <span className="w-5 text-[10px] text-[#525252] font-mono text-right">{posLabel}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-white truncate">{player.name}</span>
              {player.is_captain && <span className="text-[8px] px-1 py-0 bg-[#FFCC00]/20 text-[#FFCC00] rounded font-bold">C</span>}
              {player.is_overseas && <span className="text-[8px] px-1 py-0 bg-[#007AFF]/20 text-[#007AFF] rounded">OS</span>}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: roleColor(player.role) }}>
                {player.role}
              </span>
              {player.role_source === "claude" && (
                <span className="text-[7px] px-1 py-0 rounded bg-[#7C3AED]/25 text-[#C4B5FD] font-mono uppercase">Claude</span>
              )}
              {venueStats && venueStats.matches_at_venue > 0 && (
                <span className="text-[8px] text-[#525252] font-mono">
                  @venue: {venueStats.runs_at_venue}r/{venueStats.wickets_at_venue}w in {venueStats.matches_at_venue}m
                </span>
              )}
            </div>
          </div>
          <div className="text-right space-y-0.5 flex-shrink-0">
            <div className="flex items-center gap-1.5 justify-end">
              <span className="text-[10px] text-[#A1A1AA] font-mono" data-testid="player-expected-runs">
                {player.expected_runs != null ? `${player.expected_runs}r` : "—"}
              </span>
              <span className="text-[10px] text-[#A1A1AA] font-mono" data-testid="player-expected-wickets">
                {player.expected_wickets != null ? `${player.expected_wickets}w` : "—"}
              </span>
              {/* Buzz badge */}
              <button
                onClick={() => buzz.reason && setShowReason(!showReason)}
                className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-0.5 transition-all"
                style={{ color: buzz.color, backgroundColor: buzz.bgColor }}
                title={buzz.reason || `Buzz: ${buzz.label}`}
                data-testid="player-buzz-score"
              >
                {buzz.isPositive ? <TrendUp weight="bold" className="w-2.5 h-2.5" /> : <TrendDown weight="bold" className="w-2.5 h-2.5" />}
                {buzz.label}
                {buzz.reason && <ChatDots weight="fill" className="w-2.5 h-2.5 opacity-50" />}
              </button>
              {luck && (
                <span className="flex items-center gap-0.5" title={`Luck: ${luck.label} (${player.luck_factor})`}>
                  <luck.icon weight="bold" className="w-2.5 h-2.5" style={{ color: luck.color }} />
                </span>
              )}
            </div>
          </div>
        </div>
        {/* Buzz reason tooltip */}
        {showReason && buzz.reason && (
          <div className="ml-7 mt-1 mb-0.5 px-2 py-1 bg-[#1A1A1A] border border-[#262626] rounded text-[9px] text-[#A3A3A3] leading-relaxed" data-testid="player-buzz-reason">
            <span style={{ color: buzz.color }} className="font-bold">BUZZ:</span> {buzz.reason}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="playing-xi-performance">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] flex items-center gap-1.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
          <UsersThree weight="fill" className="w-4 h-4 text-[#7C3AED]" />
          Expected Playing XI + Performance
          <InfoTooltip text="Expected XI from SportMonks with squad merge. If a side has only 10 named starters, use “Complete Expected XI” to add the 11th from the bench, then “Manual IPL Impact” for the impact sub — both persist to Mongo and feed pre-match + Claude after Apply to model." />
        </h4>
        {!data && (
          <button onClick={handleFetch} disabled={loading} data-testid="fetch-playing-xi-btn"
            className="text-[10px] font-bold uppercase px-3 py-1.5 rounded bg-[#7C3AED]/20 text-[#7C3AED] hover:bg-[#7C3AED]/30 transition-colors disabled:opacity-50">
            {loading ? <span className="flex items-center gap-1"><Spinner className="w-3 h-3 animate-spin" /> Fetching...</span> : "Fetch Playing XI"}
          </button>
        )}
        {data && (
          <div className="flex items-center gap-2">
            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase" 
              style={{ backgroundColor: data.confidence === "confirmed" ? "rgba(52,199,89,0.15)" : "rgba(234,179,8,0.15)", color: data.confidence === "confirmed" ? "#34C759" : "#EAB308" }}>
              {data.confidence}
            </span>
            <button onClick={handleFetch} disabled={loading} data-testid="refresh-playing-xi-btn"
              className="text-[10px] text-[#737373] hover:text-[#7C3AED] transition-colors disabled:opacity-50">
              {loading ? <Spinner className="w-3 h-3 animate-spin" /> : "Refresh"}
            </button>
          </div>
        )}
      </div>

      {error && <p className="text-[10px] text-[#FF3B30] mb-2">{error}</p>}
      {impactMsg && !error && (
        <p className="text-[10px] text-[#34C759] mb-2 flex flex-wrap items-center gap-2">
          {impactMsg}
          <button
            type="button"
            onClick={applyPreMatchModel}
            disabled={repredicting}
            data-testid="apply-manual-impact-prematch-btn"
            className="text-[9px] font-bold uppercase px-2 py-1 rounded bg-[#34C759]/20 text-[#34C759] border border-[#34C759]/40 hover:bg-[#34C759]/30 disabled:opacity-50"
          >
            {repredicting ? <Spinner className="w-3 h-3 animate-spin inline" /> : "Apply to model"}
          </button>
        </p>
      )}

      {data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Team 1 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#007AFF]">{team1}</p>
              <p className="text-[9px] text-[#525252] font-mono">Runs | Wkts | Buzz | Luck</p>
            </div>
            {(data.team1_xi || []).map((p, i) => <PlayerRow key={i} player={p} idx={i} />)}
            {(data.team1_xi || []).length === 0 && <p className="text-[10px] text-[#525252]">No XI data</p>}
            {data.team1_xi?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-[#262626] flex justify-between text-[10px] font-mono">
                <span className="text-[#737373]">Team Total Expected</span>
                <span className="text-white font-bold">
                  {data.team1_xi.reduce((s, p) => s + (p.expected_runs || 0), 0).toFixed(0)}r &middot; {data.team1_xi.reduce((s, p) => s + (p.expected_wickets || 0), 0).toFixed(1)}w
                </span>
              </div>
            )}
            {xiNamedCount("team1") > 0 && xiNamedCount("team1") < 11 && (
              <div
                className="mt-2 rounded border border-[#007AFF]/35 bg-[#007AFF]/10 px-2 py-1.5 space-y-1"
                data-testid="team1-complete-xi-picker"
              >
                <p className="text-[8px] text-[#007AFF] font-bold uppercase tracking-wider">
                  Complete Expected XI ({xiNamedCount("team1")}/11) — add next starter from bench
                </p>
                <p className="text-[8px] text-[#737373]">
                  Search the franchise bench (same pool as impact). Saved to DB + pre-match cache for the model and Claude.
                </p>
                <div className="flex flex-wrap gap-1 items-start">
                  <div className="flex-1 min-w-[140px] space-y-1">
                    <input
                      type="text"
                      value={t1FillQuery}
                      onChange={(e) => setT1FillQuery(e.target.value)}
                      placeholder="Search bench…"
                      disabled={fillSaving === "team1" || impactSaving === "team1"}
                      className="w-full text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white placeholder:text-[#525252]"
                      data-testid="team1-fill-xi-search-input"
                    />
                    {t1FillSearching && (
                      <p className="text-[8px] text-[#525252] flex items-center gap-1">
                        <Spinner className="w-3 h-3 animate-spin" /> Searching…
                      </p>
                    )}
                    {t1FillResults.length > 0 && (
                      <ul className="max-h-28 overflow-y-auto rounded border border-[#333] bg-[#0d0d0d] text-[10px]">
                        {t1FillResults.map((b) => (
                          <li key={`fill-${b.name}`}>
                            <button
                              type="button"
                              disabled={fillSaving === "team1"}
                              onClick={() => {
                                setT1FillSelected(b);
                                setT1FillQuery(b.name);
                                setT1FillResults([]);
                              }}
                              className={`w-full text-left px-2 py-1 hover:bg-[#262626] ${
                                t1FillSelected?.name === b.name ? "bg-[#007AFF]/25 text-[#BFDBFE]" : "text-[#E5E5E5]"
                              }`}
                            >
                              {b.name}
                              <span className="text-[#737373] ml-1">· {b.role || "—"}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={fillSaving === "team1" || !t1FillSelected?.name}
                    onClick={() => saveCompleteXiSlot("team1", t1FillSelected?.name || "")}
                    className="text-[9px] font-bold uppercase px-2 py-1 rounded bg-[#007AFF]/25 text-[#93C5FD] hover:bg-[#007AFF]/35 disabled:opacity-50"
                    data-testid="team1-fill-xi-save-btn"
                  >
                    {fillSaving === "team1" ? <Spinner className="w-3 h-3 animate-spin" /> : "Save to XI"}
                  </button>
                </div>
              </div>
            )}
            {data.team1_manual_impact_player?.name && (
              <div className="mt-2 rounded border border-dashed border-[#FFCC00]/35 bg-[#FFCC00]/5 px-2 py-1.5" data-testid="team1-manual-impact-display">
                <p className="text-[8px] text-[#EAB308] font-bold uppercase tracking-wider mb-0.5">IPL Impact (manual)</p>
                {data.team1_manual_impact_swap_out && (
                  <p className="text-[8px] text-[#A1A1AA] mb-1">
                    Swap target (starter replaced in model XI):{" "}
                    <span className="text-white font-mono">{data.team1_manual_impact_swap_out}</span>
                  </p>
                )}
                <PlayerRow player={{ ...data.team1_manual_impact_player, expected_runs: data.team1_manual_impact_player.expected_runs, expected_wickets: data.team1_manual_impact_player.expected_wickets }} idx="IP" />
              </div>
            )}
            <div className="mt-2 space-y-1" data-testid="team1-manual-impact-picker">
              <p className="text-[8px] text-[#737373] uppercase font-bold tracking-wider">
                Manual IPL Impact (12th / depth) — type to search squad
 {xiNamedCount("team1") > 0 && xiNamedCount("team1") < 11 && (
                  <span className="block text-[#737373] font-normal normal-case mt-0.5">
                    You can save the impact pick now; pre-match needs 11 starters — finish “Complete Expected XI” above before Apply to model.
                  </span>
                )}
              </p>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <label className="text-[8px] text-[#525252] uppercase shrink-0">Swap out (optional)</label>
                <select
                  value={t1SwapOut}
                  onChange={(e) => setT1SwapOut(e.target.value)}
                  disabled={
                    impactSaving === "team1" || fillSaving === "team1" || xiStarterNames("team1").length < 11
                  }
                  className="text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white max-w-[200px]"
                  data-testid="team1-impact-swap-select"
                >
                  <option value="">Depth only (12th — not in XI)</option>
                  {xiStarterNames("team1").map((nm, i) => (
                    <option key={`t1-swap-${i}-${nm}`} value={nm}>
                      {nm}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-wrap gap-1 items-start">
                <div className="flex-1 min-w-[140px] space-y-1">
                  <input
                    type="text"
                    value={t1Query}
                    onChange={(e) => setT1Query(e.target.value)}
                    placeholder="e.g. Kohli"
                    disabled={impactSaving === "team1" || fillSaving === "team1"}
                    className="w-full text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white placeholder:text-[#525252]"
                    data-testid="team1-impact-search-input"
                  />
                  {t1Searching && (
                    <p className="text-[8px] text-[#525252] flex items-center gap-1">
                      <Spinner className="w-3 h-3 animate-spin" /> Searching…
                    </p>
                  )}
                  {t1Results.length > 0 && (
                    <ul className="max-h-32 overflow-y-auto rounded border border-[#333] bg-[#0d0d0d] text-[10px]">
                      {t1Results.map((b) => (
                        <li key={b.name}>
                          <button
                            type="button"
                            disabled={impactSaving === "team1" || fillSaving === "team1"}
                            onClick={() => {
                              setT1Selected(b);
                              setT1Query(b.name);
                              setT1Results([]);
                            }}
                            className={`w-full text-left px-2 py-1 hover:bg-[#262626] ${
                              t1Selected?.name === b.name ? "bg-[#7C3AED]/25 text-[#E9D5FF]" : "text-[#E5E5E5]"
                            }`}
                          >
                            {b.name}
                            <span className="text-[#737373] ml-1">· {b.role || "—"}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {t1Query.trim().length >= 2 && !t1Searching && t1Results.length === 0 && (
                    <p className="text-[8px] text-[#737373]">No bench match — try another spelling.</p>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    disabled={impactSaving === "team1" || fillSaving === "team1" || !t1Selected?.name}
                    onClick={() => saveManualImpact("team1", t1Selected?.name || "", t1SwapOut)}
                    className="text-[9px] font-bold uppercase px-2 py-1 rounded bg-[#262626] text-[#E5E5E5] hover:bg-[#333] disabled:opacity-50"
                    data-testid="team1-impact-save-btn"
                  >
                    {impactSaving === "team1" ? <Spinner className="w-3 h-3 animate-spin" /> : "Save"}
                  </button>
                  <button
                    type="button"
                    disabled={impactSaving === "team1" || fillSaving === "team1"}
                    onClick={() => {
                      setT1SwapOut("");
                      saveManualImpact("team1", "");
                    }}
                    className="text-[8px] font-bold uppercase px-2 py-0.5 rounded text-[#737373] hover:text-[#FF3B30]"
                  >
                    Clear
                  </button>
                </div>
              </div>
            </div>
          </div>
          {/* Team 2 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF3B30]">{team2}</p>
              <p className="text-[9px] text-[#525252] font-mono">Runs | Wkts | Buzz | Luck</p>
            </div>
            {(data.team2_xi || []).map((p, i) => <PlayerRow key={i} player={p} idx={i} />)}
            {(data.team2_xi || []).length === 0 && <p className="text-[10px] text-[#525252]">No XI data</p>}
            {data.team2_xi?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-[#262626] flex justify-between text-[10px] font-mono">
                <span className="text-[#737373]">Team Total Expected</span>
                <span className="text-white font-bold">
                  {data.team2_xi.reduce((s, p) => s + (p.expected_runs || 0), 0).toFixed(0)}r &middot; {data.team2_xi.reduce((s, p) => s + (p.expected_wickets || 0), 0).toFixed(1)}w
                </span>
              </div>
            )}
            {xiNamedCount("team2") > 0 && xiNamedCount("team2") < 11 && (
              <div
                className="mt-2 rounded border border-[#FF3B30]/35 bg-[#FF3B30]/10 px-2 py-1.5 space-y-1"
                data-testid="team2-complete-xi-picker"
              >
                <p className="text-[8px] text-[#FF3B30] font-bold uppercase tracking-wider">
                  Complete Expected XI ({xiNamedCount("team2")}/11) — add next starter from bench
                </p>
                <p className="text-[8px] text-[#737373]">
                  Search the franchise bench (same pool as impact). Saved to DB + pre-match cache for the model and Claude.
                </p>
                <div className="flex flex-wrap gap-1 items-start">
                  <div className="flex-1 min-w-[140px] space-y-1">
                    <input
                      type="text"
                      value={t2FillQuery}
                      onChange={(e) => setT2FillQuery(e.target.value)}
                      placeholder="Search bench…"
                      disabled={fillSaving === "team2" || impactSaving === "team2"}
                      className="w-full text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white placeholder:text-[#525252]"
                      data-testid="team2-fill-xi-search-input"
                    />
                    {t2FillSearching && (
                      <p className="text-[8px] text-[#525252] flex items-center gap-1">
                        <Spinner className="w-3 h-3 animate-spin" /> Searching…
                      </p>
                    )}
                    {t2FillResults.length > 0 && (
                      <ul className="max-h-28 overflow-y-auto rounded border border-[#333] bg-[#0d0d0d] text-[10px]">
                        {t2FillResults.map((b) => (
                          <li key={`t2fill-${b.name}`}>
                            <button
                              type="button"
                              disabled={fillSaving === "team2"}
                              onClick={() => {
                                setT2FillSelected(b);
                                setT2FillQuery(b.name);
                                setT2FillResults([]);
                              }}
                              className={`w-full text-left px-2 py-1 hover:bg-[#262626] ${
                                t2FillSelected?.name === b.name ? "bg-[#FF3B30]/25 text-[#FECACA]" : "text-[#E5E5E5]"
                              }`}
                            >
                              {b.name}
                              <span className="text-[#737373] ml-1">· {b.role || "—"}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={fillSaving === "team2" || !t2FillSelected?.name}
                    onClick={() => saveCompleteXiSlot("team2", t2FillSelected?.name || "")}
                    className="text-[9px] font-bold uppercase px-2 py-1 rounded bg-[#FF3B30]/25 text-[#FECACA] hover:bg-[#FF3B30]/35 disabled:opacity-50"
                    data-testid="team2-fill-xi-save-btn"
                  >
                    {fillSaving === "team2" ? <Spinner className="w-3 h-3 animate-spin" /> : "Save to XI"}
                  </button>
                </div>
              </div>
            )}
            {data.team2_manual_impact_player?.name && (
              <div className="mt-2 rounded border border-dashed border-[#FFCC00]/35 bg-[#FFCC00]/5 px-2 py-1.5" data-testid="team2-manual-impact-display">
                <p className="text-[8px] text-[#EAB308] font-bold uppercase tracking-wider mb-0.5">IPL Impact (manual)</p>
                {data.team2_manual_impact_swap_out && (
                  <p className="text-[8px] text-[#A1A1AA] mb-1">
                    Swap target (starter replaced in model XI):{" "}
                    <span className="text-white font-mono">{data.team2_manual_impact_swap_out}</span>
                  </p>
                )}
                <PlayerRow player={{ ...data.team2_manual_impact_player, expected_runs: data.team2_manual_impact_player.expected_runs, expected_wickets: data.team2_manual_impact_player.expected_wickets }} idx="IP" />
              </div>
            )}
            <div className="mt-2 space-y-1" data-testid="team2-manual-impact-picker">
              <p className="text-[8px] text-[#737373] uppercase font-bold tracking-wider">
                Manual IPL Impact (12th / depth) — type to search squad
                {xiNamedCount("team2") > 0 && xiNamedCount("team2") < 11 && (
                  <span className="block text-[#737373] font-normal normal-case mt-0.5">
                    You can save the impact pick now; pre-match needs 11 starters — finish “Complete Expected XI” above before Apply to model.
                  </span>
                )}
              </p>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <label className="text-[8px] text-[#525252] uppercase shrink-0">Swap out (optional)</label>
                <select
                  value={t2SwapOut}
                  onChange={(e) => setT2SwapOut(e.target.value)}
                  disabled={
                    impactSaving === "team2" || fillSaving === "team2" || xiStarterNames("team2").length < 11
                  }
                  className="text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white max-w-[200px]"
                  data-testid="team2-impact-swap-select"
                >
                  <option value="">Depth only (12th — not in XI)</option>
                  {xiStarterNames("team2").map((nm, i) => (
                    <option key={`t2-swap-${i}-${nm}`} value={nm}>
                      {nm}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-wrap gap-1 items-start">
                <div className="flex-1 min-w-[140px] space-y-1">
                  <input
                    type="text"
                    value={t2Query}
                    onChange={(e) => setT2Query(e.target.value)}
                    placeholder="e.g. Russell"
                    disabled={impactSaving === "team2" || fillSaving === "team2"}
                    className="w-full text-[10px] bg-[#1A1A1A] border border-[#333] rounded px-2 py-1 text-white placeholder:text-[#525252]"
                    data-testid="team2-impact-search-input"
                  />
                  {t2Searching && (
                    <p className="text-[8px] text-[#525252] flex items-center gap-1">
                      <Spinner className="w-3 h-3 animate-spin" /> Searching…
                    </p>
                  )}
                  {t2Results.length > 0 && (
                    <ul className="max-h-32 overflow-y-auto rounded border border-[#333] bg-[#0d0d0d] text-[10px]">
                      {t2Results.map((b) => (
                        <li key={b.name}>
                          <button
                            type="button"
                            disabled={impactSaving === "team2" || fillSaving === "team2"}
                            onClick={() => {
                              setT2Selected(b);
                              setT2Query(b.name);
                              setT2Results([]);
                            }}
                            className={`w-full text-left px-2 py-1 hover:bg-[#262626] ${
                              t2Selected?.name === b.name ? "bg-[#7C3AED]/25 text-[#E9D5FF]" : "text-[#E5E5E5]"
                            }`}
                          >
                            {b.name}
                            <span className="text-[#737373] ml-1">· {b.role || "—"}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {t2Query.trim().length >= 2 && !t2Searching && t2Results.length === 0 && (
                    <p className="text-[8px] text-[#737373]">No bench match — try another spelling.</p>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    disabled={impactSaving === "team2" || fillSaving === "team2" || !t2Selected?.name}
                    onClick={() => saveManualImpact("team2", t2Selected?.name || "", t2SwapOut)}
                    className="text-[9px] font-bold uppercase px-2 py-1 rounded bg-[#262626] text-[#E5E5E5] hover:bg-[#333] disabled:opacity-50"
                    data-testid="team2-impact-save-btn"
                  >
                    {impactSaving === "team2" ? <Spinner className="w-3 h-3 animate-spin" /> : "Save"}
                  </button>
                  <button
                    type="button"
                    disabled={impactSaving === "team2" || fillSaving === "team2"}
                    onClick={() => {
                      setT2SwapOut("");
                      saveManualImpact("team2", "");
                    }}
                    className="text-[8px] font-bold uppercase px-2 py-0.5 rounded text-[#737373] hover:text-[#FF3B30]"
                  >
                    Clear
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : !loading ? (
        <div className="text-center py-6" data-testid="playing-xi-empty">
          <Lightning weight="duotone" className="w-8 h-8 text-[#333] mx-auto mb-2" />
          <p className="text-xs text-[#525252]">Click "Fetch Playing XI" to get expected lineups with performance predictions</p>
        </div>
      ) : null}
    </div>
  );
}
