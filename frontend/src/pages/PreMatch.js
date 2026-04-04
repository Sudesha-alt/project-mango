import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import PlayingXIPerformance from "@/components/PlayingXIPerformance";
import ConsultantDashboard from "@/components/ConsultantDashboard";
import PreMatchPredictionBreakdown from "@/components/PreMatchPredictionBreakdown";
import ClaudeAnalysis from "@/components/ClaudeAnalysis";
import { WinProbabilityChart, AlgorithmRadarChart, PreMatchRadarChart } from "@/components/Charts";
import { ArrowRight, Spinner, MapPin, CalendarBlank } from "@phosphor-icons/react";

export default function PreMatch() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { getTeamSquad, fetchMatchPrediction, fetchBetaPrediction, fetchConsultation, sendChat, fetchClaudeAnalysis, clearClaudeAnalysis } = useMatchData();
  const [matchInfo, setMatchInfo] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [claudeData, setClaudeData] = useState(null);
  const [claudeLoading, setClaudeLoading] = useState(false);
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
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId]);

  const handlePredict = async () => {
    setPredLoading(true);
    const res = await fetchMatchPrediction(matchId);
    if (res?.prediction) setPrediction(res.prediction);
    setPredLoading(false);
  };

  const handleClaudeAnalysis = async () => {
    setClaudeLoading(true);
    // Clear cache to force fresh analysis
    await clearClaudeAnalysis(matchId);
    const res = await fetchClaudeAnalysis(matchId, true);
    if (res) setClaudeData(res);
    setClaudeLoading(false);
  };

  // Load cached claude analysis on mount (GET, no generation)
  useEffect(() => {
    const loadCached = async () => {
      const res = await fetchClaudeAnalysis(matchId, false);
      if (res && res.analysis) setClaudeData(res);
    };
    if (matchId && matchInfo) loadCached();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId, matchInfo]);

  const team1 = matchInfo?.team1 || "Team A";
  const team2 = matchInfo?.team2 || "Team B";
  const t1Short = matchInfo?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchInfo?.team2Short || team2.slice(0, 3).toUpperCase();

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
              {/* Section 1: Algorithm-Based Prediction (11-factor) */}
              <PreMatchPredictionBreakdown matchId={matchId} team1={t1Short} team2={t2Short} />

              {/* Section 2: Claude Opus Deep Analysis */}
              <ClaudeAnalysis
                data={claudeData}
                matchInfo={matchInfo}
                loading={claudeLoading}
                onFetch={handleClaudeAnalysis}
              />

              {/* Expected Playing XI with Performance */}
              <PlayingXIPerformance matchId={matchId} team1={t1Short} team2={t2Short} />
            </div>

            <div className="lg:col-span-4 space-y-4">
              {/* Consultant Dashboard */}
              <ConsultantDashboard matchId={matchId} team1={t1Short} team2={t2Short} fetchConsultation={fetchConsultation} sendChat={sendChat} />
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
