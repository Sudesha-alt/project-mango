import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import PlayingXI from "@/components/PlayingXI";
import AlgorithmPanel from "@/components/AlgorithmPanel";
import { WinProbabilityChart, AlgorithmRadarChart } from "@/components/Charts";
import PlayerPredictions from "@/components/PlayerPredictions";
import { ArrowRight, Spinner } from "@phosphor-icons/react";

export default function PreMatch() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { fetchMatchDetail, fetchSquad, fetchPredictions, triggerCalculation, fetchPlayerPredictions } = useMatchData();
  const [matchDetail, setMatchDetail] = useState(null);
  const [squad, setSquad] = useState(null);
  const [predictions, setPredictions] = useState(null);
  const [playerPreds, setPlayerPreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [detail, sq, calc] = await Promise.all([
        fetchMatchDetail(matchId),
        fetchSquad(matchId),
        triggerCalculation(matchId),
      ]);
      setMatchDetail(detail);
      setSquad(sq?.squad || []);
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId, fetchMatchDetail, fetchSquad, triggerCalculation]);

  const loadAIPredictions = async () => {
    setAiLoading(true);
    const [preds, pPreds] = await Promise.all([
      fetchPredictions(matchId),
      fetchPlayerPredictions(matchId),
    ]);
    setPredictions(preds?.predictions);
    setPlayerPreds(pPreds?.players || []);
    setAiLoading(false);
  };

  const info = matchDetail?.info || {};
  const teams = info.teams || [];
  const team1 = teams[0] || "Team A";
  const team2 = teams[1] || "Team B";
  const probs = matchDetail?.probabilities || {};

  return (
    <div data-testid="pre-match-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-6">
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-6">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-1">Pre-Match Analysis</p>
              <h2
                className="text-2xl sm:text-3xl font-bold uppercase tracking-tight"
                style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
                data-testid="prematch-title"
              >
                {team1} vs {team2}
              </h2>
              <p className="text-xs text-[#71717A] mt-1">{info.venue || ""} {info.dateTimeGMT ? `| ${new Date(info.dateTimeGMT).toLocaleDateString()}` : ""}</p>
            </div>
            <button
              onClick={() => navigate(`/live/${matchId}`)}
              data-testid="go-live-btn"
              className="flex items-center gap-2 bg-[#007AFF] text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-[#0066DD] transition-colors"
            >
              Go Live <ArrowRight weight="bold" className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left Column */}
            <div className="lg:col-span-8 space-y-4">
              <PlayingXI squad={squad} team1={team1} team2={team2} />

              {/* AI Predictions */}
              <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="ai-predictions">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                    AI Match Prediction
                  </h4>
                  <button
                    onClick={loadAIPredictions}
                    disabled={aiLoading}
                    data-testid="load-ai-btn"
                    className="text-[10px] font-bold uppercase px-3 py-1.5 rounded bg-[#007AFF]/20 text-[#007AFF] hover:bg-[#007AFF]/30 transition-colors disabled:opacity-50"
                  >
                    {aiLoading ? (
                      <span className="flex items-center gap-1"><Spinner className="w-3 h-3 animate-spin" /> Analyzing...</span>
                    ) : predictions ? "Refresh" : "Generate AI Prediction"}
                  </button>
                </div>
                {predictions?.prediction ? (
                  <div>
                    <p className="text-sm text-[#A1A1AA] mb-3">{predictions.prediction.analysis}</p>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                        <p className="text-xs text-[#71717A] mb-1">{team1}</p>
                        <p className="text-xl font-bold font-mono tabular-nums text-[#007AFF]">
                          {((predictions.prediction.team1WinProb || 0.5) * 100).toFixed(0)}%
                        </p>
                      </div>
                      <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                        <p className="text-xs text-[#71717A] mb-1">{team2}</p>
                        <p className="text-xl font-bold font-mono tabular-nums text-[#FF3B30]">
                          {((predictions.prediction.team2WinProb || 0.5) * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                    {predictions.prediction.keyFactors?.length > 0 && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-1">Key Factors</p>
                        <ul className="space-y-1">
                          {predictions.prediction.keyFactors.map((f, i) => (
                            <li key={i} className="text-xs text-[#A1A1AA] flex items-start gap-1.5">
                              <span className="text-[#007AFF] mt-0.5">-</span> {f}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-[#71717A]">Click "Generate AI Prediction" to get Claude-powered analysis</p>
                )}
              </div>

              <PlayerPredictions players={playerPreds} />
            </div>

            {/* Right Column */}
            <div className="lg:col-span-4 space-y-4">
              <AlgorithmPanel probabilities={probs} team1={team1} team2={team2} />
              <WinProbabilityChart
                data={matchDetail?.probabilityHistory || []}
                team1={team1}
                team2={team2}
              />
              <AlgorithmRadarChart probabilities={probs} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
