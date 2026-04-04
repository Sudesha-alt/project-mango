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
  const { fetchLiveData, getMatchState, getTeamSquad, fetchPlayerPredictions, fetchBetaPrediction, fetchConsultation, sendChat, fetchClaudeLive } = useMatchData();
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

  const liveData = matchState?.liveData || {};
  const score = liveData.score || {};
  const probs = matchState?.probabilities || {};
  const odds = matchState?.odds || {};
  const balls = matchState?.ballHistory || [];
  const team1 = matchState?.team1 || liveData.team1 || "Team A";
  const team2 = matchState?.team2 || liveData.team2 || "Team B";
  const t1Short = matchState?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchState?.team2Short || team2.slice(0, 3).toUpperCase();
  const hasLiveData = !matchState?.noLiveData && matchState?.liveData && !matchState?.noLiveMatch;
  const noLiveMatch = matchState?.noLiveMatch;
  const bettingEdge = matchState?.bettingEdge || null;

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
                            <span>SR: <span className="font-mono">{b.strikeRate}</span></span>
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
                  </div>
                )}

                {/* Live Prediction Panel */}
                {matchState?.live_prediction && (
                  <div className="bg-[#141414] border border-[#007AFF]/30 rounded-md p-4 space-y-3" data-testid="live-prediction-panel">
                    <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] flex items-center gap-1.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                      <Lightning weight="fill" className="w-4 h-4" /> Live Match Prediction
                    </h4>
                    <p className="text-sm text-[#D4D4D4] leading-relaxed">{matchState.live_prediction.summary}</p>
                    
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-[#0A0A0A] rounded p-2 text-center">
                        <p className="text-[9px] text-[#737373] uppercase">Win Prob</p>
                        <p className="text-xl font-black font-mono text-[#007AFF]" style={{ fontFamily: "'Barlow Condensed'" }}>{matchState.live_prediction.win_probability}%</p>
                        <p className="text-[8px] text-[#525252]">{matchState.live_prediction.batting_team}</p>
                      </div>
                      <div className="bg-[#0A0A0A] rounded p-2 text-center">
                        <p className="text-[9px] text-[#737373] uppercase">Phase</p>
                        <p className="text-sm font-bold text-white uppercase">{matchState.live_prediction.phase}</p>
                        <p className="text-[8px] text-[#525252]">CRR: {matchState.live_prediction.crr}</p>
                      </div>
                      <div className="bg-[#0A0A0A] rounded p-2 text-center">
                        <p className="text-[9px] text-[#737373] uppercase">Wkts in Hand</p>
                        <p className="text-xl font-black font-mono text-white" style={{ fontFamily: "'Barlow Condensed'" }}>{matchState.live_prediction.wickets_in_hand}</p>
                      </div>
                    </div>

                    {matchState.live_prediction.projected_score && (
                      <div className="bg-[#0A0A0A] border border-[#262626] rounded p-2 text-center">
                        <p className="text-[9px] text-[#737373] uppercase">Projected Score</p>
                        <p className="text-2xl font-black font-mono text-[#34C759]" style={{ fontFamily: "'Barlow Condensed'" }}>~{matchState.live_prediction.projected_score}</p>
                      </div>
                    )}

                    {matchState.live_prediction.chase_analysis && (
                      <div className="bg-[#0A0A0A] border border-[#262626] rounded p-3 space-y-1">
                        <div className="flex items-center justify-between">
                          <p className="text-[9px] text-[#737373] uppercase">Chase Analysis</p>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                            matchState.live_prediction.chase_analysis.difficulty === "easy" ? "bg-[#34C759]/15 text-[#34C759]" :
                            matchState.live_prediction.chase_analysis.difficulty === "moderate" ? "bg-[#FFCC00]/15 text-[#FFCC00]" :
                            "bg-[#FF3B30]/15 text-[#FF3B30]"
                          }`}>{matchState.live_prediction.chase_analysis.difficulty}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                          <div><span className="text-[#737373]">Need: </span><span className="text-white font-bold">{matchState.live_prediction.chase_analysis.runs_remaining} off {matchState.live_prediction.chase_analysis.balls_remaining}b</span></div>
                          <div><span className="text-[#737373]">RRR: </span><span className="text-white font-bold">{matchState.live_prediction.chase_analysis.required_rate}</span></div>
                        </div>
                      </div>
                    )}

                    {matchState.live_prediction.batsmen_on_field?.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-[9px] text-[#737373] uppercase">Batsmen Impact</p>
                        {matchState.live_prediction.batsmen_on_field.map((b, i) => (
                          <div key={i} className="flex items-center justify-between text-[10px]">
                            <span className="text-white">{b.name} {b.is_set && <span className="text-[#34C759]">(SET)</span>}</span>
                            <div className="flex items-center gap-2 font-mono">
                              <span className="text-[#A3A3A3]">{b.runs}({b.balls}) SR:{b.sr}</span>
                              <span className={`px-1 py-0 rounded text-[8px] font-bold uppercase ${
                                b.impact === "high" ? "bg-[#34C759]/15 text-[#34C759]" :
                                b.impact === "medium" ? "bg-[#FFCC00]/15 text-[#FFCC00]" :
                                "bg-[#525252]/15 text-[#525252]"
                              }`}>{b.impact}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {matchState.live_prediction.current_bowler && (
                      <div className="flex items-center justify-between text-[10px] bg-[#0A0A0A] rounded p-2">
                        <span className="text-[#FF3B30]">{matchState.live_prediction.current_bowler.name} (bowling)</span>
                        <div className="flex items-center gap-2 font-mono text-[#A3A3A3]">
                          <span>{matchState.live_prediction.current_bowler.wickets}/{matchState.live_prediction.current_bowler.runs} ({matchState.live_prediction.current_bowler.overs}ov)</span>
                          <span className={`px-1 py-0 rounded text-[8px] font-bold uppercase ${
                            matchState.live_prediction.current_bowler.impact === "high" ? "bg-[#FF3B30]/15 text-[#FF3B30]" :
                            matchState.live_prediction.current_bowler.impact === "medium" ? "bg-[#FFCC00]/15 text-[#FFCC00]" :
                            "bg-[#525252]/15 text-[#525252]"
                          }`}>{matchState.live_prediction.current_bowler.impact}</span>
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
