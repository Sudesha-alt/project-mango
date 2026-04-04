import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Scales, MapPin, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

function FactorBar({ label, weight, logit, icon: Icon, tooltip, team1, team2, team1Detail, team2Detail }) {
  // logit > 0 favors team1, logit < 0 favors team2
  const absLogit = Math.abs(logit);
  const barWidth = Math.min(100, absLogit * 300); // visual scale
  const favorsTeam1 = logit > 0;
  const favorsTeam2 = logit < 0;
  const neutral = absLogit < 0.01;

  return (
    <div className="py-3 border-b border-[#262626] last:border-0 space-y-2" data-testid={`factor-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon weight="bold" className="w-3.5 h-3.5 text-[#007AFF]" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#A3A3A3]">{label}</span>
          {tooltip && <InfoTooltip text={tooltip} />}
        </div>
        <span className="text-[9px] font-mono text-[#737373]">Weight: {(weight * 100).toFixed(0)}%</span>
      </div>
      {/* Two-sided bar */}
      <div className="flex items-center gap-1">
        {/* Team 1 side (left) */}
        <div className="flex-1 flex justify-end">
          <div className="w-full h-2 bg-[#1A1A1A] rounded-l-full relative overflow-hidden">
            {favorsTeam1 && (
              <div className="absolute top-0 right-0 h-full rounded-l-full bg-[#34C759] transition-all duration-500"
                style={{ width: `${barWidth}%` }} />
            )}
            {favorsTeam2 && (
              <div className="absolute top-0 right-0 h-full rounded-l-full bg-[#FF3B30]/20 transition-all duration-500"
                style={{ width: `${barWidth}%` }} />
            )}
          </div>
        </div>
        {/* Center divider */}
        <div className="w-px h-4 bg-[#525252] flex-shrink-0" />
        {/* Team 2 side (right) */}
        <div className="flex-1">
          <div className="w-full h-2 bg-[#1A1A1A] rounded-r-full relative overflow-hidden">
            {favorsTeam2 && (
              <div className="absolute top-0 left-0 h-full rounded-r-full bg-[#34C759] transition-all duration-500"
                style={{ width: `${barWidth}%` }} />
            )}
            {favorsTeam1 && (
              <div className="absolute top-0 left-0 h-full rounded-r-full bg-[#FF3B30]/20 transition-all duration-500"
                style={{ width: `${barWidth}%` }} />
            )}
          </div>
        </div>
      </div>
      {/* Team details row */}
      <div className="flex items-start justify-between gap-2">
        <div className={`flex-1 text-[10px] ${favorsTeam1 ? 'text-[#34C759]' : favorsTeam2 ? 'text-[#FF3B30]' : 'text-[#A3A3A3]'}`}>
          {team1Detail}
        </div>
        <div className={`flex-1 text-right text-[10px] ${favorsTeam2 ? 'text-[#34C759]' : favorsTeam1 ? 'text-[#FF3B30]' : 'text-[#A3A3A3]'}`}>
          {team2Detail}
        </div>
      </div>
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

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/matches/${matchId}/pre-match-predict?force=true`);
      if (res.data && !res.data.error) setData(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  if (!data) {
    return (
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-5" data-testid="prematch-predict-trigger">
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3 flex items-center gap-1">Algorithm Prediction <InfoTooltip text="Pre-match win confidence: 5 weighted factors (H2H, Venue, Form, Squad, Home) combined via logistic model with Platt calibration." /></p>
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
  const oddsDir = data.odds_direction || {};
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
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Algorithm Prediction <InfoTooltip text="Pre-match win confidence using 5 weighted factors combined via logistic model with Platt calibration. Data from ESPNcricinfo/Cricbuzz via GPT-5.4 web search." /></p>
          <button onClick={handleRefresh} disabled={loading} data-testid="refresh-prediction-btn"
            className="flex items-center gap-1 text-[10px] text-[#737373] hover:text-[#007AFF] transition-colors disabled:opacity-50 font-bold uppercase tracking-wider">
            {loading ? <Spinner className="w-3 h-3 animate-spin" /> : <ArrowsClockwise weight="bold" className="w-3 h-3" />} Re-Predict
          </button>
        </div>
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
        {/* Odds Direction Indicator */}
        {oddsDir.team1 && oddsDir.team1 !== "new" && (
          <div className="flex items-center justify-between mt-2 px-2 py-1.5 bg-[#0A0A0A] rounded-md" data-testid="odds-direction">
            <div className="flex items-center gap-1.5">
              {oddsDir.team1 === "up" ? <TrendUp weight="bold" className="w-3.5 h-3.5 text-[#34C759]" /> : oddsDir.team1 === "down" ? <TrendDown weight="bold" className="w-3.5 h-3.5 text-[#FF3B30]" /> : <Minus weight="bold" className="w-3.5 h-3.5 text-[#737373]" />}
              <span className="text-[10px] font-mono" style={{ color: oddsDir.team1 === "up" ? "#34C759" : oddsDir.team1 === "down" ? "#FF3B30" : "#737373" }}>
                {t1} {oddsDir.team1_change > 0 ? "+" : ""}{oddsDir.team1_change}%
              </span>
            </div>
            <span className="text-[9px] text-[#525252] font-mono flex items-center gap-1">
              vs prev: {oddsDir.previous_team1_prob}% / {oddsDir.previous_team2_prob}%
              <InfoTooltip text="Shows how the prediction changed compared to the previous run. Green = odds improved, Red = odds dropped. This helps you spot momentum shifts." />
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono" style={{ color: oddsDir.team2 === "up" ? "#34C759" : oddsDir.team2 === "down" ? "#FF3B30" : "#737373" }}>
                {oddsDir.team2_change > 0 ? "+" : ""}{oddsDir.team2_change}% {t2}
              </span>
              {oddsDir.team2 === "up" ? <TrendUp weight="bold" className="w-3.5 h-3.5 text-[#34C759]" /> : oddsDir.team2 === "down" ? <TrendDown weight="bold" className="w-3.5 h-3.5 text-[#FF3B30]" /> : <Minus weight="bold" className="w-3.5 h-3.5 text-[#737373]" />}
            </div>
          </div>
        )}
      </div>

      {/* Factor Breakdown — Two-sided Team 1 vs Team 2 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Factor Breakdown <InfoTooltip text="Each factor shows which team benefits. Green = advantage for that side, Red = disadvantage. The bar extends toward the favored team." /></p>
          {pred.uses_player_data && (
            <span className="text-[8px] px-1.5 py-0.5 bg-[#7C3AED]/15 text-[#7C3AED] rounded font-bold uppercase tracking-wider" data-testid="uses-player-data-badge">Player-Level Data</span>
          )}
        </div>
        {/* Column headers */}
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
        </div>

        <FactorBar label="Head-to-Head (5yr)" weight={factors.h2h?.weight || 0.25} logit={factors.h2h?.logit_contribution || 0} icon={Scales}
          tooltip="Win ratio from all IPL matches between these two teams over the last 5 years (2021-2026). More wins = higher logit contribution."
          team1={t1} team2={t2}
          team1Detail={`${factors.h2h?.team1_wins || 0} wins`}
          team2Detail={`${factors.h2h?.team2_wins || 0} wins`}
        />

        <FactorBar label="Venue Performance" weight={factors.venue?.weight || 0.20} logit={factors.venue?.logit_contribution || 0} icon={MapPin}
          tooltip="Average score and win percentage at this specific ground for each team. Includes first/second innings scoring trends."
          team1={t1} team2={t2}
          team1Detail={<>Avg {Math.round(factors.venue?.team1_avg_score || 0)}, Win {Math.round(factors.venue?.team1_win_pct || 0)}%{factors.venue?.is_team1_home && <span className="text-[#FFCC00] ml-1">(Home)</span>}</>}
          team2Detail={<>Win {Math.round(factors.venue?.team2_win_pct || 0)}%, Avg {Math.round(factors.venue?.team2_avg_score || 0)}{factors.venue?.is_team2_home && <span className="text-[#FFCC00] ml-1">(Home)</span>}</>}
        />

        <FactorBar label="Recent Form" weight={factors.form?.weight || 0.25} logit={factors.form?.logit_contribution || 0} icon={TrendUp}
          tooltip="Win/loss record from the last 5 IPL 2026 matches for each team. Captures current momentum and form streaks."
          team1={t1} team2={t2}
          team1Detail={`${factors.form?.team1_last5_wins || 0}W-${factors.form?.team1_last5_losses || 0}L (${factors.form?.team1_last5_win_pct || 50}%)`}
          team2Detail={`${factors.form?.team2_last5_wins || 0}W-${factors.form?.team2_last5_losses || 0}L (${factors.form?.team2_last5_win_pct || 50}%)`}
        />

        <FactorBar label="Squad Strength" weight={factors.squad?.weight || 0.20} logit={factors.squad?.logit_contribution || 0} icon={UsersThree}
          tooltip="Batting depth rating (55% weight) + bowling attack quality (45%). Based on key player averages, strike rates, and overseas impact."
          team1={t1} team2={t2}
          team1Detail={`Bat ${factors.squad?.team1_batting_rating || "?"} / Bowl ${factors.squad?.team1_bowling_rating || "?"}`}
          team2Detail={`Bat ${factors.squad?.team2_batting_rating || "?"} / Bowl ${factors.squad?.team2_bowling_rating || "?"}`}
        />

        <FactorBar label="Home Advantage" weight={factors.home_advantage?.weight || 0.10} logit={factors.home_advantage?.logit_contribution || 0} icon={House}
          tooltip="Teams playing at their home ground get a small logit boost (+0.25). Accounts for crowd support, familiarity with pitch and conditions."
          team1={t1} team2={t2}
          team1Detail={factors.venue?.is_team1_home ? "Home ground" : "Away"}
          team2Detail={factors.venue?.is_team2_home ? "Home ground" : "Away"}
        />
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
