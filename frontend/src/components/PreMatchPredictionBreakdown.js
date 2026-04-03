import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Scales, MapPin, TrendUp, UsersThree, House } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

function FactorBar({ label, weight, logit, icon: Icon, children }) {
  const pct = Math.max(0, Math.min(100, 50 + logit * 200));
  return (
    <div className="space-y-1.5 py-2 border-b border-[#262626] last:border-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon weight="bold" className="w-3.5 h-3.5 text-[#007AFF]" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#A3A3A3]">{label}</span>
        </div>
        <span className="text-[9px] font-mono text-[#737373]">Weight: {(weight * 100).toFixed(0)}%</span>
      </div>
      {/* Direction bar */}
      <div className="h-1.5 bg-[#262626] rounded-full relative">
        <div className="absolute top-0 left-1/2 w-px h-full bg-[#737373]/30" />
        {pct >= 50 ? (
          <div className="absolute top-0 left-1/2 h-full rounded-r-full bg-[#34C759] transition-all duration-500" style={{ width: `${pct - 50}%` }} />
        ) : (
          <div className="absolute top-0 h-full rounded-l-full bg-[#FF3B30] transition-all duration-500" style={{ left: `${pct}%`, width: `${50 - pct}%` }} />
        )}
      </div>
      <div className="text-[10px] text-[#A3A3A3]">{children}</div>
    </div>
  );
}

export default function PreMatchPredictionBreakdown({ matchId, team1, team2 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`);
        const match = (res.data.predictions || []).find(p => p.matchId === matchId);
        if (match) setData(match);
      } catch (e) { /* ignore */ }
    };
    load();
  }, [matchId]);

  const handlePredict = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/matches/${matchId}/pre-match-predict`);
      if (res.data && !res.data.error) setData(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  if (!data) {
    return (
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-5" data-testid="prematch-predict-trigger">
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3">Algorithm Prediction</p>
        <p className="text-xs text-[#A3A3A3] mb-3">H2H (5yr) + Venue Stats + Recent Form + Squad Strength</p>
        <button onClick={handlePredict} disabled={loading} data-testid="run-prematch-predict-btn"
          className="w-full flex items-center justify-center gap-2 bg-[#007AFF] text-white py-2.5 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-blue-600 transition-colors disabled:opacity-50">
          {loading ? <><Spinner className="w-4 h-4 animate-spin" /> Fetching Stats...</> : <><Scales weight="fill" className="w-4 h-4" /> Run Prediction</>}
        </button>
      </div>
    );
  }

  const pred = data.prediction || {};
  const factors = pred.factors || {};
  const stats = data.stats || {};
  const t1 = data.team1Short || team1;
  const t2 = data.team2Short || team2;
  const t1Prob = pred.team1_win_prob || 50;
  const t2Prob = pred.team2_win_prob || 50;
  const t1Color = t1Prob > t2Prob ? "#34C759" : "#FF3B30";
  const t2Color = t2Prob > t1Prob ? "#34C759" : "#FF3B30";

  return (
    <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4" data-testid="prematch-prediction-breakdown">
      {/* Main probability */}
      <div>
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3">Algorithm Prediction</p>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-lg font-black font-mono" style={{ color: t1Color, fontFamily: "'Barlow Condensed'" }}>{t1} {t1Prob}%</span>
          <span className="text-lg font-black font-mono" style={{ color: t2Color, fontFamily: "'Barlow Condensed'" }}>{t2Prob}% {t2}</span>
        </div>
        <div className="flex h-3 rounded-full overflow-hidden bg-[#262626]">
          <div className="h-full transition-all duration-700 rounded-l-full" style={{ width: `${t1Prob}%`, backgroundColor: t1Color }} />
          <div className="h-full transition-all duration-700 rounded-r-full" style={{ width: `${t2Prob}%`, backgroundColor: t2Color }} />
        </div>
        <p className="text-center text-[9px] text-[#737373] font-mono mt-1">
          Model confidence: {pred.confidence}% | Calibrated: {(pred.calibrated_probability * 100).toFixed(1)}%
        </p>
      </div>

      {/* Factor Breakdown */}
      <div>
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2">Factor Breakdown</p>
        <FactorBar label="Head-to-Head (5yr)" weight={factors.h2h?.weight || 0.25} logit={factors.h2h?.logit_contribution || 0} icon={Scales}>
          {t1} {factors.h2h?.team1_wins || 0} – {factors.h2h?.team2_wins || 0} {t2} ({factors.h2h?.total_matches || 0} matches)
        </FactorBar>

        <FactorBar label="Venue Performance" weight={factors.venue?.weight || 0.20} logit={factors.venue?.logit_contribution || 0} icon={MapPin}>
          {t1}: avg {factors.venue?.team1_avg_score || "?"}, win {factors.venue?.team1_win_pct || "?"}%
          {" | "}
          {t2}: avg {factors.venue?.team2_avg_score || "?"}, win {factors.venue?.team2_win_pct || "?"}%
          {(factors.venue?.is_team1_home || factors.venue?.is_team2_home) && (
            <span className="ml-1 text-[#FFCC00]"> (Home: {factors.venue?.is_team1_home ? t1 : t2})</span>
          )}
        </FactorBar>

        <FactorBar label="Recent Form" weight={factors.form?.weight || 0.25} logit={factors.form?.logit_contribution || 0} icon={TrendUp}>
          {t1}: {factors.form?.team1_last5_wins || 0}W-{factors.form?.team1_last5_losses || 0}L ({factors.form?.team1_last5_win_pct || 50}%)
          {" | "}
          {t2}: {factors.form?.team2_last5_wins || 0}W-{factors.form?.team2_last5_losses || 0}L ({factors.form?.team2_last5_win_pct || 50}%)
        </FactorBar>

        <FactorBar label="Squad Strength" weight={factors.squad?.weight || 0.20} logit={factors.squad?.logit_contribution || 0} icon={UsersThree}>
          {t1}: Bat {factors.squad?.team1_batting_rating || "?"} / Bowl {factors.squad?.team1_bowling_rating || "?"}
          {" | "}
          {t2}: Bat {factors.squad?.team2_batting_rating || "?"} / Bowl {factors.squad?.team2_bowling_rating || "?"}
        </FactorBar>

        <FactorBar label="Home Advantage" weight={factors.home_advantage?.weight || 0.10} logit={factors.home_advantage?.logit_contribution || 0} icon={House}>
          {factors.venue?.is_team1_home ? `${t1} playing at home` : factors.venue?.is_team2_home ? `${t2} playing at home` : "Neutral venue"}
        </FactorBar>
      </div>

      {/* Key Players */}
      {(stats.squad_strength?.team1_key_players?.length > 0 || stats.squad_strength?.team2_key_players?.length > 0) && (
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2">Key Players</p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-[9px] text-[#737373] mb-1">{t1}</p>
              {(stats.squad_strength?.team1_key_players || []).map((p, i) => (
                <p key={i} className="text-[10px] text-[#A3A3A3]">{p}</p>
              ))}
            </div>
            <div>
              <p className="text-[9px] text-[#737373] mb-1">{t2}</p>
              {(stats.squad_strength?.team2_key_players || []).map((p, i) => (
                <p key={i} className="text-[10px] text-[#A3A3A3]">{p}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      <p className="text-[9px] text-[#737373] font-mono text-right">
        Computed: {new Date(data.computed_at).toLocaleString()}
      </p>
    </div>
  );
}
