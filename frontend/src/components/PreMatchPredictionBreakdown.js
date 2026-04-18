import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Spinner, Scales, TrendUp, UsersThree, House, TrendDown, Minus, ArrowsClockwise, Target } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";
import PreMatchPlayerPerfToolbar, { readLivePlayerPerfPreference } from "./PreMatchPlayerPerfToolbar";
import { buildPreMatchPredictUrl, buildFetchXiRolesAndPredictUrl } from "@/lib/preMatchApi";
import { readImpactFormulaPreference } from "@/lib/impactFormulaPref";

const API = API_BASE;

/** Must match backend ``FIVE_FACTOR_PREDICTION_KEYS`` — UI bars need every block. */
const FIVE_FACTOR_KEYS = [
  "batting_quality",
  "bowling_quality",
  "allrounder_balance",
  "venue_baseline",
  "h2h_squad_adjusted",
];

/** Coerce API/Mongo values that may arrive as strings into finite numbers. */
function toFiniteNumber(value, fallback = null) {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
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

function FactorBar({ label, weight, logit, icon: Icon, tooltip, team1, team2, team1Detail, team2Detail, reasonLine, favours, claudeVerdict }) {
  // logit > 0 favors team1, logit < 0 favors team2
  const safeLogit = toFiniteNumber(logit, 0);
  const absLogit = Math.abs(safeLogit);
  const barWidth = Math.min(100, absLogit * 300); // visual scale
  const favorsTeam1 = safeLogit > 0;
  const favorsTeam2 = safeLogit < 0;
  const neutral = absLogit < 0.01;
  const testId = `factor-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;

  return (
    <div className="py-3 border-b border-[#262626] last:border-0 space-y-2" data-testid={testId}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <Icon weight="bold" className="w-3.5 h-3.5 text-[#007AFF] shrink-0" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#A3A3A3] truncate">{label}</span>
          {tooltip && <InfoTooltip text={tooltip} />}
        </div>
        <div className="flex flex-col items-end gap-0.5 shrink-0">
          <span className="text-[9px] font-mono text-[#737373]">Weight: {(toFiniteNumber(weight, 0) * 100).toFixed(0)}%</span>
          {favours === "team1" && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#34C759]">Favours {team1}</span>
          )}
          {favours === "team2" && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#FF3B30]">Favours {team2}</span>
          )}
          {(favours === "neutral" || !favours) && neutral && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#525252]">Even</span>
          )}
          {(favours === "neutral" || !favours) && !neutral && favorsTeam1 && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#34C759]">Edge {team1}</span>
          )}
          {(favours === "neutral" || !favours) && !neutral && favorsTeam2 && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#FF3B30]">Edge {team2}</span>
          )}
        </div>
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
        await reloadPreMatchDoc();
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
        await reloadPreMatchDoc();
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
        await reloadPreMatchDoc();
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

  const predMissing = !data || data.prediction == null || typeof data.prediction !== "object";

  if (predMissing) {
    return (
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4" data-testid="prematch-predict-trigger">
        <PreMatchPlayerPerfToolbar
          livePlayerPerf={livePlayerPerf}
          onLivePlayerPerfChange={setLivePlayerPerf}
          predictionSummary={null}
          phaseDataReady={undefined}
          onBackgroundPlayerJobStarted={scheduleReloadAfterBackgroundPlayerJob}
        />
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3 flex items-center gap-1">Algorithm Prediction <InfoTooltip text="5-parameter pre-match model: BPR/CSA batting & bowling, all-rounder balance, venue + weather (bowler tilt), squad-adjusted H2H." /></p>
        <p className="text-xs text-[#A3A3A3] mb-3">5-Parameter Model (30% / 30% / 10% / 20% / 10%): batting quality, bowling quality, all-rounder balance, venue baseline, H2H</p>
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
  const t1Prob = toFiniteNumber(pred.team1_win_prob, 50);
  const t2Prob = toFiniteNumber(pred.team2_win_prob, 50);
  const hasFiveFactorModel = Boolean(
    pred.factors && FIVE_FACTOR_KEYS.every((k) => pred.factors[k] != null)
  );
  const factorLogit = (key) => {
    const f = factors?.[key] || {};
    const raw = toFiniteNumber(f.raw_logit, null);
    if (raw != null) return raw;
    const w = toFiniteNumber(f.weight, null);
    const lc = toFiniteNumber(f.logit_contribution, null);
    if (w != null && lc != null && Math.abs(w) > 1e-9) return lc / w;
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
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Algorithm Prediction <InfoTooltip text="5-parameter BPR/CSA model. Toss is excluded from algorithm scoring and handled in Claude analysis." /></p>
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
          Model confidence: {pred.confidence || "—"} | Logit:{" "}
          {toFiniteNumber(pred.combined_logit, null) != null
            ? toFiniteNumber(pred.combined_logit, 0).toFixed(4)
            : pred.combined_logit ?? "—"}
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

      {!hasFiveFactorModel && (
        <div
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 space-y-1"
          data-testid="prematch-stale-model-banner"
        >
          <p className="text-[10px] font-bold uppercase tracking-wide text-amber-400">5-factor breakdown not in this cache</p>
          <p className="text-[10px] text-amber-100/90 leading-snug">
            Stored prediction is missing the current five-factor block (batting_quality, bowling_quality, …). Use{" "}
            <span className="font-semibold">Re-Predict</span> so BPR/CSA indices, logits, and bars populate.
          </p>
        </div>
      )}

      {hasFiveFactorModel && (
        <>
          <div className="rounded-md border border-[#262626] bg-[#0A0A0A] px-3 py-2.5 space-y-2" data-testid="prematch-formula-panel">
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#A3A3A3]">How BPR/CSA becomes the score</p>
            <ul className="text-[9px] text-[#A3A3A3] leading-relaxed list-disc pl-4 space-y-1">
              <li>
                <span className="font-semibold text-[#E5E5E5]">Per player</span> — BatIP and BowlIP blend baseline BPR with
                current-season CSA (formula matches Players directory / impact preference).
              </li>
              <li>
                <span className="font-semibold text-[#E5E5E5]">Team batting strength</span> — weighted mean of the top{" "}
                {data.team_strength_metrics?.config?.N ?? 5} batting-order slots (weights 0.25→0.15 on BatIP).
              </li>
              <li>
                <span className="font-semibold text-[#E5E5E5]">Team bowling strength</span> — weighted mean of the top{" "}
                {data.team_strength_metrics?.config?.M ?? 4} bowling-order slots on BowlIP.
              </li>
              <li>
                <span className="font-semibold text-[#E5E5E5]">Factor logits (team1 minus team2)</span> — batting{" "}
                <span className="font-mono">3.2 * (bat1 - bat2) / 100</span>, bowling{" "}
                <span className="font-mono">3.0 * (bowl1 - bowl2) / 100</span>; then venue baseline and H2H (damped). Weighted
                sum, confidence shrink, then <span className="font-mono">sigmoid(combined logit)</span> for win %.
              </li>
              <li>
                <span className="font-semibold text-[#E5E5E5]">Fielding</span> — not a separate FieldIP in this BPR/CSA pipeline
                (only bat/bowl). It does not enter the five weighted factors until we add a fielding signal to player rows.
              </li>
            </ul>
            {data.team_strength_metrics?.team1 && data.team_strength_metrics?.team2 && (
              <div className="text-[9px] font-mono text-[#737373] border-t border-[#262626] pt-2 space-y-0.5">
                <div className="flex justify-between gap-2">
                  <span className="text-[#007AFF]">{t1}</span>
                  <span>
                    bat {toFiniteNumber(data.team_strength_metrics.team1.batting_strength, null)?.toFixed(2) ?? "—"} · bowl{" "}
                    {toFiniteNumber(data.team_strength_metrics.team1.bowling_strength, null)?.toFixed(2) ?? "—"} · AR{" "}
                    {toFiniteNumber(data.team_strength_metrics.team1.allrounder_strength, null)?.toFixed(2) ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-[#FF3B30]">{t2}</span>
                  <span>
                    bat {toFiniteNumber(data.team_strength_metrics.team2.batting_strength, null)?.toFixed(2) ?? "—"} · bowl{" "}
                    {toFiniteNumber(data.team_strength_metrics.team2.bowling_strength, null)?.toFixed(2) ?? "—"} · AR{" "}
                    {toFiniteNumber(data.team_strength_metrics.team2.allrounder_strength, null)?.toFixed(2) ?? "—"}
                  </span>
                </div>
              </div>
            )}
            {pred.favourite_one_liner && (
              <p className="text-[9px] text-[#525252] border-t border-[#262626] pt-2">
                <span className="font-semibold text-[#A3A3A3]">Overall: </span>
                {pred.favourite_one_liner}
              </p>
            )}
          </div>

          {/* Factor Breakdown — 5 parameters */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">
                Factor Breakdown (5){" "}
                <InfoTooltip text="Weights: batting 30%, bowling 30%, all-rounder balance 10%, venue baseline 20%, H2H 10%. H2H is squad-parity damped and applied as the last weighted term." />
              </p>
            </div>
            <div className="flex items-center justify-between mb-1 px-1">
              <span className="text-[9px] font-bold uppercase tracking-wider text-[#007AFF]">{t1}</span>
              <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF3B30]">{t2}</span>
            </div>

            <FactorBar
              label="Batting quality (BPR/CSA)"
              weight={factors.batting_quality?.weight || 0.3}
              logit={factorLogit("batting_quality")}
              icon={UsersThree}
              tooltip="Team batting index from BPR + CSA (BatIP) when player rows exist; else XI fallback."
              team1={t1}
              team2={t2}
              team1Detail={`${toFiniteNumber(factors.batting_quality?.team1_share_pct, 50)}% · idx ${toFiniteNumber(factors.batting_quality?.team1_batting, "?")}`}
              team2Detail={`${toFiniteNumber(factors.batting_quality?.team2_share_pct, 50)}% · idx ${toFiniteNumber(factors.batting_quality?.team2_batting, "?")}`}
              reasonLine={factorReason("batting_quality")}
              favours={factorOneLiners.batting_quality?.favours}
              claudeVerdict={factorVerdict("batting_quality")}
            />
            <FactorBar
              label="Bowling quality (BPR/CSA)"
              weight={factors.bowling_quality?.weight || 0.3}
              logit={factorLogit("bowling_quality")}
              icon={Target}
              tooltip="Team bowling index from BPR + CSA (BowlIP) when player rows exist; else XI fallback."
              team1={t1}
              team2={t2}
              team1Detail={`${toFiniteNumber(factors.bowling_quality?.team1_share_pct, 50)}% · idx ${toFiniteNumber(factors.bowling_quality?.team1_bowling, "?")}`}
              team2Detail={`${toFiniteNumber(factors.bowling_quality?.team2_share_pct, 50)}% · idx ${toFiniteNumber(factors.bowling_quality?.team2_bowling, "?")}`}
              reasonLine={factorReason("bowling_quality")}
              favours={factorOneLiners.bowling_quality?.favours}
              claudeVerdict={factorVerdict("bowling_quality")}
            />
            <FactorBar
              label="All-rounder balance"
              weight={factors.allrounder_balance?.weight || 0.1}
              logit={factorLogit("allrounder_balance")}
              icon={Scales}
              tooltip="Blended strength + depth (55% / 45%) from AR slots."
              team1={t1}
              team2={t2}
              team1Detail={`AR str ${toFiniteNumber(factors.allrounder_balance?.team1_allrounder_strength, "?")} · depth ${toFiniteNumber(factors.allrounder_balance?.team1_allrounder_depth, "?")}`}
              team2Detail={`AR str ${toFiniteNumber(factors.allrounder_balance?.team2_allrounder_strength, "?")} · depth ${toFiniteNumber(factors.allrounder_balance?.team2_allrounder_depth, "?")}`}
              reasonLine={factorReason("allrounder_balance")}
              favours={factorOneLiners.allrounder_balance?.favours}
              claudeVerdict={factorVerdict("allrounder_balance")}
            />
            <FactorBar
              label="Venue baseline"
              weight={factors.venue_baseline?.weight || 0.2}
              logit={factorLogit("venue_baseline")}
              icon={House}
              tooltip={`Pitch fit + home + weather. Weather swing/humidity/cloud shifts toward the stronger bowling index. Profile: ${factors.venue_baseline?.pitch_profile || "?"}.`}
              team1={t1}
              team2={t2}
              team1Detail={`${factors.venue_baseline?.team1_home ? "HOME" : "—"} · w-bowl ${toFiniteNumber(factors.venue_baseline?.weather_bowler_pressure_index, 0).toFixed(2)}`}
              team2Detail={`${factors.venue_baseline?.team2_home ? "HOME" : "—"} · ${factors.venue_baseline?.pitch_type || "?"}`}
              reasonLine={factorReason("venue_baseline")}
              favours={factorOneLiners.venue_baseline?.favours}
              claudeVerdict={factorVerdict("venue_baseline")}
            />
            <FactorBar
              label="H2H (squad-adjusted)"
              weight={factors.h2h_squad_adjusted?.weight || 0.1}
              logit={factorLogit("h2h_squad_adjusted")}
              icon={Scales}
              tooltip={`Last weighted term. Raw H2H logit damped when current squads are very uneven. Source: ${factors.h2h_squad_adjusted?.source || "season_2026"}.`}
              team1={t1}
              team2={t2}
              team1Detail={`${factors.h2h_squad_adjusted?.team1_wins ?? 0}W · raw logit ${factors.h2h_squad_adjusted?.h2h_raw_logit ?? "—"}`}
              team2Detail={`${factors.h2h_squad_adjusted?.team2_wins ?? 0}W · parity ${factors.h2h_squad_adjusted?.squad_parity ?? "—"}`}
              reasonLine={factorReason("h2h_squad_adjusted")}
              favours={factorOneLiners.h2h_squad_adjusted?.favours}
              claudeVerdict={factorVerdict("h2h_squad_adjusted")}
            />

            <div className="text-[9px] text-[#737373] -mt-1 mb-1 px-1">
              Toss is handled in Claude contextual analysis, not in algorithm score.
            </div>
          </div>
        </>
      )}

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
