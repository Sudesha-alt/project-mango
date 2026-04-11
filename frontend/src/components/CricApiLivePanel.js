import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Lightning, Spinner, ArrowsClockwise, Warning, Database } from "@phosphor-icons/react";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

export default function CricApiLivePanel() {
  const [data, setData] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchUsage = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/cricket-api/usage`);
      setUsage(res.data);
    } catch (e) {
      console.error("Usage fetch error:", e);
    }
  }, []);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  const handleFetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/cricket-api/fetch-live`);
      if (res.data.error) {
        setError(res.data.error);
      } else {
        setData(res.data);
        setUsage(prev => ({
          ...prev,
          hits: res.data.api_info?.hits_today || prev?.hits,
          remaining: res.data.api_info?.hits_remaining || prev?.remaining,
          last_fetched: res.data.api_info?.fetched_at,
        }));
      }
    } catch (e) {
      setError("Failed to reach CricketData.org API");
    }
    setLoading(false);
  };

  const hitsUsed = usage?.hits || 0;
  const hitsLimit = usage?.limit || 100;
  const hitsRemaining = usage?.remaining ?? (hitsLimit - hitsUsed);
  const hitsPct = (hitsUsed / hitsLimit) * 100;

  return (
    <div data-testid="cricapi-live-panel" className="space-y-3">
      {/* API Usage Bar */}
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1.5">
            <Database weight="bold" className="w-3.5 h-3.5" /> CricketData.org API
          </p>
          <span className={`text-[10px] font-mono font-bold ${hitsRemaining < 10 ? "text-[#FF3B30]" : hitsRemaining < 30 ? "text-[#FFCC00]" : "text-[#34C759]"}`}
            data-testid="api-hits-counter">
            {hitsUsed} / {hitsLimit} hits used
          </span>
        </div>
        <div className="h-1.5 bg-[#262626] rounded-full overflow-hidden mb-2">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${hitsPct}%`,
              backgroundColor: hitsRemaining < 10 ? "#FF3B30" : hitsRemaining < 30 ? "#FFCC00" : "#34C759"
            }}
          />
        </div>
        <div className="flex items-center justify-between text-[9px] text-[#737373]">
          <span>{hitsRemaining} remaining today</span>
          {usage?.last_fetched && (
            <span>Last: {new Date(usage.last_fetched).toLocaleTimeString()}</span>
          )}
        </div>
      </div>

      {/* Fetch Button */}
      <button
        onClick={handleFetch}
        disabled={loading || hitsRemaining <= 0}
        data-testid="fetch-cricapi-btn"
        className="w-full flex items-center justify-center gap-2 bg-[#007AFF] text-white py-3 rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-blue-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {loading ? (
          <><Spinner className="w-4 h-4 animate-spin" /> Fetching Live Data...</>
        ) : hitsRemaining <= 0 ? (
          <><Warning weight="fill" className="w-4 h-4" /> Daily Limit Reached</>
        ) : (
          <><Lightning weight="fill" className="w-4 h-4" /> Fetch Live IPL Details (1 API hit)</>
        )}
      </button>

      {error && (
        <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 rounded-lg p-3 text-xs text-[#FF3B30]" data-testid="cricapi-error">
          {error}
        </div>
      )}

      {/* Match Results */}
      {data && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold">
              IPL 2026 Live Matches ({data.count})
            </p>
            <span className="text-[9px] text-[#737373] font-mono">{data.all_matches_count} total matches in API</span>
          </div>

          {data.count === 0 && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 text-center">
              <p className="text-xs text-[#A3A3A3]">No live IPL matches at this moment</p>
              <p className="text-[10px] text-[#737373] mt-1">Check back during match hours</p>
            </div>
          )}

          {data.matches?.map((match, idx) => (
            <MatchCard key={idx} match={match} />
          ))}
        </div>
      )}

      {!data && !loading && (
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 text-center">
          <ArrowsClockwise weight="duotone" className="w-8 h-8 text-[#007AFF] mx-auto mb-2" />
          <p className="text-xs text-[#A3A3A3]">Click the button to fetch live IPL data</p>
          <p className="text-[10px] text-[#737373] mt-1">Each click uses 1 API hit from your daily quota</p>
        </div>
      )}
    </div>
  );
}

function MatchCard({ match }) {
  const isLive = match.matchStarted && !match.matchEnded;
  const [expanded, setExpanded] = useState(isLive);

  return (
    <div
      data-testid={`cricapi-match-${match.cricapi_id}`}
      className={`bg-[#141414] border rounded-lg overflow-hidden ${
        isLive ? "border-[#34C759]/40" : "border-[#262626]"
      }`}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors"
      >
        <div className="text-left">
          <div className="flex items-center gap-2">
            {isLive && <span className="w-2 h-2 rounded-full bg-[#34C759] animate-pulse" />}
            <span className="text-xs font-bold text-white" style={{ fontFamily: "'Barlow Condensed'" }}>
              {match.team1} vs {match.team2}
            </span>
          </div>
          <p className="text-[10px] text-[#737373] mt-0.5">{match.venue}</p>
        </div>
        <div className="text-right">
          <p className={`text-[10px] font-bold ${isLive ? "text-[#34C759]" : match.matchEnded ? "text-[#A3A3A3]" : "text-[#FFCC00]"}`}>
            {isLive ? "LIVE" : match.matchEnded ? "COMPLETED" : "UPCOMING"}
          </p>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-[#262626]">
          {/* Status */}
          <p className="text-xs text-[#A3A3A3] pt-2" style={{ fontFamily: "'IBM Plex Sans'" }}>{match.status}</p>

          {/* Innings Scores */}
          {match.innings?.map((inn, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-[#262626] last:border-0">
              <span className="text-[10px] text-[#A3A3A3] flex-1">{inn.inning_label}</span>
              <span className="text-sm font-bold font-mono text-white">
                {inn.runs}/{inn.wickets}
                <span className="text-[#737373] text-[10px] ml-1">({inn.overs} ov)</span>
              </span>
            </div>
          ))}

          {/* Target info for 2nd innings */}
          {match.target && match.current_innings >= 2 && (
            <div className="bg-[#0A0A0A] rounded px-3 py-2">
              <p className="text-[10px] text-[#737373]">
                Target: <span className="text-white font-mono font-bold">{match.target}</span>
                {match.current_score && (
                  <span className="ml-3">
                    Need: <span className="text-[#FFCC00] font-mono font-bold">
                      {Math.max(0, match.target - match.current_score.runs)}
                    </span> from{" "}
                    <span className="text-[#A3A3A3] font-mono">
                      {Math.max(0, 120 - Math.floor(match.current_score.overs * 6 + (match.current_score.overs % 1) * 10))} balls
                    </span>
                  </span>
                )}
              </p>
            </div>
          )}

          <p className="text-[9px] text-[#737373] font-mono text-right">Source: cricketdata.org | ID: {match.cricapi_id?.slice(0, 12)}</p>
        </div>
      )}
    </div>
  );
}
