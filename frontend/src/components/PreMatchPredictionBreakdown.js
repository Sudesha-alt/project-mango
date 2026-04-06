import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Scales, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise, Sword, Target, FirstAidKit, CloudSun, Lightning, CoinVertical, Mountains } from "@phosphor-icons/react";
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
        <p className="text-xs text-[#A3A3A3] mb-3">10-Category Model: Squad + Form + Venue + H2H + Toss + Matchups + Bowling + Injuries + Conditions + Momentum</p>
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
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Algorithm Prediction <InfoTooltip text="10-Category pre-match model. Research-validated weights. Categories 1-3 (56%) dominate. No hard-capping." /></p>
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
          Model confidence: {pred.confidence || "—"} | Logit: {pred.combined_logit || "—"}
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

      {/* Factor Breakdown — 10 Categories (Research-Validated) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Factor Breakdown (10 Categories) <InfoTooltip text="Research-validated weights. Squad (22%) + Form (18%) + Venue (16%) = 56% dominance. Data from 2023-2026 only." /></p>
          {pred.uses_player_data && (
            <span className="text-[8px] px-1.5 py-0.5 bg-[#7C3AED]/15 text-[#7C3AED] rounded font-bold uppercase tracking-wider" data-testid="uses-player-data-badge">Player-Level Data</span>
          )}
        </div>
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
        </div>

        {/* Cat 1: Squad Strength (22%) */}
        <FactorBar label="Squad Strength & Balance" weight={factors.squad_strength?.weight || 0.22} logit={factors.squad_strength?.logit_contribution || 0} icon={UsersThree}
          tooltip="Player Impact Score (55% batting + 45% bowling) with balance penalty. Allrounders get 1.35x multiplier."
          team1={t1} team2={t2}
          team1Detail={`Bat ${factors.squad_strength?.team1_batting || "?"} / Bowl ${factors.squad_strength?.team1_bowling || "?"} (Bal: ${factors.squad_strength?.team1_balance || "?"})`}
          team2Detail={`Bat ${factors.squad_strength?.team2_batting || "?"} / Bowl ${factors.squad_strength?.team2_bowling || "?"} (Bal: ${factors.squad_strength?.team2_balance || "?"})`}
        />

        {/* Cat 2: Current Form (18%) */}
        <FactorBar label="Current Season Form" weight={factors.current_form?.weight || 0.18} logit={factors.current_form?.logit_contribution || 0} icon={TrendUp}
          tooltip="IPL 2026 win/loss with exponential decay. NRR differential included. Sample-size damped."
          team1={t1} team2={t2}
          team1Detail={`${factors.current_form?.team1_record || "?W/?L"} (${factors.current_form?.team1_form_pct || 50}%) NRR: ${factors.current_form?.team1_nrr || 0}`}
          team2Detail={`${factors.current_form?.team2_record || "?W/?L"} (${factors.current_form?.team2_form_pct || 50}%) NRR: ${factors.current_form?.team2_nrr || 0}`}
        />

        {/* Cat 3: Venue + Home (16%) */}
        <FactorBar label="Venue + Pitch + Home" weight={factors.venue_pitch_home?.weight || 0.16} logit={factors.venue_pitch_home?.logit_contribution || 0} icon={House}
          tooltip="Venue win%, avg scores, home ground boost (57.91% historical), pitch type interaction."
          team1={t1} team2={t2}
          team1Detail={`${factors.venue_pitch_home?.team1_home ? "HOME" : "Away"} | Win ${factors.venue_pitch_home?.team1_venue_win_pct || "?"}%`}
          team2Detail={`${factors.venue_pitch_home?.team2_home ? "HOME" : "Away"} | Win ${factors.venue_pitch_home?.team2_venue_win_pct || "?"}%`}
        />

        {/* Cat 4: H2H (10%) */}
        <FactorBar label="Head-to-Head (2023-26)" weight={factors.h2h?.weight || 0.10} logit={factors.h2h?.logit_contribution || 0} icon={Scales}
          tooltip="Recency-weighted H2H from last 3 IPL seasons. Damped by sample size (need 4+ games)."
          team1={t1} team2={t2}
          team1Detail={`${factors.h2h?.team1_wins || 0} wins`}
          team2Detail={`${factors.h2h?.team2_wins || 0} wins (${factors.h2h?.total || 0} total)`}
        />

        {/* Cat 5: Toss (8%) */}
        <FactorBar label="Toss Impact (Venue)" weight={factors.toss_impact?.weight || 0.08} logit={factors.toss_impact?.logit_contribution || 0} icon={CoinVertical}
          tooltip={`Venue-specific toss data. Preferred: ${factors.toss_impact?.preferred_decision || "?"}. Toss winner wins ${Math.round((factors.toss_impact?.toss_win_pct || 0.52) * 100)}%.`}
          team1={t1} team2={t2}
          team1Detail={`${factors.toss_impact?.is_night ? "Night" : "Day"} | ${factors.toss_impact?.condition || "—"}`}
          team2Detail={`Pref: ${factors.toss_impact?.preferred_decision || "?"} | Wt: ${factors.toss_impact?.model_weight || "MED"}`}
        />

        {/* Cat 6: Matchups (8%) */}
        <FactorBar label="Key Player Matchups" weight={factors.matchup_index?.weight || 0.08} logit={factors.matchup_index?.logit_contribution || 0} icon={Sword}
          tooltip="Batter vs bowler H2H records. Top 4 batters vs top 3 bowlers weighted more heavily."
          team1={t1} team2={t2}
          team1Detail={`Score: ${factors.matchup_index?.team1_matchup_score || "—"} (${factors.matchup_index?.team1_matchups_count || 0} matchups)`}
          team2Detail={`Score: ${factors.matchup_index?.team2_matchup_score || "—"} (${factors.matchup_index?.team2_matchups_count || 0} matchups)`}
        />

        {/* Cat 7: Bowling Depth (7%) */}
        <FactorBar label="Bowling Depth & Balance" weight={factors.bowling_depth?.weight || 0.07} logit={factors.bowling_depth?.logit_contribution || 0} icon={Target}
          tooltip="Quality bowling overs available (bowler rating × 4 overs each). Variety (pace+spin) bonus."
          team1={t1} team2={t2}
          team1Detail={`${factors.bowling_depth?.team1_bowler_count || "?"} bowlers | Q: ${factors.bowling_depth?.team1_quality_score || "?"}`}
          team2Detail={`${factors.bowling_depth?.team2_bowler_count || "?"} bowlers | Q: ${factors.bowling_depth?.team2_quality_score || "?"}`}
        />

        {/* Cat 8: Injuries (5%) */}
        <FactorBar label="Injuries & Availability" weight={factors.injury_availability?.weight || 0.05} logit={factors.injury_availability?.logit_contribution || 0} icon={FirstAidKit}
          tooltip={`Impact: T1=${factors.injury_availability?.team1_impact || 0}, T2=${factors.injury_availability?.team2_impact || 0}. Manual overrides take priority. Allrounder absence = 1.35x impact.`}
          team1={t1} team2={t2}
          team1Detail={factors.injury_availability?.team1_injuries?.length ? factors.injury_availability.team1_injuries.map(i => i.player).join(", ") : "No injuries"}
          team2Detail={factors.injury_availability?.team2_injuries?.length ? factors.injury_availability.team2_injuries.map(i => i.player).join(", ") : "No injuries"}
        />

        {/* Cat 9: Conditions (4%) */}
        <FactorBar label="Conditions (Dew/Weather)" weight={factors.conditions?.weight || 0.04} logit={factors.conditions?.logit_contribution || 0} icon={CloudSun}
          tooltip={factors.conditions?.conditions_summary || "Day/night, dew probability, pace/spin conditions."}
          team1={t1} team2={t2}
          team1Detail={`${factors.conditions?.is_night ? "Night" : "Day"} | Dew: ${factors.conditions?.dew_probability || "?"}`}
          team2Detail={`Pace: ${factors.conditions?.pace_factor || "?"}/10 | Spin: ${factors.conditions?.spin_factor || "?"}/10`}
        />

        {/* Cat 10: Momentum (2%) */}
        <FactorBar label="Momentum & Psychology" weight={factors.momentum?.weight || 0.02} logit={factors.momentum?.logit_contribution || 0} icon={Lightning}
          tooltip="Win streak (capped contribution). Max 2% total shift. Real but small signal."
          team1={t1} team2={t2}
          team1Detail={`Streak: ${(factors.momentum?.team1_streak || 0) > 0 ? "+" : ""}${factors.momentum?.team1_streak || 0} | L10: ${factors.momentum?.team1_last10 || "?"}W`}
          team2Detail={`Streak: ${(factors.momentum?.team2_streak || 0) > 0 ? "+" : ""}${factors.momentum?.team2_streak || 0} | L10: ${factors.momentum?.team2_last10 || "?"}W`}
        />
      </div>

      <p className="text-[9px] text-[#737373] font-mono text-right">
        Computed: {new Date(data.computed_at).toLocaleString()}
      </p>
    </div>
  );
}
