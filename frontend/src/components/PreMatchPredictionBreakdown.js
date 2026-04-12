import { useState, useEffect } from "react";
import axios from "axios";
import { Spinner, Scales, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise, Target, CloudSun, Lightning, CoinVertical } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";

const API = API_BASE;

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
      const res = await axios.post(
        `${API}/matches/${matchId}/pre-match-predict`,
        {},
        { timeout: 180000 }
      );
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
      const res = await axios.post(
        `${API}/matches/${matchId}/pre-match-predict?force=true`,
        {},
        { timeout: 180000 }
      );
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
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Algorithm Prediction <InfoTooltip text="8-Category pre-match model. Squad-based analysis. No web scraping." /></p>
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

      {/* Factor Breakdown — 8 Categories */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Factor Breakdown (8 Categories) <InfoTooltip text="Squad-based model. Squad (25%) + Form (21%) + Venue (18%) = 64% dominance. No web scraping." /></p>
        </div>
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
        </div>

        {/* Cat 1: Squad Strength (25%) */}
        <FactorBar label="Squad Strength & Balance" weight={factors.squad_strength?.weight || 0.25} logit={factors.squad_strength?.logit_contribution || 0} icon={UsersThree}
          tooltip="Player Impact Score (55% batting + 45% bowling) with balance penalty. Allrounders get 1.35x multiplier."
          team1={t1} team2={t2}
          team1Detail={`Bat ${factors.squad_strength?.team1_batting || "?"} / Bowl ${factors.squad_strength?.team1_bowling || "?"} (Bal: ${factors.squad_strength?.team1_balance || "?"})`}
          team2Detail={`Bat ${factors.squad_strength?.team2_batting || "?"} / Bowl ${factors.squad_strength?.team2_bowling || "?"} (Bal: ${factors.squad_strength?.team2_balance || "?"})`}
        />

        {/* Cat 2: Current Form (21%) */}
        <FactorBar label="Current Season Form" weight={factors.current_form?.weight || 0.21} logit={factors.current_form?.logit_contribution || 0} icon={TrendUp}
          tooltip="IPL 2026 performance. Recency-weighted form score from completed matches. Sample-size damped."
          team1={t1} team2={t2}
          team1Detail={`Score: ${factors.current_form?.team1_form_score || 50} | ${factors.current_form?.team1_wins || 0}W ${factors.current_form?.team1_matches_played || 0} played`}
          team2Detail={`Score: ${factors.current_form?.team2_form_score || 50} | ${factors.current_form?.team2_wins || 0}W ${factors.current_form?.team2_matches_played || 0} played`}
        />

        {/* Cat 3: Venue + Home (18%) */}
        <FactorBar label="Venue + Pitch + Home" weight={factors.venue_pitch_home?.weight || 0.18} logit={factors.venue_pitch_home?.logit_contribution || 0} icon={House}
          tooltip={`Pitch: ${factors.venue_pitch_home?.pitch_type || "unknown"}. Avg 1st inn: ${factors.venue_pitch_home?.avg_first_innings || "?"}. Bat 1st win: ${factors.venue_pitch_home?.batting_first_win_pct || "?"}%. Pace: ${factors.venue_pitch_home?.pace_assist || "?"}. Spin: ${factors.venue_pitch_home?.spin_assist || "?"}.`}
          team1={t1} team2={t2}
          team1Detail={factors.venue_pitch_home?.team1_home ? "HOME" : "Away"}
          team2Detail={factors.venue_pitch_home?.team2_home ? "HOME" : "Away"}
        />
        {factors.venue_pitch_home?.pitch_type && (
          <div className="flex items-center justify-between text-[10px] -mt-1.5 mb-1.5 px-1">
            <span className="text-[#007AFF]/80">{factors.venue_pitch_home?.pitch_type} | Avg {factors.venue_pitch_home?.avg_first_innings || "?"}</span>
            <span className="text-[#A3A3A3]">Pace {factors.venue_pitch_home?.pace_assist} | Spin {factors.venue_pitch_home?.spin_assist}</span>
          </div>
        )}

        {/* Cat 4: H2H (11%) */}
        <FactorBar label="Head-to-Head" weight={factors.h2h?.weight || 0.11} logit={factors.h2h?.logit_contribution || 0} icon={Scales}
          tooltip={`H2H from ${factors.h2h?.source === "historical_ipl" ? "IPL 2023-2025" : "IPL 2026 season"}. ${factors.h2h?.total || 0} total matches.`}
          team1={t1} team2={t2}
          team1Detail={`${factors.h2h?.team1_wins || 0} wins`}
          team2Detail={`${factors.h2h?.team2_wins || 0} wins (${factors.h2h?.total || 0} total)`}
        />

        {/* Cat 5: Toss (9%) */}
        <FactorBar label="Toss Impact (Venue)" weight={factors.toss_impact?.weight || 0.09} logit={factors.toss_impact?.logit_contribution || 0} icon={CoinVertical}
          tooltip={factors.toss_impact?.dew_impact_text || `Venue toss data. Dew: ${factors.toss_impact?.dew_factor || "none"}.`}
          team1={t1} team2={t2}
          team1Detail={`${(factors.toss_impact?.match_time_class || (factors.toss_impact?.is_night ? "evening" : "day")).charAt(0).toUpperCase() + (factors.toss_impact?.match_time_class || (factors.toss_impact?.is_night ? "evening" : "day")).slice(1)} | Dew: ${factors.toss_impact?.dew_factor || "none"}`}
          team2Detail={`Pref: ${factors.toss_impact?.preferred_decision || "?"} | Win%: ${Math.round((factors.toss_impact?.toss_win_pct || 0.5) * 100)}%`}
        />
        {factors.toss_impact?.dew_impact_text && (
          <div className="flex items-center text-[9px] -mt-1.5 mb-1.5 px-1">
            <span className={`${factors.toss_impact?.match_time_class === "afternoon" ? "text-[#FF9500]" : factors.toss_impact?.dew_factor === "heavy" ? "text-[#FF9500]" : factors.toss_impact?.dew_factor === "moderate" ? "text-[#FFCC00]/80" : "text-[#525252]"}`}>
              {factors.toss_impact.dew_impact_text}
            </span>
          </div>
        )}

        {/* Cat 6: Bowling Depth (8%) */}
        <FactorBar label="Bowling Depth & Balance" weight={factors.bowling_depth?.weight || 0.08} logit={factors.bowling_depth?.logit_contribution || 0} icon={Target}
          tooltip={`Venue-weighted bowling quality. Pace assist: ${factors.bowling_depth?.venue_pace_assist || "?"}, Spin assist: ${factors.bowling_depth?.venue_spin_assist || "?"}`}
          team1={t1} team2={t2}
          team1Detail={`${factors.bowling_depth?.team1_bowler_count || "?"} bowlers (P${factors.bowling_depth?.team1_pace_count || 0} S${factors.bowling_depth?.team1_spin_count || 0}) VQ:${factors.bowling_depth?.team1_venue_quality || "?"}`}
          team2Detail={`${factors.bowling_depth?.team2_bowler_count || "?"} bowlers (P${factors.bowling_depth?.team2_pace_count || 0} S${factors.bowling_depth?.team2_spin_count || 0}) VQ:${factors.bowling_depth?.team2_venue_quality || "?"}`}
        />

        {/* Cat 7: Conditions (5%) */}
        <FactorBar label="Conditions (Weather/Dew)" weight={factors.conditions?.weight || 0.05} logit={factors.conditions?.logit_contribution || 0} icon={CloudSun}
          tooltip={factors.conditions?.conditions_edge_text || "Real-time weather data."}
          team1={t1} team2={t2}
          team1Detail={`${factors.conditions?.condition || "?"} | ${factors.conditions?.temperature || "?"}C`}
          team2Detail={`Humidity: ${factors.conditions?.humidity || "?"}% | Dew: ${factors.conditions?.dew_factor || "none"}`}
        />
        {factors.conditions?.conditions_edge_text && factors.conditions?.conditions_edge_text !== "Conditions relatively neutral for both teams" && (
          <div className="flex items-center text-[9px] -mt-1.5 mb-1.5 px-1">
            <span className={`${factors.conditions?.favours_team === "team1" ? "text-[#34C759]" : factors.conditions?.favours_team === "team2" ? "text-[#FF3B30]" : "text-[#525252]"}`}>
              {factors.conditions.conditions_edge_text}
            </span>
          </div>
        )}

        {/* Cat 8: Momentum (3%) */}
        <FactorBar label="Momentum (Last 2)" weight={factors.momentum?.weight || 0.03} logit={factors.momentum?.logit_contribution || 0} icon={Lightning}
          tooltip="Last 2 match results (W/L). Real but small signal."
          team1={t1} team2={t2}
          team1Detail={`Last 2: ${(factors.momentum?.team1_last2 || []).join(", ") || "N/A"} (${factors.momentum?.team1_wins_last2 || 0}W)`}
          team2Detail={`Last 2: ${(factors.momentum?.team2_last2 || []).join(", ") || "N/A"} (${factors.momentum?.team2_wins_last2 || 0}W)`}
        />
      </div>

      {/* Expected Playing XI — SportMonks last match + impact points */}
      {data.playing_xi?.team1_xi?.length > 0 && (
        <div className="border border-[#262626] rounded-md p-3 space-y-2" data-testid="prematch-playing-xi">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] text-[#737373] uppercase tracking-[0.15em] font-semibold flex items-center gap-1">
              <UsersThree weight="fill" className="w-3.5 h-3.5 text-[#7C3AED]" />
              Expected Playing XI
              <InfoTooltip text={data.playing_xi.xi_lineup_note || "XI from SportMonks when available; impact_points match the Lucky 11 model card rating."} />
            </p>
            <span className="text-[9px] font-mono text-[#525252]">
              {data.playing_xi.source === "last_match" ? "Last IPL match" : data.playing_xi.source === "squad_estimate" ? "Squad estimate" : data.playing_xi.source || "—"}
              {data.playing_xi.stats_lookback_matches ? ` · last ${data.playing_xi.stats_lookback_matches} stats` : ""}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF] mb-1">{t1}</p>
              <ul className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {(data.playing_xi.team1_xi || []).map((p, i) => (
                  <li key={i} className="flex items-center justify-between text-[10px] gap-2 border-b border-[#1E1E1E] pb-1 last:border-0">
                    <span className="text-[#E5E5E5] truncate">{p.name}</span>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0">
                      {p.impact_points != null ? <span className="text-[#FFCC00] font-bold">{p.impact_points}</span> : "—"}
                      {p.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(p.recent_form_impact)}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30] mb-1">{t2}</p>
              <ul className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {(data.playing_xi.team2_xi || []).map((p, i) => (
                  <li key={i} className="flex items-center justify-between text-[10px] gap-2 border-b border-[#1E1E1E] pb-1 last:border-0">
                    <span className="text-[#E5E5E5] truncate">{p.name}</span>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0">
                      {p.impact_points != null ? <span className="text-[#FFCC00] font-bold">{p.impact_points}</span> : "—"}
                      {p.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(p.recent_form_impact)}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
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
