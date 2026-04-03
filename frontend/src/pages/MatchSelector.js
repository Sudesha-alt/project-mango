import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import { Lightning, MapPin, Clock, CaretRight, Broadcast, Trophy, CalendarBlank, ArrowsClockwise, Spinner } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";

export default function MatchSelector() {
  const navigate = useNavigate();
  const { schedule, loading, apiStatus, fetchStatus, loadSchedule } = useMatchData();
  const [tab, setTab] = useState("upcoming");
  const [scheduleLoading, setScheduleLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
    loadSchedule();
  }, [fetchStatus, loadSchedule]);

  const handleLoadSchedule = async (force = false) => {
    setScheduleLoading(true);
    await loadSchedule(force);
    setScheduleLoading(false);
  };

  const selectMatch = (match) => {
    const status = (match.status || "").toLowerCase();
    if (status === "live" || status === "in progress") {
      navigate(`/live/${match.matchId}`);
    } else if (status === "completed" || status === "result") {
      navigate(`/post-match/${match.matchId}`);
    } else {
      navigate(`/pre-match/${match.matchId}`);
    }
  };

  const getMatchesForTab = () => {
    if (!schedule.matches?.length) return [];
    if (tab === "live") return schedule.live || [];
    if (tab === "upcoming") return schedule.upcoming || [];
    if (tab === "completed") return schedule.completed || [];
    return schedule.matches;
  };

  const matches = getMatchesForTab();

  return (
    <div data-testid="match-selector-page" className="min-h-screen">
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#007AFF]/10 to-transparent" />
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 pt-12 pb-8 relative">
          <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-2">IPL 2026</p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed', sans-serif" }} data-testid="page-title">
            Gamble Consultant
          </h1>
          <p className="text-base text-[#A1A1AA] mt-2 max-w-xl" style={{ fontFamily: "'DM Sans', sans-serif" }}>
            Real-time match predictions powered by ensemble probability models, GPT analysis, and live odds tracking.
          </p>
          {!schedule.loaded && (
            <button
              onClick={() => handleLoadSchedule(false)}
              disabled={scheduleLoading}
              data-testid="load-schedule-btn"
              className="mt-4 flex items-center gap-2 bg-[#007AFF] text-white px-5 py-2.5 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-[#0066DD] transition-colors disabled:opacity-50"
            >
              {scheduleLoading ? <><Spinner className="w-4 h-4 animate-spin" /> Loading IPL 2026 Schedule...</> : <><CalendarBlank weight="bold" className="w-4 h-4" /> Load IPL 2026 Schedule</>}
            </button>
          )}
          {schedule.loaded && (
            <div className="mt-4 flex items-center gap-3">
              <span className="text-xs text-[#22C55E] font-mono">{schedule.total || 0} matches loaded</span>
              <button onClick={() => handleLoadSchedule(true)} data-testid="refresh-schedule-btn" className="text-[10px] text-[#A1A1AA] hover:text-white flex items-center gap-1 transition-colors">
                <ArrowsClockwise weight="bold" className="w-3 h-3" /> Refresh
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
        <div className="flex gap-1 mb-6" data-testid="match-tabs">
          {[
            { key: "live", label: "Live", icon: Broadcast, count: schedule.live?.length || 0 },
            { key: "upcoming", label: "Upcoming", icon: CalendarBlank, count: schedule.upcoming?.length || 0 },
            { key: "completed", label: "Completed", icon: Trophy, count: schedule.completed?.length || 0 },
          ].map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)} data-testid={`tab-${t.key}`}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-md transition-colors flex items-center gap-1.5 ${
                tab === t.key ? "bg-[#007AFF] text-white" : "bg-[#141414] text-[#A1A1AA] hover:bg-[#1E1E1E] hover:text-white"
              }`}>
              <t.icon weight={tab === t.key ? "fill" : "bold"} className="w-3.5 h-3.5" />
              {t.label}
              {t.count > 0 && <span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full ${tab === t.key ? "bg-white/20" : "bg-white/10"}`}>{t.count}</span>}
            </button>
          ))}
        </div>

        {(loading || scheduleLoading) && (
          <div className="flex items-center justify-center py-20" data-testid="loading-state">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-[#A1A1AA]">Loading IPL 2026 schedule via Web Search...</p>
            </div>
          </div>
        )}

        {!loading && !scheduleLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-12" data-testid="match-grid">
            {matches.map((match, i) => {
              const status = (match.status || "").toLowerCase();
              const isLive = status === "live" || status === "in progress";
              const isCompleted = status === "completed" || status === "result";
              return (
                <button key={match.matchId || i} onClick={() => selectMatch(match)} data-testid={`match-card-${i}`}
                  className="bg-[#141414] border border-white/10 rounded-md p-4 text-left hover:border-[#007AFF]/40 hover:bg-[#1A1A1A] transition-all group">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {isLive && <Badge className="bg-[#FF3B30] text-white text-[10px] px-1.5 py-0 rounded animate-live-pulse">LIVE</Badge>}
                      {isCompleted && <Badge className="bg-[#22C55E]/20 text-[#22C55E] text-[10px] px-1.5 py-0 rounded">DONE</Badge>}
                      <span className="text-[10px] font-mono text-[#71717A]">#{match.match_number || i + 1}</span>
                    </div>
                    <CaretRight weight="bold" className="w-4 h-4 text-[#71717A] group-hover:text-[#007AFF] transition-colors" />
                  </div>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-lg font-bold uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{match.team1Short || "?"}</p>
                      <p className="text-[10px] text-[#A1A1AA] truncate max-w-[120px]">{match.team1}</p>
                    </div>
                    <span className="text-xs font-bold text-[#71717A] px-2">VS</span>
                    <div className="text-right">
                      <p className="text-lg font-bold uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{match.team2Short || "?"}</p>
                      <p className="text-[10px] text-[#A1A1AA] truncate max-w-[120px]">{match.team2}</p>
                    </div>
                  </div>
                  {match.score && <p className="text-xs font-mono text-[#A1A1AA] bg-[#1E1E1E] rounded px-2 py-1 mb-2 truncate tabular-nums" data-testid={`match-score-${i}`}>{match.score}</p>}
                  {match.winner && <p className="text-xs text-[#22C55E] mb-2 font-medium">{match.winner} won</p>}
                  <div className="flex items-center justify-between text-[10px] text-[#71717A]">
                    {match.venue && <span className="flex items-center gap-1 truncate"><MapPin weight="bold" className="w-3 h-3 flex-shrink-0" />{match.venue.length > 35 ? match.venue.slice(0, 35) + "..." : match.venue}</span>}
                    {match.dateTimeGMT && <span className="flex items-center gap-1 flex-shrink-0"><Clock weight="bold" className="w-3 h-3" />{new Date(match.dateTimeGMT).toLocaleDateString()}</span>}
                  </div>
                </button>
              );
            })}

            {matches.length === 0 && !loading && (
              <div className="col-span-full text-center py-16" data-testid="empty-state">
                <Lightning weight="duotone" className="w-12 h-12 text-[#333] mx-auto mb-4" />
                <p className="text-sm text-[#71717A] mb-2">
                  {!schedule.loaded ? "Click 'Load IPL 2026 Schedule' to fetch all matches." : `No ${tab} matches found.`}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
