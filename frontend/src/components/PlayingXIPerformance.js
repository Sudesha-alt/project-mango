import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Lightning, TrendUp, TrendDown, Minus, UsersThree, ChatDots } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

export default function PlayingXIPerformance({ matchId, team1, team2 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadCached = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`);
        const pred = (res.data.predictions || []).find(p => p.matchId === matchId);
        if (pred?.playing_xi && ((pred.playing_xi.team1_xi?.length > 0) || (pred.playing_xi.team2_xi?.length > 0))) {
          setData(pred.playing_xi);
        }
      } catch (e) { /* ignore */ }
    };
    loadCached();
  }, [matchId]);

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
            setData(d);
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
    return (
      <div className={`py-1.5 ${idx > 0 ? "border-t border-[#1E1E1E]" : ""}`}>
        <div className="flex items-center gap-2">
          <span className="w-5 text-[10px] text-[#525252] font-mono text-right">{idx + 1}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-white truncate">{player.name}</span>
              {player.is_captain && <span className="text-[8px] px-1 py-0 bg-[#FFCC00]/20 text-[#FFCC00] rounded font-bold">C</span>}
              {player.is_overseas && <span className="text-[8px] px-1 py-0 bg-[#007AFF]/20 text-[#007AFF] rounded">OS</span>}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: roleColor(player.role) }}>
                {player.role}
              </span>
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
                {player.expected_runs}r
              </span>
              <span className="text-[10px] text-[#A1A1AA] font-mono" data-testid="player-expected-wickets">
                {player.expected_wickets}w
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
          <InfoTooltip text="Expected XI from each team’s last completed IPL match (SportMonks lineup), with squad merge when DB squads match. Buzz / expected runs load when enriched from prediction cache. Click a buzz badge for detail." />
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
