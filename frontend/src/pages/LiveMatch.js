import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import { useWebSocket } from "@/hooks/useWebSocket";
import LiveScoreboard from "@/components/LiveScoreboard";
import BallLog from "@/components/BallLog";
import AlgorithmPanel from "@/components/AlgorithmPanel";
import OddsPanel from "@/components/OddsPanel";
import { WinProbabilityChart, ManhattanChart, AlgorithmRadarChart } from "@/components/Charts";
import PlayerPredictions from "@/components/PlayerPredictions";
import PlayingXI from "@/components/PlayingXI";
import { WifiHigh, WifiSlash, ArrowsClockwise } from "@phosphor-icons/react";

export default function LiveMatch() {
  const { matchId } = useParams();
  const { fetchMatchDetail, fetchSquad, triggerCalculation, fetchOdds, fetchPlayerPredictions } = useMatchData();
  const { data: wsData, connected, requestUpdate } = useWebSocket(matchId);

  const [matchDetail, setMatchDetail] = useState(null);
  const [squad, setSquad] = useState([]);
  const [odds, setOdds] = useState({});
  const [oddsHistory, setOddsHistory] = useState([]);
  const [probHistory, setProbHistory] = useState([]);
  const [ballHistory, setBallHistory] = useState([]);
  const [playerPreds, setPlayerPreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("models");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [detail, sq, calc, oddsData] = await Promise.all([
        fetchMatchDetail(matchId),
        fetchSquad(matchId),
        triggerCalculation(matchId),
        fetchOdds(matchId),
      ]);
      setMatchDetail(detail);
      setSquad(sq?.squad || []);
      setOdds(oddsData?.odds || {});
      setOddsHistory(oddsData?.history || []);
      setProbHistory(detail?.probabilityHistory || []);
      setBallHistory(detail?.ballHistory || []);
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId, fetchMatchDetail, fetchSquad, triggerCalculation, fetchOdds]);

  // Update from WebSocket
  useEffect(() => {
    if (wsData) {
      if (wsData.odds) setOdds(wsData.odds);
      if (wsData.probabilityHistory) setProbHistory((prev) => [...prev, ...wsData.probabilityHistory].slice(-100));
      if (wsData.ballHistory) setBallHistory(wsData.ballHistory);
    }
  }, [wsData]);

  // Auto-refresh every 15s
  useEffect(() => {
    const interval = setInterval(() => {
      if (matchId) {
        requestUpdate();
        triggerCalculation(matchId);
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [matchId, requestUpdate, triggerCalculation]);

  const handleRefresh = useCallback(async () => {
    requestUpdate();
    const calc = await triggerCalculation(matchId);
    if (calc?.result) {
      setOdds(calc.result.odds || {});
    }
  }, [matchId, requestUpdate, triggerCalculation]);

  const loadPlayerPreds = useCallback(async () => {
    const data = await fetchPlayerPredictions(matchId);
    setPlayerPreds(data?.players || []);
  }, [matchId, fetchPlayerPredictions]);

  const info = matchDetail?.info || {};
  const teams = info.teams || [];
  const team1 = wsData?.team1 || teams[0] || "Team A";
  const team2 = wsData?.team2 || teams[1] || "Team B";
  const t1Short = wsData?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = wsData?.team2Short || team2.slice(0, 3).toUpperCase();
  const probs = wsData?.probabilities || matchDetail?.probabilities || {};

  const rightTabs = [
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
          {/* Top bar */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                {connected ? (
                  <WifiHigh weight="fill" className="w-4 h-4 text-[#22C55E]" />
                ) : (
                  <WifiSlash weight="fill" className="w-4 h-4 text-[#FF3B30]" />
                )}
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#A1A1AA]">
                  {connected ? "Connected" : "Reconnecting..."}
                </span>
              </div>
            </div>
            <button
              onClick={handleRefresh}
              data-testid="refresh-btn"
              className="flex items-center gap-1.5 text-[10px] font-bold uppercase px-3 py-1.5 rounded bg-[#1E1E1E] text-[#A1A1AA] hover:bg-[#252525] hover:text-white transition-colors"
            >
              <ArrowsClockwise weight="bold" className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>

          {/* Main Grid: 8/4 split */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* LEFT: Scoreboard + Ball Log + Charts */}
            <div className="lg:col-span-8 space-y-4">
              <LiveScoreboard matchData={matchDetail} wsData={wsData} />
              <BallLog balls={ballHistory} />
              <WinProbabilityChart data={probHistory} team1={t1Short} team2={t2Short} />
              <ManhattanChart data={[]} />
            </div>

            {/* RIGHT: Models / Odds / Squad / Players */}
            <div className="lg:col-span-4 space-y-4">
              <div className="flex gap-1 bg-[#141414] border border-white/10 rounded-md p-1">
                {rightTabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => {
                      setActiveTab(tab.key);
                      if (tab.key === "players" && playerPreds.length === 0) loadPlayerPreds();
                    }}
                    data-testid={`tab-${tab.key}`}
                    className={`flex-1 text-[10px] font-bold uppercase tracking-wider py-1.5 rounded transition-colors ${
                      activeTab === tab.key ? "bg-[#007AFF] text-white" : "text-[#A1A1AA] hover:text-white"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {activeTab === "models" && (
                <>
                  <AlgorithmPanel probabilities={probs} team1={t1Short} team2={t2Short} />
                  <AlgorithmRadarChart probabilities={probs} />
                </>
              )}

              {activeTab === "odds" && (
                <OddsPanel odds={odds} history={oddsHistory} team1={t1Short} team2={t2Short} />
              )}

              {activeTab === "squad" && (
                <PlayingXI squad={squad} team1={team1} team2={team2} />
              )}

              {activeTab === "players" && (
                <PlayerPredictions players={playerPreds} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
