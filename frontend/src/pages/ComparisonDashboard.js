import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkle, Robot, ArrowLeft, Trophy, Equals, ArrowRight, Lightning } from "@phosphor-icons/react";
import axios from "axios";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

function ProbBar({ label, pct, color }) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-[#737373] uppercase">{label}</span>
        <span className="text-[10px] font-mono font-bold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-[#1A1A1A] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function MatchCompareCard({ match, algoPred, claudeAnalysis }) {
  const t1 = match.team1Short || "T1";
  const t2 = match.team2Short || "T2";

  const algoT1 = algoPred?.prediction?.win_probability || 50;
  const algoT2 = 100 - algoT1;

  const ca = claudeAnalysis?.analysis || {};
  const claudeT1 = ca.team1_win_pct || 50;
  const claudeT2 = ca.team2_win_pct || 50;

  const diff = Math.abs(algoT1 - claudeT1);
  const agreement = diff < 5 ? "HIGH" : diff < 15 ? "MODERATE" : "LOW";
  const agreementColor = agreement === "HIGH" ? "#34C759" : agreement === "MODERATE" ? "#FFCC00" : "#FF3B30";

  const algoWinner = algoT1 > algoT2 ? t1 : t2;
  const claudeWinner = claudeT1 > claudeT2 ? t1 : t2;
  const sameWinner = algoWinner === claudeWinner;

  return (
    <div className="bg-[#0A0A0A] border border-[#262626] rounded-xl p-4 hover:border-[#525252] transition-colors" data-testid={`compare-card-${match.matchId}`}>
      {/* Match Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-white">{t1} vs {t2}</span>
          <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold uppercase ${
            match.status === "live" ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
            match.status === "Completed" ? "bg-[#525252]/20 text-[#525252]" :
            "bg-[#007AFF]/20 text-[#007AFF]"
          }`}>{match.status}</span>
        </div>
        <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold`}
          style={{ backgroundColor: agreementColor + "20", color: agreementColor }}>
          {agreement} AGREEMENT
        </span>
      </div>

      {/* Venue */}
      <p className="text-[9px] text-[#737373] mb-3">M{match.match_number} | {match.venue}</p>

      {/* Side-by-side comparison */}
      <div className="grid grid-cols-2 gap-3">
        {/* Algorithm */}
        <div className="bg-[#141414] border border-[#007AFF]/20 rounded-lg p-3">
          <div className="flex items-center gap-1 mb-2">
            <Robot size={12} className="text-[#007AFF]" />
            <span className="text-[9px] font-bold text-[#007AFF] uppercase tracking-wider">Algorithm</span>
          </div>
          {algoPred ? (
            <>
              <ProbBar label={t1} pct={algoT1.toFixed(0)} color="#007AFF" />
              <ProbBar label={t2} pct={algoT2.toFixed(0)} color="#FF3B30" />
              <div className="mt-2 flex items-center gap-1">
                <Trophy size={10} className="text-[#FFCC00]" />
                <span className="text-[10px] font-bold text-white">{algoWinner}</span>
              </div>
            </>
          ) : (
            <p className="text-[9px] text-[#525252]">Not generated</p>
          )}
        </div>

        {/* Claude */}
        <div className="bg-[#141414] border border-[#A78BFA]/20 rounded-lg p-3">
          <div className="flex items-center gap-1 mb-2">
            <Sparkle size={12} className="text-[#A78BFA]" weight="fill" />
            <span className="text-[9px] font-bold text-[#A78BFA] uppercase tracking-wider">Claude Opus</span>
          </div>
          {claudeAnalysis?.analysis ? (
            <>
              <ProbBar label={t1} pct={claudeT1} color="#A78BFA" />
              <ProbBar label={t2} pct={claudeT2} color="#FF6B6B" />
              <div className="mt-2 flex items-center gap-1">
                <Trophy size={10} className="text-[#FFCC00]" />
                <span className="text-[10px] font-bold text-white">{claudeWinner}</span>
              </div>
              {ca.confidence && (
                <p className="text-[8px] text-[#737373] mt-1">Confidence: {ca.confidence}</p>
              )}
            </>
          ) : (
            <p className="text-[9px] text-[#525252]">Not generated</p>
          )}
        </div>
      </div>

      {/* Agreement indicator */}
      <div className="mt-3 flex items-center justify-center gap-2">
        {sameWinner && algoPred && claudeAnalysis?.analysis ? (
          <div className="flex items-center gap-1.5 text-[#34C759]">
            <Equals size={12} />
            <span className="text-[10px] font-bold">Both pick {algoWinner} ({diff.toFixed(0)}% gap)</span>
          </div>
        ) : algoPred && claudeAnalysis?.analysis ? (
          <div className="flex items-center gap-1.5 text-[#FF3B30]">
            <Lightning size={12} weight="fill" />
            <span className="text-[10px] font-bold">DISAGREEMENT: Algo={algoWinner} | Claude={claudeWinner}</span>
          </div>
        ) : null}
      </div>

      {/* Claude headline */}
      {ca.headline && (
        <p className="text-[9px] text-[#A3A3A3] mt-2 italic border-l-2 border-[#A78BFA]/30 pl-2">{ca.headline}</p>
      )}
    </div>
  );
}

export default function ComparisonDashboard() {
  const navigate = useNavigate();
  const [predictions, setPredictions] = useState({});
  const [claudeData, setClaudeData] = useState({});
  const [loading, setLoading] = useState(true);
  const [allMatches, setAllMatches] = useState([]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        // Fetch schedule directly
        const schedRes = await axios.get(`${API}/schedule`);
        const sched = schedRes.data;
        const matches = [...(sched.live || []), ...(sched.upcoming || []), ...(sched.completed || [])].slice(0, 15);
        setAllMatches(matches);

        if (matches.length === 0) { setLoading(false); return; }

        // Load cached predictions in batches of 5
        const predMap = {};
        const claudeMap = {};

        for (let i = 0; i < matches.length; i += 5) {
          const batch = matches.slice(i, i + 5);
          const results = await Promise.allSettled([
            ...batch.map(m => axios.get(`${API}/predictions/${m.matchId}/pre-match`).then(r => ({ id: m.matchId, type: "pred", data: r.data }))),
            ...batch.map(m => axios.get(`${API}/matches/${m.matchId}/claude-analysis`).then(r => ({ id: m.matchId, type: "claude", data: r.data }))),
          ]);
          results.forEach(r => {
            if (r.status === "fulfilled" && r.value?.data) {
              if (r.value.type === "pred") predMap[r.value.id] = r.value.data;
              if (r.value.type === "claude" && r.value.data.analysis) claudeMap[r.value.id] = r.value.data;
            }
          });
        }

        setPredictions(predMap);
        setClaudeData(claudeMap);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    load();
  }, []);

  // Summary stats
  const matchesWithBoth = allMatches.filter(m => predictions[m.matchId] && claudeData[m.matchId]?.analysis);
  const agreements = matchesWithBoth.filter(m => {
    const algoT1 = predictions[m.matchId]?.prediction?.win_probability || 50;
    const claudeT1 = claudeData[m.matchId]?.analysis?.team1_win_pct || 50;
    const algoWin = algoT1 > 50 ? "t1" : "t2";
    const claudeWin = claudeT1 > 50 ? "t1" : "t2";
    return algoWin === claudeWin;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-6" data-testid="comparison-dashboard">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate("/")} className="text-[#737373] hover:text-white transition-colors" data-testid="back-btn">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-xl font-black uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
            <span className="text-[#007AFF]">Algorithm</span>
            <span className="text-[#525252] mx-2">vs</span>
            <span className="text-[#A78BFA]">Claude Opus</span>
          </h1>
          <p className="text-[10px] text-[#737373]">Side-by-side comparison across all IPL 2026 matches</p>
        </div>
      </div>

      {/* Summary Strip */}
      {matchesWithBoth.length > 0 && (
        <div className="flex gap-4 mb-6 bg-[#141414] border border-[#262626] rounded-xl px-5 py-3">
          <div className="text-center">
            <p className="text-[9px] text-[#737373] uppercase">Matches Compared</p>
            <p className="text-xl font-black font-mono text-white">{matchesWithBoth.length}</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-[#737373] uppercase">Same Winner</p>
            <p className="text-xl font-black font-mono text-[#34C759]">{agreements.length}</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-[#737373] uppercase">Disagreements</p>
            <p className="text-xl font-black font-mono text-[#FF3B30]">{matchesWithBoth.length - agreements.length}</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-[#737373] uppercase">Agreement %</p>
            <p className="text-xl font-black font-mono text-[#FFCC00]">
              {matchesWithBoth.length > 0 ? ((agreements.length / matchesWithBoth.length) * 100).toFixed(0) : 0}%
            </p>
          </div>
        </div>
      )}

      {/* Match Cards Grid */}
      {loading ? (
        <div className="text-center py-10">
          <div className="animate-spin w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-xs text-[#737373]">Loading predictions...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {allMatches.map(m => (
            <MatchCompareCard
              key={m.matchId}
              match={m}
              algoPred={predictions[m.matchId]}
              claudeAnalysis={claudeData[m.matchId]}
            />
          ))}
        </div>
      )}

      {allMatches.length === 0 && !loading && (
        <div className="text-center py-10">
          <p className="text-sm text-[#737373]">No matches loaded. Go to home page and load the schedule first.</p>
        </div>
      )}
    </div>
  );
}
