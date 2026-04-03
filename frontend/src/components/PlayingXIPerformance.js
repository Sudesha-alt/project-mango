import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Lightning, TrendUp, TrendDown, Minus, UsersThree } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function PlayingXIPerformance({ matchId, team1, team2 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadCached = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`);
        const pred = (res.data.predictions || []).find(p => p.matchId === matchId);
        if (pred?.playing_xi?.team1_xi?.length > 0) {
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
      const res = await axios.post(`${API}/matches/${matchId}/playing-xi`);
      if (res.data?.team1_xi?.length > 0) {
        setData(res.data);
      } else {
        setError("No Playing XI data available yet.");
      }
    } catch (e) {
      setError("Failed to fetch Playing XI. Try again.");
    }
    setLoading(false);
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

  const PlayerRow = ({ player, idx }) => {
    const luck = luckLabel(player.luck_factor);
    return (
      <div className={`flex items-center gap-2 py-1.5 ${idx > 0 ? "border-t border-[#1E1E1E]" : ""}`}>
        <span className="w-5 text-[10px] text-[#525252] font-mono text-right">{idx + 1}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-white truncate">{player.name}</span>
            {player.is_captain && <span className="text-[8px] px-1 py-0 bg-[#FFCC00]/20 text-[#FFCC00] rounded font-bold">C</span>}
            {player.is_overseas && <span className="text-[8px] px-1 py-0 bg-[#007AFF]/20 text-[#007AFF] rounded">OS</span>}
          </div>
          <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: roleColor(player.role) }}>
            {player.role}
          </span>
        </div>
        <div className="text-right space-y-0.5 flex-shrink-0">
          <div className="flex items-center gap-2 justify-end">
            <span className="text-[10px] text-[#A1A1AA] font-mono" data-testid="player-expected-runs">
              {player.expected_runs}r
            </span>
            <span className="text-[10px] text-[#A1A1AA] font-mono" data-testid="player-expected-wickets">
              {player.expected_wickets}w
            </span>
            {luck && (
              <span className="flex items-center gap-0.5" title={`Luck: ${luck.label} (${player.luck_factor})`}>
                <luck.icon weight="bold" className="w-2.5 h-2.5" style={{ color: luck.color }} />
              </span>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="playing-xi-performance">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] flex items-center gap-1.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
          <UsersThree weight="fill" className="w-4 h-4 text-[#7C3AED]" />
          Expected Playing XI + Performance
          <InfoTooltip text="Predicted or confirmed Playing XI for this match. Expected runs and wickets are calculated from season stats with a 'luck biasness' variance (+-15%) for realistic projections. Green arrow = lucky day, Red = unlucky." />
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
              <p className="text-[9px] text-[#525252] font-mono">Runs | Wkts | Luck</p>
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
              <p className="text-[9px] text-[#525252] font-mono">Runs | Wkts | Luck</p>
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
