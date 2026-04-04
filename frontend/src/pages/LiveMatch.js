import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import { useWebSocket } from "@/hooks/useWebSocket";
import LiveScoreboard from "@/components/LiveScoreboard";
import BallLog from "@/components/BallLog";
import { WinProbabilityChart, ManhattanChart, AlgorithmComparisonChart, AlgorithmRadarChart } from "@/components/Charts";
import BettingOddsInput from "@/components/BettingOddsInput";
import OddsPanel from "@/components/OddsPanel";
import PlayerPredictions from "@/components/PlayerPredictions";
import PlayingXI from "@/components/PlayingXI";
import BetaPrediction from "@/components/BetaPrediction";
import ConsultantDashboard from "@/components/ConsultantDashboard";
import CricApiLivePanel from "@/components/CricApiLivePanel";
import ClaudeLiveAnalysis from "@/components/ClaudeLiveAnalysis";
import { WifiHigh, WifiSlash, Lightning, Spinner, UserCircle } from "@phosphor-icons/react";

export default function LiveMatch() {
  const { matchId } = useParams();
  const { fetchLiveData, getMatchState, getTeamSquad, fetchPlayerPredictions, fetchBetaPrediction, fetchConsultation, sendChat, fetchClaudeLive, refreshClaudePrediction } = useMatchData();
  const { data: wsData, connected } = useWebSocket(matchId);

  const [matchState, setMatchState] = useState(null);
  const [squads, setSquads] = useState([]);
  const [playerPreds, setPlayerPreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchingLive, setFetchingLive] = useState(false);
  const [fetchingPlayers, setFetchingPlayers] = useState(false);
  const [activeTab, setActiveTab] = useState("consult");
  const [probHistory, setProbHistory] = useState([]);
  const [bettingOdds, setBettingOdds] = useState(null);
  const [claudeLive, setClaudeLive] = useState(null);
  const [claudeLiveLoading, setClaudeLiveLoading] = useState(false);
  const [refreshingClaude, setRefreshingClaude] = useState(false);
  const [showFormula, setShowFormula] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const state = await getMatchState(matchId);
      if (state && !state.noLiveData) {
        setMatchState(state);
        if (state.probabilities) setProbHistory(prev => [...prev, state.probabilities]);
      } else if (state?.info) {
        setMatchState({ ...state.info, matchId, noLiveData: true });
        if (state.info.team1Short) {
          const s1 = await getTeamSquad(state.info.team1Short);
          const s2 = await getTeamSquad(state.info.team2Short);
          setSquads([s1, s2].filter(Boolean));
        }
      }
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId, getMatchState, getTeamSquad]);

  useEffect(() => {
    if (wsData && wsData.probabilities) {
      setMatchState(prev => ({ ...prev, ...wsData }));
      setProbHistory(prev => [...prev, wsData.probabilities].slice(-50));
    }
  }, [wsData]);

  const handleFetchLive = useCallback(async () => {
    setFetchingLive(true);
    const data = await fetchLiveData(matchId, bettingOdds);
    if (data && !data.error) {
      if (data.noLiveMatch) {
        setMatchState(prev => ({
          ...prev, ...data,
          noLiveData: false,
          noLiveMatch: true,
        }));
      } else {
        setMatchState(data);
        if (data.probabilities) setProbHistory(prev => [...prev, data.probabilities].slice(-50));
      }
    }
    setFetchingLive(false);
  }, [matchId, fetchLiveData, bettingOdds]);

  const handleFetchPlayers = useCallback(async () => {
    setFetchingPlayers(true);
    const data = await fetchPlayerPredictions(matchId);
    if (data?.players) setPlayerPreds(data.players);
    setFetchingPlayers(false);
  }, [matchId, fetchPlayerPredictions]);

  const handleOddsChange = (odds) => {
    setBettingOdds(odds);
  };

  const handleClaudeLive = async () => {
    setClaudeLiveLoading(true);
    const res = await fetchClaudeLive(matchId);
    if (res) setClaudeLive(res);
    setClaudeLiveLoading(false);
  };

  const handleRefreshClaude = async () => {
    setRefreshingClaude(true);
    const res = await refreshClaudePrediction(matchId);
    if (res && !res.error) {
      setMatchState(prev => ({
        ...prev,
        claudePrediction: res.claudePrediction,
        weightedPrediction: res.weightedPrediction,
        probabilities: res.probabilities,
      }));
    }
    setRefreshingClaude(false);
  };

  const liveData = matchState?.liveData || {};
  const score = liveData.score || {};
  const probs = matchState?.probabilities || {};
  const claudePred = matchState?.claudePrediction;
  const odds = matchState?.odds || {};
  const balls = matchState?.ballHistory || [];
  const team1 = matchState?.team1 || liveData.team1 || "Team A";
  const team2 = matchState?.team2 || liveData.team2 || "Team B";
  const t1Short = matchState?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchState?.team2Short || team2.slice(0, 3).toUpperCase();
  const hasLiveData = !matchState?.noLiveData && matchState?.liveData && !matchState?.noLiveMatch;
  const noLiveMatch = matchState?.noLiveMatch;
  const bettingEdge = matchState?.bettingEdge || null;
  const livePred = matchState?.live_prediction;
  const weightedPred = matchState?.weightedPrediction;

  const rightTabs = [
    { key: "consult", label: "Consult" },
    { key: "claude", label: "Claude" },
    { key: "liveapi", label: "Live API" },
    { key: "models", label: "Models" },
    { key: "odds", label: "Odds" },
    { key: "squad", label: "Squad" },
    { key: "players", label: "Players" },
  ];

  return (
    <div data-testid="live-match-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-4">
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                {connected ? <WifiHigh weight="fill" className="w-4 h-4 text-[#22C55E]" /> : <WifiSlash weight="fill" className="w-4 h-4 text-[#FF3B30]" />}
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#A1A1AA]">{connected ? "WS Connected" : "Disconnected"}</span>
              </div>
              {matchState?.source && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#1E1E1E] text-[#A1A1AA] font-mono">
                  Source: {matchState.source.toUpperCase()}
                </span>
              )}
              {probs.projected_score && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#22C55E]/10 text-[#22C55E] font-mono">
                  Projected: {Math.round(probs.projected_score)}
                </span>
              )}
            </div>
            <button onClick={handleFetchLive} disabled={fetchingLive} data-testid="fetch-live-btn"
              className="flex items-center gap-2 bg-[#007AFF] text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-[#0066DD] transition-colors disabled:opacity-50">
              {fetchingLive ? <><Spinner className="w-4 h-4 animate-spin" /> Fetching...</> : <><Lightning weight="fill" className="w-4 h-4" /> Fetch Live Scores</>}
            </button>
          </div>

          {!hasLiveData && !noLiveMatch && (
            <div className="bg-[#141414] border border-[#007AFF]/30 rounded-md p-8 text-center mb-4" data-testid="no-live-data">
              {fetchingLive ? (
                <>
                  <Spinner className="w-10 h-10 text-[#007AFF] mx-auto mb-3 animate-spin" />
                  <p className="text-sm text-[#A1A1AA] mb-2">Fetching live match data via GPT Web Search...</p>
                  <p className="text-xs text-[#71717A]">This may take 15-30 seconds. Searching for live scores, batsmen, bowlers, and match state.</p>
                </>
              ) : (
                <>
                  <Lightning weight="duotone" className="w-10 h-10 text-[#007AFF] mx-auto mb-3" />
                  <p className="text-sm text-[#A1A1AA] mb-2">No live data loaded yet.</p>
                  <p className="text-xs text-[#71717A] mb-4">Click "Fetch Live Scores" to get real-time data via web search. Set betting odds first for Bayesian model input.</p>
                </>
              )}
              <p className="text-lg font-bold uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{t1Short} vs {t2Short}</p>
              {!fetchingLive && (
                <div className="max-w-sm mx-auto mt-4">
                  <BettingOddsInput team1={t1Short} team2={t2Short} onOddsChange={handleOddsChange} currentEdge={bettingEdge} />
                </div>
              )}
            </div>
          )}

          {/* Always show Consultant + Chat even before live data loads */}
          {!hasLiveData && !noLiveMatch && !loading && (
            <div className="max-w-xl mx-auto mt-4">
              <ConsultantDashboard matchId={matchId} team1={t1Short} team2={t2Short} fetchConsultation={fetchConsultation} sendChat={sendChat} />
            </div>
          )}

          {noLiveMatch && (
            <div className="bg-[#141414] border border-amber-500/30 rounded-md p-8 text-center mb-4" data-testid="no-live-match">
              <WifiSlash weight="duotone" className="w-10 h-10 text-amber-500 mx-auto mb-3" />
              <p className="text-lg font-bold uppercase mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{t1Short} vs {t2Short}</p>
              <p className="text-sm text-amber-400 mb-2">This match is not live right now</p>
              <p className="text-xs text-[#71717A] mb-4">{matchState?.status || "The match hasn't started yet or has already been completed."}</p>
              {matchState?.source && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#1E1E1E] text-[#A1A1AA] font-mono">
                  Verified via {matchState.source === "web_search" ? "GPT-5.1 Web Search" : matchState.source}
                </span>
              )}
            </div>
          )}

          {hasLiveData && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              <div className="lg:col-span-8 space-y-4">
                <LiveScoreboard
                  matchData={{
                    team1, team2, team1Short: t1Short, team2Short: t2Short,
                    runs: score.runs || 0, overs: score.overs || 0, wickets: score.wickets || 0,
                    innings: liveData.innings || 1, status: liveData.status || "",
                    venue: matchState?.venue || "", isLive: true, probabilities: probs,
                    score: score.target ? `Target: ${score.target}` : "",
                    target: score.target || null,
                  }}
                />

                {/* Current batsmen + bowler */}
                {(matchState?.batsmen?.length > 0 || matchState?.bowler?.name) && (
                  <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="current-players">
                    <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>At The Crease</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {matchState.batsmen?.map((b, i) => (
                        <div key={i} className="bg-[#1E1E1E] rounded-md p-3">
                          <p className="text-xs font-bold mb-1">{b.name}{i === 0 ? " *" : ""}</p>
                          <div className="flex gap-3 text-[10px] text-[#A1A1AA]">
                            <span><span className="text-white font-mono font-bold">{b.runs}</span> ({b.balls})</span>
                            <span>4s: <span className="text-[#007AFF] font-mono">{b.fours}</span></span>
                            <span>6s: <span className="text-[#22C55E] font-mono">{b.sixes}</span></span>
                            <span>SR: <span className="font-mono">{b.strikeRate || b.strike_rate || 0}</span></span>
                          </div>
                        </div>
                      ))}
                      {matchState.bowler?.name && (
                        <div className="bg-[#1E1E1E] rounded-md p-3">
                          <p className="text-xs font-bold mb-1">{matchState.bowler.name} (bowling)</p>
                          <div className="flex gap-3 text-[10px] text-[#A1A1AA]">
                            <span>{matchState.bowler.overs} ov</span>
                            <span><span className="text-[#FF3B30] font-mono">{matchState.bowler.wickets}</span>/{matchState.bowler.runs}</span>
                            <span>Econ: <span className="font-mono">{matchState.bowler.economy}</span></span>
                          </div>
                        </div>
                      )}
                    </div>
                    {matchState.lastBallCommentary && (
                      <p className="text-xs text-[#A1A1AA] mt-2 italic">{matchState.lastBallCommentary}</p>
                    )}
                    {/* Yet to bat / Yet to bowl */}
                    {(matchState?.yetToBat?.length > 0 || matchState?.yetToBowl?.length > 0) && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-white/5">
                        {matchState.yetToBat?.length > 0 && (
                          <div data-testid="yet-to-bat">
                            <p className="text-[9px] uppercase tracking-wider text-[#737373] mb-1.5">Yet to Bat</p>
                            <div className="flex flex-wrap gap-1">
                              {matchState.yetToBat.map((p, i) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 bg-[#0A0A0A] border border-white/5 rounded text-[#A1A1AA] font-mono">{p.name}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {matchState.yetToBowl?.length > 0 && (
                          <div data-testid="yet-to-bowl">
                            <p className="text-[9px] uppercase tracking-wider text-[#737373] mb-1.5">Yet to Bowl</p>
                            <div className="flex flex-wrap gap-1">
                              {matchState.yetToBowl.map((p, i) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 bg-[#0A0A0A] border border-white/5 rounded text-[#A1A1AA] font-mono">{p.name}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* ═══ TWO PREDICTION MODELS ═══ */}
                {(weightedPred || (claudePred && !claudePred.error)) && (
                  <div className="space-y-4" data-testid="dual-prediction-models">
                    {/* Refresh bar */}
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                        Live Prediction Models
                      </h3>
                      <button onClick={handleRefreshClaude} disabled={refreshingClaude} data-testid="refresh-predictions-btn"
                        className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider bg-[#1E1E1E] hover:bg-[#2A2A2A] text-white px-3 py-1.5 rounded transition-colors disabled:opacity-50">
                        {refreshingClaude ? <><Spinner className="w-3 h-3 animate-spin" /> Refreshing...</> : <><Lightning weight="fill" className="w-3 h-3 text-[#007AFF]" /> Refresh Both</>}
                      </button>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      {/* ── MODEL 1: Weighted Probability ── */}
                      {weightedPred && (
                        <div className="bg-[#141414] border border-[#007AFF]/30 rounded-md p-4 space-y-3" data-testid="weighted-prediction">
                          <div className="flex items-center justify-between">
                            <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                              Weighted Probability
                            </h4>
                            <button onClick={() => setShowFormula(!showFormula)} data-testid="formula-info-btn"
                              className="w-5 h-5 rounded-full border border-[#007AFF]/40 text-[#007AFF] text-[10px] font-bold flex items-center justify-center hover:bg-[#007AFF]/10 transition-colors">
                              i
                            </button>
                          </div>

                          {/* Win probabilities */}
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-[#007AFF]/5 border border-[#007AFF]/20 rounded px-3 py-2.5 text-center">
                              <p className="text-[9px] text-[#007AFF]/70 uppercase">{t1Short}</p>
                              <p className="text-2xl font-black font-mono text-[#007AFF]" style={{ fontFamily: "'Barlow Condensed'" }}>{weightedPred.team1_pct}%</p>
                            </div>
                            <div className="bg-[#007AFF]/5 border border-[#007AFF]/20 rounded px-3 py-2.5 text-center">
                              <p className="text-[9px] text-[#007AFF]/70 uppercase">{t2Short}</p>
                              <p className="text-2xl font-black font-mono text-[#007AFF]" style={{ fontFamily: "'Barlow Condensed'" }}>{weightedPred.team2_pct}%</p>
                            </div>
                          </div>

                          {/* Breakdown */}
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between text-[10px]">
                              <span className="text-[#737373]">Dynamic Weight (α)</span>
                              <span className="font-mono text-white">{weightedPred.alpha}</span>
                            </div>
                            <div className="flex items-center justify-between text-[10px]">
                              <span className="text-[#737373]">Historical (H)</span>
                              <span className="font-mono text-[#FFCC00]">{(weightedPred.H * 100).toFixed(1)}%</span>
                            </div>
                            <div className="flex items-center justify-between text-[10px]">
                              <span className="text-[#737373]">Live (L)</span>
                              <span className="font-mono text-[#34C759]">{(weightedPred.L * 100).toFixed(1)}%</span>
                            </div>
                          </div>

                          {/* Historical factors breakdown */}
                          <div className="bg-[#0A0A0A] border border-[#262626] rounded p-2.5 space-y-1">
                            <p className="text-[9px] text-[#525252] uppercase mb-1">Historical Factors (H)</p>
                            {[
                              { label: "H2H Win %", val: weightedPred.breakdown?.h2h_win_pct, w: "0.40" },
                              { label: "Venue Win %", val: weightedPred.breakdown?.venue_win_pct, w: "0.25" },
                              { label: "Recent Form", val: weightedPred.breakdown?.recent_form_pct, w: "0.20" },
                              { label: "Toss Adv.", val: weightedPred.breakdown?.toss_advantage_pct, w: "0.15" },
                            ].map(f => (
                              <div key={f.label} className="flex items-center justify-between text-[10px]">
                                <span className="text-[#737373]">{f.label} <span className="text-[#525252]">({f.w})</span></span>
                                <div className="flex items-center gap-2">
                                  <div className="w-16 h-1 bg-[#1E1E1E] rounded-full overflow-hidden">
                                    <div className="h-full bg-[#FFCC00] rounded-full" style={{ width: `${(f.val || 0) * 100}%` }} />
                                  </div>
                                  <span className="font-mono text-[#A3A3A3] w-10 text-right">{((f.val || 0) * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Live factors breakdown */}
                          <div className="bg-[#0A0A0A] border border-[#262626] rounded p-2.5 space-y-1">
                            <p className="text-[9px] text-[#525252] uppercase mb-1">Live Factors (L)</p>
                            {[
                              { label: "Run Rate Ratio", val: weightedPred.breakdown?.run_rate_ratio, w: "0.40" },
                              { label: "Wickets in Hand", val: weightedPred.breakdown?.wickets_in_hand_ratio, w: "0.35" },
                              { label: "Phase Momentum", val: weightedPred.breakdown?.phase_momentum, w: "0.25" },
                            ].map(f => (
                              <div key={f.label} className="flex items-center justify-between text-[10px]">
                                <span className="text-[#737373]">{f.label} <span className="text-[#525252]">({f.w})</span></span>
                                <div className="flex items-center gap-2">
                                  <div className="w-16 h-1 bg-[#1E1E1E] rounded-full overflow-hidden">
                                    <div className="h-full bg-[#34C759] rounded-full" style={{ width: `${(f.val || 0) * 100}%` }} />
                                  </div>
                                  <span className="font-mono text-[#A3A3A3] w-10 text-right">{((f.val || 0) * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Chase Analysis */}
                          {livePred?.chase_analysis && (
                            <div className="bg-[#0A0A0A] border border-[#262626] rounded p-2.5">
                              <div className="flex items-center justify-between mb-1">
                                <p className="text-[9px] text-[#737373] uppercase">Chase</p>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                                  livePred.chase_analysis.difficulty === "easy" ? "bg-[#34C759]/15 text-[#34C759]" :
                                  livePred.chase_analysis.difficulty === "moderate" ? "bg-[#FFCC00]/15 text-[#FFCC00]" :
                                  "bg-[#FF3B30]/15 text-[#FF3B30]"
                                }`}>{livePred.chase_analysis.difficulty}</span>
                              </div>
                              <div className="grid grid-cols-3 gap-2 text-[10px] font-mono">
                                <div><span className="text-[#737373]">Need </span><span className="text-white font-bold">{livePred.chase_analysis.runs_remaining}/{livePred.chase_analysis.balls_remaining}b</span></div>
                                <div><span className="text-[#737373]">RRR </span><span className="text-white font-bold">{livePred.chase_analysis.required_rate}</span></div>
                                <div><span className="text-[#737373]">Wkts </span><span className="text-white font-bold">{livePred.wickets_in_hand}</span></div>
                              </div>
                            </div>
                          )}

                          {livePred?.projected_score && !livePred?.chase_analysis && (
                            <div className="bg-[#0A0A0A] border border-[#262626] rounded p-2 text-center">
                              <p className="text-[9px] text-[#737373] uppercase">Projected</p>
                              <p className="text-xl font-black font-mono text-[#34C759]" style={{ fontFamily: "'Barlow Condensed'" }}>~{livePred.projected_score}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* ── MODEL 2: Claude Opus Prediction ── */}
                      {claudePred && !claudePred.error && (
                        <div className="bg-[#141414] border border-purple-500/30 rounded-md p-4 space-y-3" data-testid="claude-live-prediction">
                          <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-purple-400" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                            Claude Opus Prediction
                          </h4>
                          <p className="text-sm font-bold text-white leading-snug">{claudePred.headline}</p>

                          {/* Win probabilities */}
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-purple-500/10 border border-purple-500/20 rounded px-3 py-2.5 text-center">
                              <p className="text-[9px] text-purple-300 uppercase">{t1Short}</p>
                              <p className="text-2xl font-black font-mono text-purple-400" style={{ fontFamily: "'Barlow Condensed'" }}>{claudePred.team1_win_pct ?? 50}%</p>
                            </div>
                            <div className="bg-purple-500/10 border border-purple-500/20 rounded px-3 py-2.5 text-center">
                              <p className="text-[9px] text-purple-300 uppercase">{t2Short}</p>
                              <p className="text-2xl font-black font-mono text-purple-400" style={{ fontFamily: "'Barlow Condensed'" }}>{claudePred.team2_win_pct ?? 50}%</p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <span className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase ${
                              claudePred.momentum === "BATTING" ? "bg-[#34C759]/15 text-[#34C759]" :
                              claudePred.momentum === "BOWLING" ? "bg-[#FF3B30]/15 text-[#FF3B30]" :
                              "bg-[#525252]/15 text-[#A1A1AA]"
                            }`}>Momentum: {claudePred.momentum}</span>
                            <span className="text-[9px] px-2 py-0.5 rounded font-bold bg-purple-500/10 text-purple-400">
                              Confidence: {claudePred.confidence}
                            </span>
                          </div>

                          <p className="text-[11px] text-[#D4D4D4] leading-relaxed">{claudePred.reasoning}</p>

                          <div className="grid grid-cols-1 gap-2">
                            {claudePred.batting_depth_assessment && (
                              <div className="bg-[#0A0A0A] border border-white/5 rounded p-2.5">
                                <p className="text-[9px] text-[#737373] uppercase mb-1">Batting Depth</p>
                                <p className="text-[10px] text-[#A3A3A3] leading-relaxed">{claudePred.batting_depth_assessment}</p>
                              </div>
                            )}
                            {claudePred.bowling_assessment && (
                              <div className="bg-[#0A0A0A] border border-white/5 rounded p-2.5">
                                <p className="text-[9px] text-[#737373] uppercase mb-1">Bowling Options</p>
                                <p className="text-[10px] text-[#A3A3A3] leading-relaxed">{claudePred.bowling_assessment}</p>
                              </div>
                            )}
                            {claudePred.key_matchup && (
                              <div className="bg-[#0A0A0A] border border-purple-500/10 rounded p-2.5">
                                <p className="text-[9px] text-purple-300 uppercase mb-1">Key Matchup</p>
                                <p className="text-[10px] text-[#D4D4D4]">{claudePred.key_matchup}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Formula Methodology Modal */}
                    {showFormula && (
                      <div className="bg-[#0A0A0A] border border-[#007AFF]/20 rounded-md p-5 space-y-3 relative" data-testid="formula-modal">
                        <button onClick={() => setShowFormula(false)} className="absolute top-3 right-3 text-[#737373] hover:text-white text-sm">x</button>
                        <h4 className="text-sm font-bold text-[#007AFF] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Weighted Probability Methodology</h4>
                        <div className="space-y-2 text-[11px] text-[#A3A3A3] leading-relaxed font-mono">
                          <p className="text-white font-bold">P(win) = (balls_rem / total_balls) x H + (1 - balls_rem / total_balls) x L</p>
                          <div>
                            <p className="text-[#FFCC00] font-bold mb-1">Step 1 - Dynamic Weight (alpha)</p>
                            <p>alpha = Balls Remaining / Total Match Balls</p>
                            <p className="text-[#525252]">Early in match: historical data matters more. Late: live performance dominates.</p>
                          </div>
                          <div>
                            <p className="text-[#FFCC00] font-bold mb-1">Step 2 - Historical (H)</p>
                            <p>H = 0.40 x H2H_Win% + 0.25 x Venue_Win% + 0.20 x Recent_Form% + 0.15 x Toss_Adv%</p>
                            <p className="text-[#525252]">Head-to-head is weighted highest. All values 0-1.</p>
                          </div>
                          <div>
                            <p className="text-[#34C759] font-bold mb-1">Step 3 - Live (L)</p>
                            <p>L = 0.40 x (CRR/RRR) + 0.35 x (Wickets_Left/10) + 0.25 x (Phase_Momentum)</p>
                            <p className="text-[#525252]">Run rate ratio capped at 1. Phase momentum = last 6 balls runs vs par.</p>
                          </div>
                          <div>
                            <p className="text-white font-bold mb-1">Step 4 - Final Score</p>
                            <p>Final = [alpha x H + (1-alpha) x L] x 100</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Betting Edge Display */}
                {bettingEdge && (bettingEdge.team1 || bettingEdge.team2) && (
                  <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="edge-panel">
                    <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Betting Edge</h4>
                    <div className="grid grid-cols-2 gap-3">
                      {[{ team: t1Short, edge: bettingEdge.team1 }, { team: t2Short, edge: bettingEdge.team2 }]
                        .filter(e => e.edge)
                        .map((e) => (
                          <div key={e.team} className={`rounded-md p-3 text-center border ${e.edge.edge_positive ? "bg-[#22C55E]/5 border-[#22C55E]/20" : "bg-[#FF3B30]/5 border-[#FF3B30]/20"}`}>
                            <p className="text-xs text-[#A1A1AA] mb-1">{e.team}</p>
                            <p className="text-xs font-mono text-[#71717A]">Market: {e.edge.market_implied}% | Model: {e.edge.model_prob}%</p>
                            <p className={`text-lg font-bold font-mono tabular-nums ${e.edge.edge_positive ? "text-[#22C55E]" : "text-[#FF3B30]"}`}>
                              Edge: {e.edge.edge > 0 ? "+" : ""}{e.edge.edge}%
                            </p>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                <BallLog balls={balls} />
                <WinProbabilityChart data={probHistory} team1={t1Short} team2={t2Short} />

                {matchState?.aiPrediction && (
                  <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="ai-analysis">
                    <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>GPT Analysis</h4>
                    <p className="text-sm text-[#A1A1AA]">{matchState.aiPrediction.analysis}</p>
                    {matchState.aiPrediction.keyFactors?.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {matchState.aiPrediction.keyFactors.map((f, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 bg-[#1E1E1E] rounded text-[#A1A1AA]">{f}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="lg:col-span-4 space-y-4">
                <div className="flex gap-1 bg-[#141414] border border-white/10 rounded-md p-1">
                  {rightTabs.map((tab) => (
                    <button key={tab.key}
                      onClick={() => { setActiveTab(tab.key); if (tab.key === "players" && playerPreds.length === 0) handleFetchPlayers(); }}
                      data-testid={`tab-${tab.key}`}
                      className={`flex-1 text-[10px] font-bold uppercase tracking-wider py-1.5 rounded transition-colors ${
                        activeTab === tab.key ? "bg-[#007AFF] text-white" : "text-[#A1A1AA] hover:text-white"
                      }`}>
                      {tab.label}
                    </button>
                  ))}
                </div>

                {activeTab === "consult" && (
                  <ConsultantDashboard matchId={matchId} team1={t1Short} team2={t2Short} fetchConsultation={fetchConsultation} sendChat={sendChat} />
                )}
                {activeTab === "claude" && (
                  <ClaudeLiveAnalysis data={claudeLive} loading={claudeLiveLoading} onFetch={handleClaudeLive} />
                )}
                {activeTab === "liveapi" && (
                  <CricApiLivePanel />
                )}
                {activeTab === "models" && (
                  <>
                    <AlgorithmComparisonChart probabilities={probs} team1={t1Short} team2={t2Short} />
                    <AlgorithmRadarChart probabilities={probs} />
                  </>
                )}
                {activeTab === "odds" && (
                  <>
                    <BettingOddsInput team1={t1Short} team2={t2Short} onOddsChange={handleOddsChange} currentEdge={bettingEdge} />
                    <OddsPanel odds={odds} history={[]} team1={t1Short} team2={t2Short} />
                  </>
                )}
                {activeTab === "squad" && <PlayingXI squad={squads.map(s => ({ teamName: s?.teamName, players: s?.players?.slice(0, 11) || [] }))} team1={team1} team2={team2} />}
                {activeTab === "players" && (
                  <div>
                    {fetchingPlayers ? (
                      <div className="bg-[#141414] border border-white/10 rounded-md p-8 text-center">
                        <Spinner className="w-6 h-6 animate-spin mx-auto mb-2 text-[#007AFF]" />
                        <p className="text-xs text-[#A1A1AA]">Generating player predictions via Claude...</p>
                      </div>
                    ) : <PlayerPredictions players={playerPreds} />}
                    {playerPreds.length === 0 && !fetchingPlayers && (
                      <button onClick={handleFetchPlayers} data-testid="load-player-preds-btn"
                        className="w-full mt-2 py-2 bg-[#007AFF]/20 text-[#007AFF] rounded-md text-xs font-bold uppercase hover:bg-[#007AFF]/30 transition-colors">
                        <UserCircle weight="bold" className="inline w-4 h-4 mr-1" /> Generate Player Predictions
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
