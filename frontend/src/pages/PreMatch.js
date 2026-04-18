import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import PlayingXIPerformance from "@/components/PlayingXIPerformance";
import ConsultantDashboard from "@/components/ConsultantDashboard";
import PreMatchPredictionBreakdown from "@/components/PreMatchPredictionBreakdown";
import ClaudeAnalysis from "@/components/ClaudeAnalysis";
import CombinedPredictionBlock from "@/components/CombinedPredictionBlock";
import WeatherCard from "@/components/WeatherCard";
import NewsCard from "@/components/NewsCard";
import { WinProbabilityChart, AlgorithmRadarChart, PreMatchRadarChart } from "@/components/Charts";
import { ArrowRight, Spinner, MapPin, CalendarBlank } from "@phosphor-icons/react";
import axios from "axios";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

function clampRadarPct(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return 50;
  return Math.min(100, Math.max(0, n));
}

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
  const [algoData, setAlgoData] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(`${API}/matches/${matchId}/state`, { signal: controller.signal });
        clearTimeout(timeout);
        const data = await res.json();
        const info = data.info || data;
        setMatchInfo(info);
      } catch (e) { console.error("Match state load:", e.name === "AbortError" ? "Timeout" : e); }
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId]);

  // Load cached algo prediction for combined block
  useEffect(() => {
    const loadAlgo = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`, { timeout: 10000 });
        const match = (res.data.predictions || []).find(p => p.matchId === matchId);
        if (match) setAlgoData(match);
      } catch (e) { /* ignore timeout */ }
    };
    if (matchId) loadAlgo();
  }, [matchId]);

  const handlePredict = async () => {
    setPredLoading(true);
    const res = await fetchMatchPrediction(matchId);
    if (res?.prediction) setPrediction(res.prediction);
    setPredLoading(false);
  };

  const handleClaudeAnalysis = async () => {
    setClaudeLoading(true);
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

  // Listen for algo prediction updates from the breakdown component
  const handleAlgoUpdate = useCallback((data) => {
    if (data) setAlgoData(data);
  }, []);

  const team1 = matchInfo?.team1 || "Team A";
  const team2 = matchInfo?.team2 || "Team B";
  const t1Short = matchInfo?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchInfo?.team2Short || team2.slice(0, 3).toUpperCase();

  const [prematchRadarT1, prematchRadarT2] = useMemo(() => {
    const f = algoData?.prediction?.factors;
    if (!f) return [{}, {}];

    const bq = f.batting_quality ?? {};
    const bowq = f.bowling_quality ?? {};
    const arb = f.allrounder_balance ?? {};
    const vb = f.venue_baseline ?? {};
    const h2h = f.h2h_squad_adjusted ?? {};

    const h2hT = Number(h2h.total) || 0;
    const t1h = h2hT > 0 ? (100 * (Number(h2h.team1_wins) || 0)) / h2hT : 50;
    const t2h = h2hT > 0 ? (100 * (Number(h2h.team2_wins) || 0)) / h2hT : 50;

    const bat1 = clampRadarPct(
      typeof bq.team1_share_pct === "number" ? bq.team1_share_pct : Number(bq.team1_batting) || 50
    );
    const bat2 = clampRadarPct(
      typeof bq.team2_share_pct === "number" ? bq.team2_share_pct : Number(bq.team2_batting) || 50
    );
    const bowl1 = clampRadarPct(
      typeof bowq.team1_share_pct === "number" ? bowq.team1_share_pct : Number(bowq.team1_bowling) || 50
    );
    const bowl2 = clampRadarPct(
      typeof bowq.team2_share_pct === "number" ? bowq.team2_share_pct : Number(bowq.team2_bowling) || 50
    );

    const s1a = arb.team1_strength_share_pct;
    const s1b = arb.team1_depth_share_pct;
    const s2a = arb.team2_strength_share_pct;
    const s2b = arb.team2_depth_share_pct;
    const bal1 =
      typeof s1a === "number" && typeof s1b === "number"
        ? clampRadarPct((s1a + s1b) / 2)
        : clampRadarPct(Number(arb.team1_allrounder_strength) || 50);
    const bal2 =
      typeof s2a === "number" && typeof s2b === "number"
        ? clampRadarPct((s2a + s2b) / 2)
        : clampRadarPct(Number(arb.team2_allrounder_strength) || 50);

    const vl = Number(vb.raw_logit);
    const vlSafe = Number.isFinite(vl) ? vl : 0;
    const vScale = 14;
    const vAdj = Math.max(-1.4, Math.min(1.4, vlSafe / 2));
    const venue1 = clampRadarPct(50 + vScale * vAdj);
    const venue2 = clampRadarPct(50 - vScale * vAdj);

    return [
      { batting: bat1, bowling: bowl1, balance: bal1, venue: venue1, h2h: clampRadarPct(t1h) },
      { batting: bat2, bowling: bowl2, balance: bal2, venue: venue2, h2h: clampRadarPct(t2h) },
    ];
  }, [algoData]);

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
              {/* Combined Prediction Block — Algorithm + Claude + Average */}
              <CombinedPredictionBlock
                algoData={algoData}
                claudeData={claudeData}
                team1={t1Short}
                team2={t2Short}
              />

              {/* Algorithm-Based Prediction (5-factor BPR/CSA model) */}
              <PreMatchPredictionBreakdown matchId={matchId} team1={t1Short} team2={t2Short} onDataUpdate={handleAlgoUpdate} />

              {/* Claude Opus Deep Analysis */}
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
                  {matchInfo?.timeIST && <div className="flex justify-between"><span className="text-[#71717A]">Time (IST)</span><span>{matchInfo.timeIST}</span></div>}
                  {matchInfo?.city && <div className="flex justify-between"><span className="text-[#71717A]">City</span><span>{matchInfo.city}</span></div>}
                </div>
              </div>
              {/* Weather Conditions */}
              <WeatherCard matchId={matchId} />
              {/* Match News */}
              <NewsCard matchId={matchId} />
              <PreMatchRadarChart team1={t1Short} team2={t2Short} team1Data={prematchRadarT1} team2Data={prematchRadarT2} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
