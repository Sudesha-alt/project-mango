import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import AlgorithmPanel from "@/components/AlgorithmPanel";
import { WinProbabilityChart, AlgorithmRadarChart } from "@/components/Charts";
import { Trophy, Target, ChartLine } from "@phosphor-icons/react";

export default function PostMatch() {
  const { matchId } = useParams();
  const { fetchMatchDetail, fetchScorecard } = useMatchData();
  const [matchDetail, setMatchDetail] = useState(null);
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [detail, sc] = await Promise.all([
        fetchMatchDetail(matchId),
        fetchScorecard(matchId),
      ]);
      setMatchDetail(detail);
      setScorecard(sc);
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId, fetchMatchDetail, fetchScorecard]);

  const info = matchDetail?.info || {};
  const teams = info.teams || [];
  const team1 = teams[0] || "Team A";
  const team2 = teams[1] || "Team B";
  const probs = matchDetail?.probabilities || {};

  return (
    <div data-testid="post-match-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-6">
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-1">Post-Match Analysis</p>
            <h2
              className="text-2xl sm:text-3xl font-bold uppercase tracking-tight"
              style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
              data-testid="postmatch-title"
            >
              {team1} vs {team2}
            </h2>
            {info.status && <p className="text-sm text-[#A1A1AA] mt-1">{info.status}</p>}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left */}
            <div className="lg:col-span-8 space-y-4">
              {/* Result Card */}
              <div className="bg-[#141414] border border-white/10 rounded-md p-6 text-center" data-testid="result-card">
                <Trophy weight="fill" className="w-10 h-10 text-[#EAB308] mx-auto mb-3" />
                <p className="text-sm text-[#A1A1AA] mb-2">Match Result</p>
                <p className="text-lg font-bold" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                  {info.status || "Match Complete"}
                </p>
              </div>

              {/* Scorecard Summary */}
              {scorecard?.scorecard && (
                <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="scorecard-summary">
                  <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                    Scorecard
                  </h4>
                  {Array.isArray(scorecard.scorecard) ? (
                    scorecard.scorecard.map((inning, idx) => (
                      <div key={idx} className="mb-4">
                        <p className="text-sm font-bold mb-2">{inning.inning || `Innings ${idx + 1}`}</p>
                        {inning.batting && (
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-[#71717A] border-b border-white/5">
                                  <th className="text-left py-1 pr-4">Batter</th>
                                  <th className="text-right py-1 px-2">R</th>
                                  <th className="text-right py-1 px-2">B</th>
                                  <th className="text-right py-1 px-2">4s</th>
                                  <th className="text-right py-1 px-2">6s</th>
                                  <th className="text-right py-1 px-2">SR</th>
                                </tr>
                              </thead>
                              <tbody>
                                {inning.batting.map((b, bi) => (
                                  <tr key={bi} className="border-b border-white/5 hover:bg-[#1E1E1E]">
                                    <td className="py-1.5 pr-4">
                                      <span className="font-medium">{b.batsman?.name || b.batsman || "—"}</span>
                                      <span className="text-[#71717A] ml-1 text-[10px]">{b.dismissal || ""}</span>
                                    </td>
                                    <td className="text-right py-1.5 px-2 font-mono tabular-nums font-bold">{b.r ?? b.runs ?? "—"}</td>
                                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-[#A1A1AA]">{b.b ?? b.balls ?? "—"}</td>
                                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-[#007AFF]">{b["4s"] ?? "—"}</td>
                                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-[#22C55E]">{b["6s"] ?? "—"}</td>
                                    <td className="text-right py-1.5 px-2 font-mono tabular-nums text-[#A1A1AA]">{b.sr ?? "—"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-[#71717A]">Scorecard data format not available</p>
                  )}
                </div>
              )}

              {/* Model Accuracy */}
              <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="model-accuracy">
                <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                  <Target weight="fill" className="inline w-4 h-4 mr-1.5 text-[#007AFF]" />
                  Model Performance
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  {[
                    { label: "Pressure", key: "pressure_index" },
                    { label: "DLS", key: "dls_resource" },
                    { label: "Bayesian", key: "bayesian" },
                    { label: "Monte Carlo", key: "monte_carlo" },
                    { label: "Ensemble", key: "ensemble" },
                  ].map((algo) => (
                    <div key={algo.key} className="bg-[#1E1E1E] rounded-md p-3 text-center">
                      <p className="text-[10px] text-[#71717A] mb-1">{algo.label}</p>
                      <p className="text-lg font-bold font-mono tabular-nums">
                        {probs[algo.key] ? (probs[algo.key] * 100).toFixed(1) + "%" : "--"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right */}
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
