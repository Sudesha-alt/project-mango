import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Scales, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise, Sword } from "@phosphor-icons/react";
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

export default function PreMatchPredictionBreakdown({ matchId, team1, team2, onDataUpdate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/predictions/upcoming`);
        const match = (res.data.predictions || []).find(p => p.matchId === matchId);
        if (match) {
          setData(match);
          if (onDataUpdate) onDataUpdate(match);
        }
      } catch (e) { /* ignore */ }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  const handlePredict = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/matches/${matchId}/pre-match-predict`);
      if (res.data && !res.data.error) {
        setData(res.data);
        if (onDataUpdate) onDataUpdate(res.data);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/matches/${matchId}/pre-match-predict?force=true`);
      if (res.data && !res.data.error) {
        setData(res.data);
        if (onDataUpdate) onDataUpdate(res.data);
      }
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

      {/* Factor Breakdown — 5 Factors (Post-Auction Model) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Factor Breakdown (5 Factors) <InfoTooltip text="Each factor shows which team benefits. Green = advantage for that side, Red = disadvantage. Weights: Form 35%, Squad 25%, Team Combo 20%, Home 15%, H2H/Pitch 5%." /></p>
          {pred.uses_player_data && (
            <span className="text-[8px] px-1.5 py-0.5 bg-[#7C3AED]/15 text-[#7C3AED] rounded font-bold uppercase tracking-wider" data-testid="uses-player-data-badge">Player-Level Data</span>
          )}
        </div>
        {/* Column headers */}
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
        </div>

        <FactorBar label="Form (IPL 2026)" weight={factors.form?.weight || 0.35} logit={factors.form?.logit_contribution || 0} icon={TrendUp}
          tooltip="Win/loss record from last 5 IPL 2026 matches + player buzz sentiment. Sample-size damped."
          team1={t1} team2={t2}
          team1Detail={`${factors.form?.team1_record || "0W/0L"} (${factors.form?.team1_form_pct || 50}%)`}
          team2Detail={`${factors.form?.team2_record || "0W/0L"} (${factors.form?.team2_form_pct || 50}%)`}
        />

        <FactorBar label="Squad Strength" weight={factors.squad_strength?.weight || 0.25} logit={factors.squad_strength?.logit_contribution || 0} icon={UsersThree}
          tooltip="Batting depth (55%) + bowling attack quality (45%). Based on 2026 roster star ratings and role-weighted averages."
          team1={t1} team2={t2}
          team1Detail={`Bat ${factors.squad_strength?.team1_batting || "?"} / Bowl ${factors.squad_strength?.team1_bowling || "?"} (${factors.squad_strength?.team1_overall || "?"})`}
          team2Detail={`Bat ${factors.squad_strength?.team2_batting || "?"} / Bowl ${factors.squad_strength?.team2_bowling || "?"} (${factors.squad_strength?.team2_overall || "?"})`}
        />

        <FactorBar label="Team Combination" weight={factors.team_combination?.weight || 0.20} logit={factors.team_combination?.logit_contribution || 0} icon={Sword}
          tooltip="XI settled-ness, overseas balance, role coverage, star power. Higher = better team combination clarity."
          team1={t1} team2={t2}
          team1Detail={`Score: ${factors.team_combination?.team1_score || "—"}`}
          team2Detail={`Score: ${factors.team_combination?.team2_score || "—"}`}
        />

        <FactorBar label="Home Advantage" weight={factors.home_advantage?.weight || 0.15} logit={factors.home_advantage?.logit_contribution || 0} icon={House}
          tooltip="Home ground boost + pitch type advantage (bowling/batting). Accounts for crowd, conditions knowledge."
          team1={t1} team2={t2}
          team1Detail={factors.home_advantage?.team1_home ? "Home" : "Away"}
          team2Detail={factors.home_advantage?.team2_home ? "Home" : "Away"}
        />

        <FactorBar label="H2H + Pitch" weight={factors.h2h_pitch?.weight || 0.05} logit={factors.h2h_pitch?.logit_contribution || 0} icon={Scales}
          tooltip="Head-to-head record between these teams + pitch type and dew factor."
          team1={t1} team2={t2}
          team1Detail={`H2H: ${factors.h2h_pitch?.h2h_record || "0-0"}`}
          team2Detail={`Pitch: ${factors.h2h_pitch?.pitch_type || "balanced"}`}
        />
      </div>

      <p className="text-[9px] text-[#737373] font-mono text-right">
        Computed: {new Date(data.computed_at).toLocaleString()}
      </p>
    </div>
  );
}
