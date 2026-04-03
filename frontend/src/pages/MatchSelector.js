import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import { Lightning, MapPin, Clock, CaretRight, Broadcast } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";

export default function MatchSelector() {
  const navigate = useNavigate();
  const { liveMatches, fixtures, loading, fetchLiveMatches, apiStatus } = useMatchData();
  const [tab, setTab] = useState("live");

  useEffect(() => {
    fetchLiveMatches();
  }, [fetchLiveMatches]);

  const selectMatch = (matchId, isLive) => {
    if (isLive) {
      navigate(`/live/${matchId}`);
    } else {
      navigate(`/pre-match/${matchId}`);
    }
  };

  return (
    <div data-testid="match-selector-page" className="min-h-screen">
      {/* Hero */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#007AFF]/10 to-transparent" />
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 pt-12 pb-8 relative">
          <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-2">IPL 2026</p>
          <h1
            className="text-4xl sm:text-5xl lg:text-6xl font-black uppercase tracking-tight"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
            data-testid="page-title"
          >
            PPL Board
          </h1>
          <p className="text-base text-[#A1A1AA] mt-2 max-w-xl" style={{ fontFamily: "'DM Sans', sans-serif" }}>
            Real-time match predictions powered by ensemble probability models, live odds tracking, and AI analysis.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
        <div className="flex gap-1 mb-6" data-testid="match-tabs">
          {["live", "upcoming", "completed"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              data-testid={`tab-${t}`}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-md transition-colors ${
                tab === t ? "bg-[#007AFF] text-white" : "bg-[#141414] text-[#A1A1AA] hover:bg-[#1E1E1E] hover:text-white"
              }`}
            >
              {t === "live" && <Broadcast weight="fill" className="inline w-3.5 h-3.5 mr-1.5" />}
              {t}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20" data-testid="loading-state">
            <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Match Cards */}
        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-12" data-testid="match-grid">
            {(tab === "live"
              ? liveMatches.filter((m) => m.isLive)
              : tab === "upcoming"
              ? liveMatches.filter((m) => !m.isLive && !m.matchEnded)
              : tab === "completed"
              ? liveMatches.filter((m) => m.matchEnded)
              : liveMatches
            ).length === 0 && tab === "live" && liveMatches.length > 0
              ? liveMatches
              : (tab === "live"
                  ? liveMatches.filter((m) => m.isLive).length > 0
                    ? liveMatches.filter((m) => m.isLive)
                    : liveMatches
                  : tab === "upcoming"
                  ? liveMatches.filter((m) => !m.isLive && !m.matchEnded)
                  : liveMatches.filter((m) => m.matchEnded)
                )
            .map((match, i) => (
              <button
                key={match.matchId || i}
                onClick={() => selectMatch(match.matchId, match.isLive)}
                data-testid={`match-card-${i}`}
                className="bg-[#141414] border border-white/10 rounded-md p-4 text-left hover:border-[#007AFF]/40 hover:bg-[#1A1A1A] transition-all group"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {match.isLive && (
                      <Badge variant="default" className="bg-[#FF3B30] text-white text-[10px] px-1.5 py-0 rounded animate-live-pulse">
                        LIVE
                      </Badge>
                    )}
                    <span className="text-[10px] font-mono text-[#71717A]">{match.matchType || "T20"}</span>
                  </div>
                  <CaretRight weight="bold" className="w-4 h-4 text-[#71717A] group-hover:text-[#007AFF] transition-colors" />
                </div>

                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-lg font-bold uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                      {match.team1Short || match.team1?.slice(0, 3).toUpperCase()}
                    </p>
                    <p className="text-[10px] text-[#A1A1AA] truncate max-w-[120px]">{match.team1}</p>
                  </div>
                  <div className="text-center px-2">
                    <span className="text-xs font-bold text-[#71717A]">VS</span>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                      {match.team2Short || match.team2?.slice(0, 3).toUpperCase()}
                    </p>
                    <p className="text-[10px] text-[#A1A1AA] truncate max-w-[120px]">{match.team2}</p>
                  </div>
                </div>

                {match.score && (
                  <p className="text-xs font-mono text-[#A1A1AA] bg-[#1E1E1E] rounded px-2 py-1 mb-2 truncate tabular-nums" data-testid={`match-score-${i}`}>
                    {match.score}
                  </p>
                )}

                <div className="flex items-center justify-between text-[10px] text-[#71717A]">
                  {match.venue && (
                    <span className="flex items-center gap-1 truncate">
                      <MapPin weight="bold" className="w-3 h-3" />
                      {match.venue.length > 30 ? match.venue.slice(0, 30) + "..." : match.venue}
                    </span>
                  )}
                  {match.dateTimeGMT && (
                    <span className="flex items-center gap-1">
                      <Clock weight="bold" className="w-3 h-3" />
                      {new Date(match.dateTimeGMT).toLocaleDateString()}
                    </span>
                  )}
                </div>

                {match.status && (
                  <p className="text-[10px] text-[#A1A1AA] mt-2 italic truncate">{match.status}</p>
                )}

                {match.probabilities?.ensemble && (
                  <div className="mt-3 pt-2 border-t border-white/5">
                    <div className="flex gap-1 h-2 rounded-full overflow-hidden">
                      <div className="bg-[#007AFF] rounded-l-full" style={{ width: `${match.probabilities.ensemble * 100}%` }} />
                      <div className="bg-[#FF3B30] rounded-r-full" style={{ width: `${(1 - match.probabilities.ensemble) * 100}%` }} />
                    </div>
                  </div>
                )}
              </button>
            ))}

            {/* Empty State */}
            {liveMatches.length === 0 && !loading && (
              <div className="col-span-full text-center py-16" data-testid="empty-state">
                <Lightning weight="duotone" className="w-12 h-12 text-[#333] mx-auto mb-4" />
                <p className="text-sm text-[#71717A] mb-2">
                  {apiStatus?.apiStatus === "blocked"
                    ? `CricAPI is rate-limited. Auto-retry in ${Math.ceil((apiStatus.blockRemaining || 0) / 60)} min.`
                    : "No matches available. API may be rate-limited."}
                </p>
                <p className="text-xs text-[#71717A]">
                  CricAPI free tier allows limited calls. Data will refresh automatically when available.
                </p>
                {apiStatus?.apiStatus === "blocked" && (
                  <div className="mt-3 flex items-center justify-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#EAB308] animate-live-pulse" />
                    <span className="text-xs text-[#EAB308] font-mono tabular-nums">
                      Cooldown: {apiStatus.blockRemaining || 0}s
                    </span>
                  </div>
                )}
                <button
                  onClick={() => fetchLiveMatches()}
                  data-testid="retry-btn"
                  className="mt-4 px-4 py-2 text-xs font-bold uppercase bg-[#007AFF] text-white rounded-md hover:bg-[#0066DD] transition-colors"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
