import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Spinner, Scales, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise, Target, CloudSun, Lightning } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";
import PreMatchPlayerPerfToolbar, { readLivePlayerPerfPreference } from "./PreMatchPlayerPerfToolbar";
import { buildPreMatchPredictUrl, buildFetchXiRolesAndPredictUrl } from "@/lib/preMatchApi";
import { readImpactFormulaPreference } from "@/lib/impactFormulaPref";

const API = API_BASE;

function phaseFactorSourceLabel(src) {
  if (src === "sportmonks_ball_phases") return "SportMonks ball-by-ball phases";
  if (src === "openai_web") return "Web context";
  if (src === "fallback_xi_proxy") return "XI rating proxy";
  return src || "—";
}

function xiRoleColor(role) {
  if (!role) return "#737373";
  const r = String(role).toLowerCase();
  if (r.includes("wicket") || r.includes("keeper")) return "#FFCC00";
  if (r.includes("all")) return "#34C759";
  if (r.includes("bowl")) return "#FF3B30";
  if (r.includes("bat")) return "#007AFF";
  return "#737373";
}

/** Last 4 completed results for momentum: W/L per game, newest first; pad with —; append record. */
function formatMomentumLastFour(momentum, teamSide) {
  const key4 = teamSide === "team1" ? "team1_last4" : "team2_last4";
  const key2 = teamSide === "team1" ? "team1_last2" : "team2_last2";
  const raw = momentum?.[key4] ?? momentum?.[key2] ?? [];
  const arr = Array.isArray(raw) ? raw : [];
  const normalized = arr.map((r) => {
    const u = String(r ?? "").toUpperCase().trim();
    if (u === "W" || u === "WIN") return "W";
    if (u === "L" || u === "LOSS") return "L";
    return null;
  });
  const slots = [];
  for (let i = 0; i < 4; i += 1) {
    slots.push(normalized[i] ?? "—");
  }
  const wins = normalized.filter((x) => x === "W").length;
  const losses = normalized.filter((x) => x === "L").length;
  const played = wins + losses;
  const record = played > 0 ? ` (${wins}W-${losses}L)` : "";
  return `Last 4 (new→old): ${slots.join(" · ")}${record}`;
}

function FactorBar({ label, weight, logit, icon: Icon, tooltip, team1, team2, team1Detail, team2Detail, reasonLine, favours, claudeVerdict }) {
  // logit > 0 favors team1, logit < 0 favors team2
  const safeLogit = Number.isFinite(logit) ? logit : 0;
  const absLogit = Math.abs(safeLogit);
  const barWidth = Math.min(100, absLogit * 300); // visual scale
  const favorsTeam1 = safeLogit > 0;
  const favorsTeam2 = safeLogit < 0;
  const neutral = absLogit < 0.01;
  const testId = `factor-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;

  return (
    <div className="py-3 border-b border-[#262626] last:border-0 space-y-2" data-testid={testId}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon weight="bold" className="w-3.5 h-3.5 text-[#007AFF]" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#A3A3A3]">{label}</span>
          {tooltip && <InfoTooltip text={tooltip} />}
        </div>
        <span className="text-[9px] font-mono text-[#737373]">Weight: {(weight * 100).toFixed(0)}%</span>
      </div>
      {/* Two-sided bar — neutral shows a visible “even” marker (zero logit used to render empty) */}
      <div className="flex items-center gap-1">
        {neutral ? (
          <div className="flex-1 flex items-center justify-center gap-2 py-0.5">
            <div className="flex-1 h-2 bg-[#1A1A1A] rounded-full max-w-[45%]" />
            <span className="text-[8px] font-mono text-[#525252] uppercase tracking-wider shrink-0">Even</span>
            <div className="flex-1 h-2 bg-[#1A1A1A] rounded-full max-w-[45%]" />
          </div>
        ) : (
          <>
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
            <div className="w-px h-4 bg-[#525252] flex-shrink-0" />
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
          </>
        )}
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
      {reasonLine && (
        <div className={`text-[9px] ${favours === "team1" ? "text-[#34C759]" : favours === "team2" ? "text-[#FF3B30]" : "text-[#737373]"} flex items-center gap-1`}>
          <span>{reasonLine}</span>
          {claudeVerdict && (
            <span className={`text-[8px] font-bold uppercase tracking-wider ${claudeVerdict === "true" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              [{claudeVerdict === "true" ? "validated" : "recalculated"}]
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default function PreMatchPredictionBreakdown({ matchId, team1, team2, onDataUpdate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [xiRolesLoading, setXiRolesLoading] = useState(false);
  const [xiRolesError, setXiRolesError] = useState(null);
  const [livePlayerPerf, setLivePlayerPerf] = useState(() => readLivePlayerPerfPreference());

  const reloadPreMatchDoc = useCallback(async () => {
    if (!API || !matchId) return;
    try {
      const res = await axios.get(`${API}/predictions/${matchId}/pre-match`, { timeout: 45000 });
      if (res.data && res.data.matchId) {
        setData(res.data);
        if (onDataUpdate) onDataUpdate(res.data);
      }
    } catch (_) { /* ignore */ }
  }, [matchId, onDataUpdate]);

  const scheduleReloadAfterBackgroundPlayerJob = useCallback(() => {
    [4000, 20000, 60000, 120000].forEach((ms) => {
      window.setTimeout(() => {
        reloadPreMatchDoc();
      }, ms);
    });
  }, [reloadPreMatchDoc]);

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
      const formula = readImpactFormulaPreference();
      const url = buildPreMatchPredictUrl(matchId, { force: false, livePlayerPerf, formula });
      const res = await axios.post(url, {}, { timeout: 180000 });
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
      const formula = readImpactFormulaPreference();
      const url = buildPreMatchPredictUrl(matchId, { force: true, livePlayerPerf, formula });
      const res = await axios.post(url, {}, { timeout: 180000 });
      if (res.data && !res.data.error) {
        setData(res.data);
        if (onDataUpdate) onDataUpdate(res.data);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleFetchRolesAndRepredict = async () => {
    setXiRolesError(null);
    setXiRolesLoading(true);
    try {
      const formula = readImpactFormulaPreference();
      const url = buildFetchXiRolesAndPredictUrl(matchId, { livePlayerPerf, formula });
      const res = await axios.post(url, {}, { timeout: 180000 });
      if (res.data && !res.data.error) {
        setData(res.data);
        if (onDataUpdate) onDataUpdate(res.data);
      }
    } catch (e) {
      const d = e.response?.data?.detail;
      let msg = "Could not fetch roles and re-predict.";
      if (typeof d === "string") msg = d;
      else if (d && typeof d === "object") msg = d.message || d.error || JSON.stringify(d);
      setXiRolesError(msg);
      console.error(e);
    }
    setXiRolesLoading(false);
  };

  if (!data) {
    return (
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4" data-testid="prematch-predict-trigger">
        <PreMatchPlayerPerfToolbar
          livePlayerPerf={livePlayerPerf}
          onLivePlayerPerfChange={setLivePlayerPerf}
          predictionSummary={null}
          phaseDataReady={undefined}
          onBackgroundPlayerJobStarted={scheduleReloadAfterBackgroundPlayerJob}
        />
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3 flex items-center gap-1">Algorithm Prediction <InfoTooltip text="16-category pre-match model from SportMonks squad/form/history data plus weather-based conditions." /></p>
        <p className="text-xs text-[#A3A3A3] mb-3">16-Category Model: batting/bowling/all-round strength+depth, form, venue, home, h2h, conditions, momentum, powerplay, death, availability, top-order consistency</p>
        <button onClick={handlePredict} disabled={loading} data-testid="run-prematch-predict-btn"
          className="w-full flex items-center justify-center gap-2 bg-[#007AFF] text-white py-2.5 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-blue-600 transition-colors disabled:opacity-50">
          {loading ? <><Spinner className="w-4 h-4 animate-spin" /> Fetching Stats...</> : <><Scales weight="fill" className="w-4 h-4" /> Run Prediction</>}
        </button>
      </div>
    );
  }

  const pred = data.prediction || {};
  const factors = pred.factors || {};
  const factorOneLiners = pred.factor_one_liners || {};
  const factorClaudeValidation = pred.factor_claude_validation || {};
  const stats = data.stats || {};
  const oddsDir = data.odds_direction || {};
  const t1 = data.team1Short || team1;
  const t2 = data.team2Short || team2;
  const t1Prob = pred.team1_win_prob || 50;
  const t2Prob = pred.team2_win_prob || 50;
  const factorLogit = (key) => {
    const f = factors?.[key] || {};
    if (Number.isFinite(f.raw_logit)) return f.raw_logit;
    if (Number.isFinite(f.logit_contribution)) return f.logit_contribution;
    return 0;
  };
  const factorReason = (key) =>
    factorClaudeValidation?.[key]?.reason || factorOneLiners?.[key]?.one_liner || "";
  const factorVerdict = (key) =>
    factorClaudeValidation?.[key]?.verdict || "";
  const t1Color = t1Prob > t2Prob ? "#34C759" : "#FF3B30";
  const t2Color = t2Prob > t1Prob ? "#34C759" : "#FF3B30";

  return (
    <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4" data-testid="prematch-prediction-breakdown">
      <PreMatchPlayerPerfToolbar
        livePlayerPerf={livePlayerPerf}
        onLivePlayerPerfChange={setLivePlayerPerf}
        predictionSummary={data.player_performance_summary || null}
        phaseDataReady={data.team_strength_metrics?.phase_data_ready}
        onBackgroundPlayerJobStarted={scheduleReloadAfterBackgroundPlayerJob}
      />
      <p className="text-[9px] text-[#525252] font-mono" data-testid="prematch-impact-formula-note">
        Team strength formula:{" "}
        {(data.impact_formula || data.team_strength_metrics?.impact_formula || "br_bor_v1") === "classic_bpr_csa"
          ? "Classic BPR + CSA"
          : "BR/BoR v1"}{" "}
        — matches{" "}
        <a href="/players" className="text-[#007AFF] hover:underline">
          Players
        </a>{" "}
        preference.
      </p>
      {data.player_data_signals?.repredict_recommended && (
        <div
          className="rounded-md border border-amber-500/45 bg-amber-500/10 px-3 py-2.5 space-y-1.5"
          data-testid="player-data-stale-banner"
        >
          <p className="text-[10px] font-bold uppercase tracking-wide text-amber-400">
            Player data / coverage — action needed
          </p>
          {data.player_data_signals.message && (
            <p className="text-[10px] text-amber-100/95 leading-snug">{data.player_data_signals.message}</p>
          )}
          <p className="text-[9px] text-[#92400E]">
            Use <span className="font-semibold text-amber-200">Re-Predict</span> (or Run prediction) after sync finishes so the model uses the latest Mongo stats. Missing names need a successful Sync player stats (or live-stats run) so every XI player has a row.
          </p>
          {Array.isArray(data.player_data_signals.reasons?.missing_xi_player_perf) &&
            data.player_data_signals.reasons.missing_xi_player_perf.length > 0 && (
            <ul className="text-[9px] font-mono text-amber-200/90 list-disc pl-4 max-h-28 overflow-y-auto space-y-0.5">
              {data.player_data_signals.reasons.missing_xi_player_perf.slice(0, 16).map((m, i) => (
                <li key={`${m.side}-${m.name}-${i}`}>
                  {m.side}: {m.name}
                  {m.player_id != null ? ` · id ${m.player_id}` : ""}
                  {m.issue ? ` · ${m.issue}` : ""}
                </li>
              ))}
              {data.player_data_signals.reasons.missing_xi_player_perf.length > 16 ? (
                <li className="list-none text-[#737373]">…and more</li>
              ) : null}
            </ul>
          )}
        </div>
      )}
      {/* Main probability */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Algorithm Prediction <InfoTooltip text="16-category pre-match model. Toss is intentionally excluded from algorithm scoring and handled in Claude analysis." /></p>
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

      {/* Factor Breakdown — 16 Categories */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Factor Breakdown (16 Categories) <InfoTooltip text="All active backend factors are displayed. Toss is intentionally excluded from algorithm scoring." /></p>
        </div>
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
        </div>

        <FactorBar label="Batting Strength" weight={factors.batting_strength?.weight || 0.08} logit={factorLogit("batting_strength")} icon={UsersThree}
          tooltip="Share of combined core batting index (sums to 100%). Higher % = stronger top-6 batting pool on paper."
          team1={t1} team2={t2}
          team1Detail={`${factors.batting_strength?.team1_share_pct ?? 50}% · idx ${factors.batting_strength?.team1_batting ?? "?"}`}
          team2Detail={`${factors.batting_strength?.team2_share_pct ?? 50}% · idx ${factors.batting_strength?.team2_batting ?? "?"}`}
          reasonLine={factorReason("batting_strength")}
          favours={factorOneLiners.batting_strength?.favours}
          claudeVerdict={factorVerdict("batting_strength")}
        />
        <FactorBar label="Batting Depth" weight={factors.batting_depth?.weight || 0.08} logit={factorLogit("batting_depth")} icon={UsersThree}
          tooltip="Share of combined tail (7th–11th batting-slot) index. Higher % = deeper middle/lower order."
          team1={t1} team2={t2}
          team1Detail={`${factors.batting_depth?.team1_share_pct ?? 50}% · tail ${factors.batting_depth?.team1_tail_batting_index ?? "—"}`}
          team2Detail={`${factors.batting_depth?.team2_share_pct ?? 50}% · tail ${factors.batting_depth?.team2_tail_batting_index ?? "—"}`}
          reasonLine={factorReason("batting_depth")}
          favours={factorOneLiners.batting_depth?.favours}
          claudeVerdict={factorVerdict("batting_depth")}
        />
        <FactorBar label="Bowling Strength" weight={factors.bowling_strength?.weight || 0.08} logit={factorLogit("bowling_strength")} icon={Target}
          tooltip="Share of combined top-5 bowling pool index. Higher % = stronger front-line attack on paper."
          team1={t1} team2={t2}
          team1Detail={`${factors.bowling_strength?.team1_share_pct ?? 50}% · idx ${factors.bowling_strength?.team1_bowling_rating ?? "?"}`}
          team2Detail={`${factors.bowling_strength?.team2_share_pct ?? 50}% · idx ${factors.bowling_strength?.team2_bowling_rating ?? "?"}`}
          reasonLine={factorReason("bowling_strength")}
          favours={factorOneLiners.bowling_strength?.favours}
          claudeVerdict={factorVerdict("bowling_strength")}
        />
        <FactorBar label="Bowling Depth" weight={factors.bowling_depth?.weight ?? 0.08} logit={factorLogit("bowling_depth")} icon={Target}
          tooltip={`Share of venue-weighted top-5 attack score (sums to 100%). Pace assist: ${factors.bowling_depth?.venue_pace_assist ?? "?"}, Spin: ${factors.bowling_depth?.venue_spin_assist ?? "?"}`}
          team1={t1} team2={t2}
          team1Detail={`${factors.bowling_depth?.team1_share_pct ?? factors.bowling_depth?.team1_depth_share_pct ?? 50}% · ${factors.bowling_depth?.team1_bowler_count ?? "?"} bowlers (P${factors.bowling_depth?.team1_pace_count ?? 0} S${factors.bowling_depth?.team1_spin_count ?? 0})`}
          team2Detail={`${factors.bowling_depth?.team2_share_pct ?? factors.bowling_depth?.team2_depth_share_pct ?? 50}% · ${factors.bowling_depth?.team2_bowler_count ?? "?"} bowlers (P${factors.bowling_depth?.team2_pace_count ?? 0} S${factors.bowling_depth?.team2_spin_count ?? 0})`}
          reasonLine={factorReason("bowling_depth")}
          favours={factorOneLiners.bowling_depth?.favours}
          claudeVerdict={factorVerdict("bowling_depth")}
        />
        <FactorBar label="All-rounder Strength" weight={factors.allrounder_strength?.weight || 0.08} logit={factorLogit("allrounder_strength")} icon={Scales}
          tooltip="Share of combined all-rounder quality (top-3 mean). Higher % = better AR ceiling."
          team1={t1} team2={t2}
          team1Detail={`${factors.allrounder_strength?.team1_share_pct ?? 50}% · AR idx ${factors.allrounder_strength?.team1_allrounder_strength ?? "?"}`}
          team2Detail={`${factors.allrounder_strength?.team2_share_pct ?? 50}% · AR idx ${factors.allrounder_strength?.team2_allrounder_strength ?? "?"}`}
          reasonLine={factorReason("allrounder_strength")}
          favours={factorOneLiners.allrounder_strength?.favours}
          claudeVerdict={factorVerdict("allrounder_strength")}
        />
        <FactorBar label="All-rounder Depth" weight={factors.allrounder_depth?.weight || 0.08} logit={factorLogit("allrounder_depth")} icon={Scales}
          tooltip="Share of combined all-rounder depth (count/activity). Higher % = more AR flexibility."
          team1={t1} team2={t2}
          team1Detail={`${factors.allrounder_depth?.team1_share_pct ?? 50}% · AR units ${factors.allrounder_depth?.team1_allrounder_depth ?? "?"}`}
          team2Detail={`${factors.allrounder_depth?.team2_share_pct ?? 50}% · AR units ${factors.allrounder_depth?.team2_allrounder_depth ?? "?"}`}
          reasonLine={factorReason("allrounder_depth")}
          favours={factorOneLiners.allrounder_depth?.favours}
          claudeVerdict={factorVerdict("allrounder_depth")}
        />
        <FactorBar label="Current Form" weight={factors.current_form?.weight || 0.08} logit={factorLogit("current_form")} icon={TrendUp}
          tooltip="IPL 2026 recency-weighted form from SportMonks."
          team1={t1} team2={t2}
          team1Detail={`Score: ${factors.current_form?.team1_form_score || 50} | ${factors.current_form?.team1_wins || 0}W`}
          team2Detail={`Score: ${factors.current_form?.team2_form_score || 50} | ${factors.current_form?.team2_wins || 0}W`}
          reasonLine={factorReason("current_form")}
          favours={factorOneLiners.current_form?.favours}
          claudeVerdict={factorVerdict("current_form")}
        />
        <FactorBar label="Venue Pitch Profile" weight={factors.venue_pitch?.weight || 0.08} logit={factorLogit("venue_pitch")} icon={House}
          tooltip={`Profile: ${factors.venue_pitch?.pitch_profile || "?"}. Pace ${factors.venue_pitch?.pace_assist || "?"}, Spin ${factors.venue_pitch?.spin_assist || "?"}.`}
          team1={t1} team2={t2}
          team1Detail={`Type: ${factors.venue_pitch?.pitch_type || "?"}`}
          team2Detail={`Avg 1st inns: ${factors.venue_pitch?.avg_first_innings || "?"}`}
          reasonLine={factorReason("venue_pitch")}
          favours={factorOneLiners.venue_pitch?.favours}
          claudeVerdict={factorVerdict("venue_pitch")}
        />
        <FactorBar label="Home Ground Advantage" weight={factors.home_ground_advantage?.weight || 0.04} logit={factorLogit("home_ground_advantage")} icon={House}
          tooltip="Venue familiarity/home mapping."
          team1={t1} team2={t2}
          team1Detail={factors.home_ground_advantage?.team1_home ? "HOME" : "Away/Neutral"}
          team2Detail={factors.home_ground_advantage?.team2_home ? "HOME" : "Away/Neutral"}
          reasonLine={factorReason("home_ground_advantage")}
          favours={factorOneLiners.home_ground_advantage?.favours}
          claudeVerdict={factorVerdict("home_ground_advantage")}
        />
        <FactorBar label="Head-to-Head" weight={factors.h2h?.weight || 0.065} logit={factorLogit("h2h")} icon={Scales}
          tooltip={`H2H source: ${factors.h2h?.source || "season_2026"}.`}
          team1={t1} team2={t2}
          team1Detail={`${factors.h2h?.team1_wins || 0} wins`}
          team2Detail={`${factors.h2h?.team2_wins || 0} wins (${factors.h2h?.total || 0} total)`}
          reasonLine={factorReason("h2h")}
          favours={factorOneLiners.h2h?.favours}
          claudeVerdict={factorVerdict("h2h")}
        />

        <div className="text-[9px] text-[#737373] -mt-1 mb-1 px-1">
          Toss is handled in Claude contextual analysis, not in algorithm score.
        </div>

        <FactorBar label="Conditions (Weather/Dew)" weight={factors.conditions?.weight || 0.05} logit={factorLogit("conditions")} icon={CloudSun}
          tooltip={factors.conditions?.conditions_edge_text || "Real-time weather conditions."}
          team1={t1} team2={t2}
          team1Detail={`${factors.conditions?.condition || "?"} | ${factors.conditions?.temperature || "?"}C`}
          team2Detail={`Humidity: ${factors.conditions?.humidity || "?"}% | Dew: ${factors.conditions?.dew_factor || "none"}`}
          reasonLine={factorReason("conditions")}
          favours={factorOneLiners.conditions?.favours}
          claudeVerdict={factorVerdict("conditions")}
        />
        <FactorBar label="Momentum (Last 4)" weight={factors.momentum?.weight || 0.035} logit={factorLogit("momentum")} icon={Lightning}
          tooltip="Last 4 completed-match results: W = win, L = loss, left slot = most recent. — = fewer than 4 games in sample."
          team1={t1} team2={t2}
          team1Detail={formatMomentumLastFour(factors.momentum, "team1")}
          team2Detail={formatMomentumLastFour(factors.momentum, "team2")}
          reasonLine={factorReason("momentum")}
          favours={factorOneLiners.momentum?.favours}
          claudeVerdict={factorVerdict("momentum")}
        />
        {factors.conditions?.conditions_edge_text && factors.conditions?.conditions_edge_text !== "Conditions relatively neutral for both teams" && (
          <div className="flex items-center text-[9px] -mt-1.5 mb-1.5 px-1">
            <span className={`${factors.conditions?.favours_team === "team1" ? "text-[#34C759]" : factors.conditions?.favours_team === "team2" ? "text-[#FF3B30]" : "text-[#525252]"}`}>
              {factors.conditions.conditions_edge_text}
            </span>
          </div>
        )}

        <FactorBar label="Powerplay Performance" weight={factors.powerplay_performance?.weight || 0.055} logit={factorLogit("powerplay_performance")} icon={TrendUp}
          tooltip={`First-6-over strength. Source: ${phaseFactorSourceLabel(factors.powerplay_performance?.source)}.`}
          team1={t1} team2={t2}
          team1Detail={
            factors.powerplay_performance?.source === "sportmonks_ball_phases"
              ? `Idx ${factors.powerplay_performance?.team1_powerplay_index ?? "—"} · bat balls ${factors.powerplay_performance?.team1_pp_bat_balls ?? "—"} · bowl ${factors.powerplay_performance?.team1_pp_bowl_balls ?? "—"}`
              : `Raw: ${factors.powerplay_performance?.raw_logit ?? "0.000"}`
          }
          team2Detail={
            factors.powerplay_performance?.source === "sportmonks_ball_phases"
              ? `Idx ${factors.powerplay_performance?.team2_powerplay_index ?? "—"} · bat balls ${factors.powerplay_performance?.team2_pp_bat_balls ?? "—"} · bowl ${factors.powerplay_performance?.team2_pp_bowl_balls ?? "—"}`
              : "Compared with opposition"
          }
          reasonLine={factorReason("powerplay_performance")}
          favours={factorOneLiners.powerplay_performance?.favours}
          claudeVerdict={factorVerdict("powerplay_performance")}
        />
        <FactorBar label="Death Overs Performance" weight={factors.death_overs_performance?.weight || 0.055} logit={factorLogit("death_overs_performance")} icon={Target}
          tooltip={`Overs 16–20 strength. Source: ${phaseFactorSourceLabel(factors.death_overs_performance?.source)}.`}
          team1={t1} team2={t2}
          team1Detail={
            factors.death_overs_performance?.source === "sportmonks_ball_phases"
              ? `Idx ${factors.death_overs_performance?.team1_death_index ?? "—"} · death bat balls ${factors.death_overs_performance?.team1_death_bat_balls ?? "—"}`
              : `Raw: ${factors.death_overs_performance?.raw_logit ?? "0.000"}`
          }
          team2Detail={
            factors.death_overs_performance?.source === "sportmonks_ball_phases"
              ? `Idx ${factors.death_overs_performance?.team2_death_index ?? "—"} · death bat balls ${factors.death_overs_performance?.team2_death_bat_balls ?? "—"}`
              : "Compared with opposition"
          }
          reasonLine={factorReason("death_overs_performance")}
          favours={factorOneLiners.death_overs_performance?.favours}
          claudeVerdict={factorVerdict("death_overs_performance")}
        />
        <FactorBar label="Key Players Availability" weight={factors.key_players_availability?.weight || 0.03} logit={factorLogit("key_players_availability")} icon={UsersThree}
          tooltip="Availability/injury flags from XI data."
          team1={t1} team2={t2}
          team1Detail={`Raw: ${factors.key_players_availability?.raw_logit ?? "0.000"}`}
          team2Detail="Compared with opposition"
          reasonLine={factorReason("key_players_availability")}
          favours={factorOneLiners.key_players_availability?.favours}
          claudeVerdict={factorVerdict("key_players_availability")}
        />
        <FactorBar label="Top Order Consistency" weight={factors.top_order_consistency?.weight || 0.03} logit={factorLogit("top_order_consistency")} icon={TrendUp}
          tooltip="Top-order form consistency from performer scores."
          team1={t1} team2={t2}
          team1Detail={`Raw: ${factors.top_order_consistency?.raw_logit ?? "0.000"}`}
          team2Detail="Compared with opposition"
          reasonLine={factorReason("top_order_consistency")}
          favours={factorOneLiners.top_order_consistency?.favours}
          claudeVerdict={factorVerdict("top_order_consistency")}
        />
      </div>

      {/* Expected Playing XI — SportMonks last match + impact points */}
      {data.playing_xi?.team1_xi?.length > 0 && (
        <div className="border border-[#262626] rounded-md p-3 space-y-2" data-testid="prematch-playing-xi">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[10px] text-[#737373] uppercase tracking-[0.15em] font-semibold flex items-center gap-1">
              <UsersThree weight="fill" className="w-3.5 h-3.5 text-[#7C3AED]" />
              Expected Playing XI
              <InfoTooltip text={data.playing_xi.xi_lineup_note || "XI from SportMonks when available; roles may be inferred by Claude (tagged) and feed all-rounder depth/strength. impact_points = Lucky 11 card rating. A manual IPL Impact pick (from bench) is included in the model when set in Expected XI + Performance."} />
            </p>
            <div className="flex flex-wrap items-center gap-2 justify-end">
              <button
                type="button"
                onClick={handleFetchRolesAndRepredict}
                disabled={xiRolesLoading || loading}
                data-testid="fetch-xi-roles-and-predict-btn"
                title="Calls Claude for each XI player’s role, then re-runs the full pre-match model."
                className="text-[10px] font-bold uppercase tracking-wide px-2.5 py-1 rounded-md bg-[#7C3AED]/25 text-[#C4B5FD] border border-[#7C3AED]/40 hover:bg-[#7C3AED]/35 transition-colors disabled:opacity-50 shrink-0"
              >
                {xiRolesLoading ? (
                  <span className="flex items-center gap-1.5">
                    <Spinner className="w-3 h-3 animate-spin" />
                    Roles + predict…
                  </span>
                ) : (
                  "Fetch respective roles"
                )}
              </button>
              <span className="text-[9px] font-mono text-[#525252]">
                {data.playing_xi.source === "last_match" ? "Last IPL match" : data.playing_xi.source === "squad_estimate" ? "Squad estimate" : data.playing_xi.source || "—"}
                {data.playing_xi.stats_lookback_matches ? ` · last ${data.playing_xi.stats_lookback_matches} stats` : ""}
              </span>
            </div>
          </div>
          {xiRolesError && (
            <p className="text-[10px] text-[#FF3B30]" data-testid="fetch-xi-roles-error">{xiRolesError}</p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF] mb-1">{t1}</p>
              <ul className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {(data.playing_xi.team1_xi || []).map((p, i) => (
                  <li key={i} className="flex items-start justify-between text-[10px] gap-2 border-b border-[#1E1E1E] pb-1 last:border-0">
                    <div className="min-w-0 flex-1">
                      <div className="text-[#E5E5E5] truncate">{p.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: xiRoleColor(p.role) }}>
                          {p.role || "—"}
                        </span>
                        {p.role_source === "claude" && (
                          <span className="text-[7px] px-1 py-0 rounded bg-[#7C3AED]/25 text-[#C4B5FD] font-mono uppercase">Claude</span>
                        )}
                      </div>
                    </div>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0 self-center">
                      {p.impact_points != null ? <span className="text-[#FFCC00] font-bold">{p.impact_points}</span> : "—"}
                      {p.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(p.recent_form_impact)}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              {data.playing_xi.team1_manual_impact_player?.name && (
                <div className="mt-2 pt-2 border-t border-[#EAB308]/25" data-testid="prematch-team1-manual-impact">
                  <p className="text-[8px] text-[#EAB308] font-bold uppercase tracking-wider mb-1">Impact player (manual)</p>
                  <div className="flex items-start justify-between text-[10px] gap-2 rounded border border-dashed border-[#EAB308]/35 bg-[#EAB308]/5 px-2 py-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="text-[#E5E5E5] truncate">{data.playing_xi.team1_manual_impact_player.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: xiRoleColor(data.playing_xi.team1_manual_impact_player.role) }}>
                          {data.playing_xi.team1_manual_impact_player.role || "—"}
                        </span>
                        {data.playing_xi.team1_manual_impact_player.role_source === "roster" && (
                          <span className="text-[7px] px-1 py-0 rounded bg-[#525252]/40 text-[#A3A3A3] font-mono uppercase">Bench</span>
                        )}
                      </div>
                    </div>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0 self-center">
                      {data.playing_xi.team1_manual_impact_player.impact_points != null ? (
                        <span className="text-[#FFCC00] font-bold">{data.playing_xi.team1_manual_impact_player.impact_points}</span>
                      ) : (
                        "—"
                      )}
                      {data.playing_xi.team1_manual_impact_player.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(data.playing_xi.team1_manual_impact_player.recent_form_impact)}</span>
                      )}
                    </span>
                  </div>
                </div>
              )}
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30] mb-1">{t2}</p>
              <ul className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {(data.playing_xi.team2_xi || []).map((p, i) => (
                  <li key={i} className="flex items-start justify-between text-[10px] gap-2 border-b border-[#1E1E1E] pb-1 last:border-0">
                    <div className="min-w-0 flex-1">
                      <div className="text-[#E5E5E5] truncate">{p.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: xiRoleColor(p.role) }}>
                          {p.role || "—"}
                        </span>
                        {p.role_source === "claude" && (
                          <span className="text-[7px] px-1 py-0 rounded bg-[#7C3AED]/25 text-[#C4B5FD] font-mono uppercase">Claude</span>
                        )}
                      </div>
                    </div>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0 self-center">
                      {p.impact_points != null ? <span className="text-[#FFCC00] font-bold">{p.impact_points}</span> : "—"}
                      {p.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(p.recent_form_impact)}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              {data.playing_xi.team2_manual_impact_player?.name && (
                <div className="mt-2 pt-2 border-t border-[#EAB308]/25" data-testid="prematch-team2-manual-impact">
                  <p className="text-[8px] text-[#EAB308] font-bold uppercase tracking-wider mb-1">Impact player (manual)</p>
                  <div className="flex items-start justify-between text-[10px] gap-2 rounded border border-dashed border-[#EAB308]/35 bg-[#EAB308]/5 px-2 py-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="text-[#E5E5E5] truncate">{data.playing_xi.team2_manual_impact_player.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: xiRoleColor(data.playing_xi.team2_manual_impact_player.role) }}>
                          {data.playing_xi.team2_manual_impact_player.role || "—"}
                        </span>
                        {data.playing_xi.team2_manual_impact_player.role_source === "roster" && (
                          <span className="text-[7px] px-1 py-0 rounded bg-[#525252]/40 text-[#A3A3A3] font-mono uppercase">Bench</span>
                        )}
                      </div>
                    </div>
                    <span className="text-[#A1A1AA] font-mono flex-shrink-0 self-center">
                      {data.playing_xi.team2_manual_impact_player.impact_points != null ? (
                        <span className="text-[#FFCC00] font-bold">{data.playing_xi.team2_manual_impact_player.impact_points}</span>
                      ) : (
                        "—"
                      )}
                      {data.playing_xi.team2_manual_impact_player.recent_form_impact != null && (
                        <span className="text-[#525252] ml-1">frm {Math.round(data.playing_xi.team2_manual_impact_player.recent_form_impact)}</span>
                      )}
                    </span>
                  </div>
                </div>
              )}
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
