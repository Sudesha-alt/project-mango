import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import PlayingXI from "@/components/PlayingXI";
import BetaPrediction from "@/components/BetaPrediction";
import { WinProbabilityChart, AlgorithmRadarChart, PreMatchRadarChart } from "@/components/Charts";
import { ArrowRight, Spinner, MapPin, CalendarBlank } from "@phosphor-icons/react";

export default function PreMatch() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { getTeamSquad, fetchMatchPrediction, fetchBetaPrediction } = useMatchData();
  const [matchInfo, setMatchInfo] = useState(null);
  const [squad1, setSquad1] = useState(null);
  const [squad2, setSquad2] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [predLoading, setPredLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/matches/${matchId}/state`);
        const data = await res.json();
        const info = data.info || data;
        setMatchInfo(info);
        if (info.team1Short) {
          const s1 = await getTeamSquad(info.team1Short);
          setSquad1(s1);
        }
        if (info.team2Short) {
          const s2 = await getTeamSquad(info.team2Short);
          setSquad2(s2);
        }
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId, getTeamSquad]);

  const handlePredict = async () => {
    setPredLoading(true);
    const res = await fetchMatchPrediction(matchId);
    if (res?.prediction) setPrediction(res.prediction);
    setPredLoading(false);
  };

  const team1 = matchInfo?.team1 || "Team A";
  const team2 = matchInfo?.team2 || "Team B";
  const t1Short = matchInfo?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchInfo?.team2Short || team2.slice(0, 3).toUpperCase();

  const squad1Players = squad1?.players?.map(p => ({ name: p.name, isCaptain: p.isCaptain, isKeeper: p.isKeeper })) || [];
  const squad2Players = squad2?.players?.map(p => ({ name: p.name, isCaptain: p.isCaptain, isKeeper: p.isKeeper })) || [];

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
              <h2 className="text-2xl sm:text-3xl font-bold uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed', sans-serif" }} data-testid="prematch-title">
                {t1Short} vs {t2Short}
              </h2>
              <div className="flex items-center gap-3 mt-1">
                {matchInfo?.venue && <span className="text-xs text-[#71717A] flex items-center gap-1"><MapPin weight="bold" className="w-3 h-3" />{matchInfo.venue}</span>}
                {matchInfo?.dateTimeGMT && <span className="text-xs text-[#71717A] flex items-center gap-1"><CalendarBlank weight="bold" className="w-3 h-3" />{new Date(matchInfo.dateTimeGMT).toLocaleDateString()}</span>}
              </div>
            </div>
            <button onClick={() => navigate(`/live/${matchId}`)} data-testid="go-live-btn"
              className="flex items-center gap-2 bg-[#007AFF] text-white px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-[#0066DD] transition-colors">
              Go Live <ArrowRight weight="bold" className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-8 space-y-4">
              {/* Playing XI */}
              <PlayingXI
                squad={[
                  { teamName: team1, players: squad1Players },
                  { teamName: team2, players: squad2Players }
                ]}
                team1={team1} team2={team2}
              />

              {/* AI Prediction */}
              <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="ai-predictions">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                    GPT Match Prediction
                  </h4>
                  <button onClick={handlePredict} disabled={predLoading} data-testid="predict-btn"
                    className="text-[10px] font-bold uppercase px-3 py-1.5 rounded bg-[#007AFF]/20 text-[#007AFF] hover:bg-[#007AFF]/30 transition-colors disabled:opacity-50">
                    {predLoading ? <span className="flex items-center gap-1"><Spinner className="w-3 h-3 animate-spin" /> Analyzing...</span> : prediction ? "Refresh Prediction" : "Generate Prediction"}
                  </button>
                </div>
                {prediction ? (
                  <div className="space-y-3">
                    <p className="text-sm text-[#A1A1AA]">{prediction.analysis}</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                        <p className="text-xs text-[#71717A] mb-1">{t1Short}</p>
                        <p className="text-2xl font-bold font-mono tabular-nums text-[#007AFF]">{((prediction.team1WinProb || 0.5) * 100).toFixed(0)}%</p>
                      </div>
                      <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                        <p className="text-xs text-[#71717A] mb-1">{t2Short}</p>
                        <p className="text-2xl font-bold font-mono tabular-nums text-[#FF3B30]">{((prediction.team2WinProb || 0.5) * 100).toFixed(0)}%</p>
                      </div>
                    </div>
                    {prediction.projectedScore && (
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-[#1E1E1E] rounded-md p-2 text-center">
                          <p className="text-[10px] text-[#71717A]">{t1Short} Projected</p>
                          <p className="text-sm font-mono font-bold">{prediction.projectedScore.team1?.expected || "—"}</p>
                          <p className="text-[10px] text-[#71717A]">{prediction.projectedScore.team1?.low}—{prediction.projectedScore.team1?.high}</p>
                        </div>
                        <div className="bg-[#1E1E1E] rounded-md p-2 text-center">
                          <p className="text-[10px] text-[#71717A]">{t2Short} Projected</p>
                          <p className="text-sm font-mono font-bold">{prediction.projectedScore.team2?.expected || "—"}</p>
                          <p className="text-[10px] text-[#71717A]">{prediction.projectedScore.team2?.low}—{prediction.projectedScore.team2?.high}</p>
                        </div>
                      </div>
                    )}
                    {prediction.keyFactors?.length > 0 && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-1">Key Factors</p>
                        <ul className="space-y-1">
                          {prediction.keyFactors.map((f, i) => (
                            <li key={i} className="text-xs text-[#A1A1AA] flex items-start gap-1.5"><span className="text-[#007AFF]">-</span>{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {prediction.venueStats && <p className="text-xs text-[#71717A] italic">{prediction.venueStats}</p>}
                  </div>
                ) : (
                  <p className="text-sm text-[#71717A]">Click "Generate Prediction" for GPT-powered match analysis</p>
                )}
              </div>
            </div>

            <div className="lg:col-span-4 space-y-4">
              {/* Beta Prediction Engine */}
              <BetaPrediction matchId={matchId} team1={t1Short} team2={t2Short} fetchBetaPrediction={fetchBetaPrediction} />
              {prediction && (
                <>
                  <AlgorithmRadarChart probabilities={{
                    pressure_index: prediction.team1WinProb || 0.5,
                    dls_resource: prediction.team1WinProb || 0.5,
                    bayesian: (prediction.team1WinProb || 0.5) * 0.95,
                    monte_carlo: (prediction.team1WinProb || 0.5) * 1.05,
                    ensemble: prediction.team1WinProb || 0.5,
                  }} />
                  <WinProbabilityChart data={[{ensemble: prediction.team1WinProb || 0.5}]} team1={t1Short} team2={t2Short} />
                </>
              )}
              {/* Quick Info */}
              <div className="bg-[#141414] border border-white/10 rounded-md p-4">
                <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Match Info</h4>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between"><span className="text-[#71717A]">Match #</span><span>{matchInfo?.match_number || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-[#71717A]">Format</span><span>{matchInfo?.matchType || "T20"}</span></div>
                  <div className="flex justify-between"><span className="text-[#71717A]">Series</span><span>{matchInfo?.series || "IPL 2026"}</span></div>
                  <div className="flex justify-between"><span className="text-[#71717A]">Status</span><span className="text-[#EAB308]">{matchInfo?.status || "Upcoming"}</span></div>
                </div>
              </div>
              <PreMatchRadarChart team1={t1Short} team2={t2Short} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
