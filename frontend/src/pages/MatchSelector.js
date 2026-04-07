import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useMatchData } from "@/hooks/useMatchData";
import { Lightning, MapPin, Clock, CaretRight, Broadcast, Trophy, CalendarBlank, ArrowsClockwise, Spinner, Target, TrendUp, TrendDown, Minus, UsersThree } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import CricApiLivePanel from "@/components/CricApiLivePanel";
import InfoTooltip from "@/components/InfoTooltip";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function MatchSelector() {
  const navigate = useNavigate();
  const { schedule, loading, apiStatus, fetchStatus, loadSchedule } = useMatchData();
  const [tab, setTab] = useState("upcoming");
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [predictions, setPredictions] = useState({});
  const [predictingAll, setPredictingAll] = useState(false);
  const [predictProgress, setPredictProgress] = useState({ done: 0, total: 0 });
  const [repredicting, setRepredicting] = useState(false);
  const [repredictStatus, setRepredictStatus] = useState(null);
  const [refreshingLive, setRefreshingLive] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);

  useEffect(() => {
    fetchStatus();
    loadSchedule();
  }, [fetchStatus, loadSchedule]);

  // Auto-discover live matches on mount (silent background check)
  useEffect(() => {
    const discoverLive = async () => {
      try {
        const res = await axios.post(`${API}/matches/refresh-live-status`);
        const data = res.data;
        if (data.promoted_count > 0 || data.completed_count > 0) {
          // Reload schedule to reflect changes
          await loadSchedule();
          // Auto-switch to Live tab if matches were found
          if (data.promoted_count > 0 || data.still_live_count > 0) {
            setTab("live");
          }
        }
      } catch (e) { /* silent */ }
    };
    discoverLive();
  }, [loadSchedule]);

  // Load cached predictions on mount
  useEffect(() => {
    const loadPredictions = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`);
        const map = {};
        for (const p of res.data.predictions || []) {
          map[p.matchId] = p;
        }
        setPredictions(map);
      } catch (e) { /* ignore */ }
    };
    loadPredictions();
  }, []);

  const handleLoadSchedule = async (force = false) => {
    setScheduleLoading(true);
    await loadSchedule(force);
    setScheduleLoading(false);
  };

  const handleRefreshLiveStatus = async () => {
    setRefreshingLive(true);
    setRefreshResult(null);
    try {
      const res = await axios.post(`${API}/matches/refresh-live-status`);
      setRefreshResult(res.data);
      // Reload schedule to reflect status changes
      await loadSchedule();
    } catch (e) {
      console.error("Refresh live status error:", e);
    }
    setRefreshingLive(false);
  };

  const handlePredictAll = async () => {
    const upcoming = schedule.upcoming || [];
    const unpredicted = upcoming.filter(m => !predictions[m.matchId]);
    if (unpredicted.length === 0) return;

    setPredictingAll(true);
    setPredictProgress({ done: 0, total: unpredicted.length });

    for (let i = 0; i < unpredicted.length; i++) {
      try {
        const res = await axios.post(`${API}/matches/${unpredicted[i].matchId}/pre-match-predict`);
        if (res.data && !res.data.error) {
          setPredictions(prev => ({ ...prev, [unpredicted[i].matchId]: res.data }));
        }
      } catch (e) { /* skip failed */ }
      setPredictProgress({ done: i + 1, total: unpredicted.length });
    }

    setPredictingAll(false);
  };

  const handleRepredictAll = async () => {
    setRepredicting(true);
    try {
      await axios.post(`${API}/predictions/repredict-all`);
      // Poll status every 5s
      const poll = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/predictions/repredict-status`);
          setRepredictStatus(res.data);
          if (!res.data.running) {
            clearInterval(poll);
            setRepredicting(false);
            // Reload predictions
            const predRes = await axios.get(`${API}/predictions/upcoming`);
            const map = {};
            for (const p of predRes.data.predictions || []) map[p.matchId] = p;
            setPredictions(map);
          }
        } catch (e) { /* ignore */ }
      }, 5000);
    } catch (e) {
      setRepredicting(false);
    }
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
  const upcomingCount = schedule.upcoming?.length || 0;
  const predictedCount = Object.keys(predictions).length;
  const unpredictedCount = Math.max(0, upcomingCount - predictedCount);

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white py-6">
      <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black uppercase tracking-tight"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
            Predictability
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-2" style={{ fontFamily: "'IBM Plex Sans'" }}>
            IPL 2026 &middot; {schedule.total || 0} matches &middot; Powered by Claude Opus
          </p>
          {!schedule.loaded && (
            <button onClick={() => handleLoadSchedule(true)} disabled={scheduleLoading} data-testid="load-schedule-btn"
              className="mt-4 inline-flex items-center gap-2 bg-[#007AFF] text-white px-6 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-blue-600 disabled:opacity-50">
              {scheduleLoading ? <><Spinner className="w-4 h-4 animate-spin" /> Loading...</> : <><ArrowsClockwise weight="bold" className="w-4 h-4" /> Load IPL 2026 Schedule</>}
            </button>
          )}
        </div>

        {/* CricketData.org Live Panel — only on Live tab */}
        {tab === "live" && (
          <div className="mb-6">
            <CricApiLivePanel />
          </div>
        )}

        {/* Tabs + Predict All */}
        <div className="flex items-center justify-between mb-6 gap-4">
          <div className="flex gap-1" data-testid="match-tabs">
            {[
              { key: "live", label: "Live", icon: Broadcast, count: schedule.live?.length || 0 },
              { key: "upcoming", label: "Upcoming", icon: CalendarBlank, count: upcomingCount },
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

          {tab === "upcoming" && upcomingCount > 0 && (
            <div className="flex gap-2">
              {predictedCount > 0 && (
                <button onClick={handleRepredictAll} disabled={repredicting || predictingAll} data-testid="repredict-all-btn"
                  className="flex items-center gap-2 bg-[#1A0A2E] border border-[#7C3AED]/30 text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:border-[#7C3AED] transition-colors disabled:opacity-40">
                  {repredicting ? (
                    <><Spinner className="w-3.5 h-3.5 animate-spin" /> Re-Predicting {repredictStatus?.completed || 0}/{repredictStatus?.total || "?"}...</>
                  ) : (
                    <><ArrowsClockwise weight="bold" className="w-3.5 h-3.5 text-[#7C3AED]" /> Re-Predict All</>
                  )}
                </button>
              )}
              <button onClick={handlePredictAll} disabled={predictingAll || unpredictedCount === 0 || repredicting} data-testid="predict-all-btn"
                className="flex items-center gap-2 bg-[#141414] border border-[#262626] text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:border-[#007AFF] transition-colors disabled:opacity-40">
                {predictingAll ? (
                  <><Spinner className="w-3.5 h-3.5 animate-spin" /> Predicting {predictProgress.done}/{predictProgress.total}...</>
                ) : unpredictedCount === 0 ? (
                  <><Target weight="fill" className="w-3.5 h-3.5 text-[#34C759]" /> All Predicted</>
                ) : (
                  <><Target weight="fill" className="w-3.5 h-3.5 text-[#007AFF]" /> Predict All ({unpredictedCount} left)</>
                )}
              </button>
            </div>
          )}

          {tab === "live" && (
            <button onClick={handleRefreshLiveStatus} disabled={refreshingLive} data-testid="refresh-live-btn"
              className="flex items-center gap-2 bg-[#141414] border border-[#FF3B30]/30 text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:border-[#FF3B30] transition-colors disabled:opacity-50">
              {refreshingLive ? (
                <><Spinner className="w-3.5 h-3.5 animate-spin" /> Checking...</>
              ) : (
                <><ArrowsClockwise weight="bold" className="w-3.5 h-3.5 text-[#FF3B30]" /> Refresh Matches</>
              )}
            </button>
          )}
        </div>

        {(loading || scheduleLoading) && (
          <div className="flex items-center justify-center py-20" data-testid="loading-state">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-[#A1A1AA]">Loading IPL 2026 schedule via Web Search...</p>
            </div>
          </div>
        )}

        {repredicting && repredictStatus && (
          <div className="mb-4 bg-[#1A0A2E] border border-[#7C3AED]/30 rounded-md p-3 flex items-center gap-3" data-testid="repredict-banner">
            <Spinner className="w-4 h-4 animate-spin text-[#7C3AED]" />
            <div className="flex-1">
              <p className="text-xs font-bold text-white">Re-Predicting All Matches with Fresh Data + Playing XI</p>
              <p className="text-[10px] text-[#A1A1AA]">
                {repredictStatus.completed}/{repredictStatus.total} complete &middot; {repredictStatus.failed} failed &middot; Current: {repredictStatus.current_match}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs font-mono text-[#7C3AED]">{repredictStatus.total > 0 ? Math.round(repredictStatus.completed / repredictStatus.total * 100) : 0}%</p>
            </div>
          </div>
        )}

        {refreshResult && (
          <div className={`mb-4 rounded-md p-3 flex items-center gap-3 ${
            refreshResult.promoted_count > 0 ? "bg-[#FF3B30]/10 border border-[#FF3B30]/30" :
            refreshResult.completed_count > 0 ? "bg-[#22C55E]/10 border border-[#22C55E]/30" :
            "bg-[#141414] border border-white/10"
          }`} data-testid="refresh-result-banner">
            {refreshResult.promoted_count > 0 ? (
              <Broadcast weight="fill" className="w-4 h-4 text-[#FF3B30]" />
            ) : refreshResult.completed_count > 0 ? (
              <Trophy weight="fill" className="w-4 h-4 text-[#22C55E]" />
            ) : (
              <Broadcast weight="fill" className="w-4 h-4 text-[#A1A1AA]" />
            )}
            <div className="flex-1">
              {refreshResult.promoted_count > 0 && (
                <p className="text-xs font-bold text-[#FF3B30]">
                  {refreshResult.promoted_count} match{refreshResult.promoted_count > 1 ? "es" : ""} now LIVE!
                </p>
              )}
              {refreshResult.newly_promoted?.map((m, i) => (
                <p key={`p-${i}`} className="text-[10px] text-[#A1A1AA]">
                  {m.team1} vs {m.team2} — {m.score || m.status}
                </p>
              ))}
              {refreshResult.completed_count > 0 && (
                <p className="text-xs font-bold text-[#22C55E]">
                  {refreshResult.completed_count} match{refreshResult.completed_count > 1 ? "es" : ""} completed
                </p>
              )}
              {refreshResult.completed?.map((m, i) => (
                <p key={`c-${i}`} className="text-[10px] text-[#A1A1AA]">
                  {m.team1} vs {m.team2} — {m.winner ? `${m.winner} won` : m.result || "Completed"}
                </p>
              ))}
              {refreshResult.still_live_count > 0 && (
                <p className="text-xs text-[#A1A1AA]">
                  {refreshResult.still_live_count} match{refreshResult.still_live_count !== 1 ? "es" : ""} still live
                </p>
              )}
              {!refreshResult.promoted_count && !refreshResult.completed_count && !refreshResult.still_live_count && (
                <p className="text-xs text-[#737373]">
                  {refreshResult.message || "No live IPL matches found right now"}
                </p>
              )}
              <p className="text-[9px] text-[#525252] mt-1">
                SportMonks: {refreshResult.sportmonks_live || 0} &middot; CricAPI: {refreshResult.cricapi_live || 0}
              </p>
            </div>
            <button onClick={() => setRefreshResult(null)} className="text-[#737373] hover:text-white text-xs">x</button>
          </div>
        )}

        {!loading && !scheduleLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-12" data-testid="match-grid">
            {matches.map((match, i) => {
              const status = (match.status || "").toLowerCase();
              const isLive = status === "live" || status === "in progress";
              const isCompleted = status === "completed" || status === "result";
              const pred = predictions[match.matchId];
              const isUpcoming = !isLive && !isCompleted;

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

                  {/* Team names row */}
                  <div className="flex items-center justify-between mb-2">
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

                  {/* Confidence bar + odds direction + playing XI for upcoming matches with predictions */}
                  {isUpcoming && pred && (
                    <>
                      <ConfidenceBar
                        team1={match.team1Short}
                        team2={match.team2Short}
                        team1Prob={pred.prediction?.team1_win_prob}
                        team2Prob={pred.prediction?.team2_win_prob}
                        confidence={pred.prediction?.confidence}
                        oddsDirection={pred.odds_direction}
                      />
                      {pred.playing_xi?.confidence && pred.playing_xi.confidence !== "unavailable" && (
                        <div className="flex items-center gap-1 mt-1 mb-1">
                          <UsersThree weight="fill" className="w-3 h-3 text-[#7C3AED]" />
                          <span className="text-[9px] text-[#A1A1AA] font-mono">
                            Playing XI: {pred.playing_xi.confidence === "confirmed" ? "Confirmed" : "Predicted"} &middot;
                            {pred.playing_xi.team1_xi?.length || 0} + {pred.playing_xi.team2_xi?.length || 0} players
                          </span>
                        </div>
                      )}
                    </>
                  )}

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

function ConfidenceBar({ team1, team2, team1Prob, team2Prob, confidence, oddsDirection }) {
  if (!team1Prob && team1Prob !== 0) return null;
  const t1 = Math.round(team1Prob);
  const t2 = Math.round(team2Prob);
  const t1Color = t1 > t2 ? "#34C759" : t1 === t2 ? "#FFCC00" : "#FF3B30";
  const t2Color = t2 > t1 ? "#34C759" : t2 === t1 ? "#FFCC00" : "#FF3B30";

  const dir1 = oddsDirection?.team1;
  const dir2 = oddsDirection?.team2;
  const change1 = oddsDirection?.team1_change;
  const change2 = oddsDirection?.team2_change;

  const DirIcon = ({ dir, change }) => {
    if (!dir || dir === "new") return null;
    if (dir === "up") return <span className="inline-flex items-center text-[#34C759]"><TrendUp weight="bold" className="w-2.5 h-2.5" /><span className="text-[8px] ml-0.5">+{Math.abs(change)}</span></span>;
    if (dir === "down") return <span className="inline-flex items-center text-[#FF3B30]"><TrendDown weight="bold" className="w-2.5 h-2.5" /><span className="text-[8px] ml-0.5">{change}</span></span>;
    return <span className="inline-flex items-center text-[#737373]"><Minus weight="bold" className="w-2.5 h-2.5" /></span>;
  };

  return (
    <div data-testid="confidence-bar" className="my-2 space-y-1">
      <div className="flex items-center justify-between text-[10px] font-mono font-bold">
        <span className="flex items-center gap-1" style={{ color: t1Color }}>
          {team1} {t1}% <DirIcon dir={dir1} change={change1} />
        </span>
        <span className="text-[9px] text-[#737373]">PREDICTION</span>
        <span className="flex items-center gap-1" style={{ color: t2Color }}>
          <DirIcon dir={dir2} change={change2} /> {t2}% {team2}
        </span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-[#262626]">
        <div className="h-full transition-all duration-700 rounded-l-full" style={{ width: `${t1}%`, backgroundColor: t1Color }} />
        <div className="h-full transition-all duration-700 rounded-r-full" style={{ width: `${t2}%`, backgroundColor: t2Color }} />
      </div>
      <p className="text-[9px] text-[#737373] text-center font-mono">
        Model confidence: {confidence}% | H2H + Venue + Form + Squad
      </p>
    </div>
  );
}
