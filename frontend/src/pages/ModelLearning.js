import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API_BASE } from "@/lib/apiBase";
import { Brain, CheckCircle, XCircle, Warning } from "@phosphor-icons/react";

const API = API_BASE;

export default function ModelLearning() {
  const [calibration, setCalibration] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [outcomes, setOutcomes] = useState([]);
  const [liveOutcomes, setLiveOutcomes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [liveBackfillBusy, setLiveBackfillBusy] = useState(false);
  const [liveBackfillLast, setLiveBackfillLast] = useState(null);
  const [completedReport, setCompletedReport] = useState({ rows: [], count: 0 });
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncLast, setSyncLast] = useState(null);
  const [syncForceLive, setSyncForceLive] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [calRes, propRes, outRes, liveRes, reportRes] = await Promise.all([
        axios.get(`${API}/learning/calibration`, { timeout: 30000 }),
        axios.get(`${API}/learning/proposals/pending`, { timeout: 30000 }),
        axios.get(`${API}/learning/outcomes`, { timeout: 30000, params: { limit: 25 } }),
        axios.get(`${API}/learning/live-outcomes`, { timeout: 30000, params: { limit: 25 } }),
        axios.get(`${API}/learning/completed-report`, { timeout: 90000, params: { limit: 500 } }),
      ]);
      setCalibration(calRes.data || {});
      setProposals(propRes.data?.proposals || []);
      setOutcomes(outRes.data?.outcomes || []);
      setLiveOutcomes(liveRes.data?.outcomes || []);
      setCompletedReport(reportRes.data || { rows: [], count: 0 });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to load learning data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async (id) => {
    setBusyId(id);
    setError(null);
    try {
      await axios.post(`${API}/learning/proposals/${id}/approve`, {}, { timeout: 60000 });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Approve failed");
    } finally {
      setBusyId(null);
    }
  };

  const dismiss = async (id) => {
    setBusyId(id);
    setError(null);
    try {
      await axios.post(`${API}/learning/proposals/${id}/dismiss`, {}, { timeout: 30000 });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Dismiss failed");
    } finally {
      setBusyId(null);
    }
  };

  const runLiveBackfill = async () => {
    setLiveBackfillBusy(true);
    setError(null);
    setLiveBackfillLast(null);
    try {
      const res = await axios.post(
        `${API}/learning/live-backfill`,
        {},
        { timeout: 120000, params: { limit: 500, force: false } }
      );
      setLiveBackfillLast(res.data || null);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Live backfill failed");
    } finally {
      setLiveBackfillBusy(false);
    }
  };

  const runSyncLearnings = async () => {
    setSyncBusy(true);
    setError(null);
    setSyncLast(null);
    try {
      const res = await axios.post(
        `${API}/learning/sync-completed`,
        {},
        { timeout: 180000, params: { limit: 500, force_live: syncForceLive } }
      );
      setSyncLast(res.data || null);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Sync learnings failed");
    } finally {
      setSyncBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-10 text-[#A3A3A3] text-sm">
        Loading model learning…
      </div>
    );
  }

  const wo = calibration?.weight_overrides || {};
  const hasOverrides = Object.keys(wo).length > 0;
  const addendum = (calibration?.claude_prompt_addendum || "").trim();

  const reportRows = completedReport?.rows || [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8" data-testid="model-learning-page">
      <div className="flex items-start gap-3">
        <Brain weight="duotone" className="w-10 h-10 text-[#007AFF] shrink-0" />
        <div>
          <h1
            className="text-2xl font-black uppercase tracking-tight text-white"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
          >
            Model learning
          </h1>
          <p className="text-sm text-[#A3A3A3] mt-2 leading-relaxed">
            After each result sync, the system compares the stored <span className="text-white font-semibold">pre-match</span>{" "}
            blend to the winner and may open a calibration proposal. Separately, the last{" "}
            <span className="text-white font-semibold">live</span> snapshot (Claude + combined) is compared to the final
            schedule; wrong live calls can propose an addendum-only tweak. Approving merges into{" "}
            <code className="text-[#737373]">backend/config/prematch_calibration.json</code> — not by rewriting Python.
          </p>
          <p className="text-xs text-amber-200/90 mt-3 flex items-start gap-2">
            <Warning weight="bold" className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Cricket is high-variance: no model can be 100% accurate. Use proposals to improve long-run calibration,
              not to chase perfect picks on single games.
            </span>
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {typeof error === "string" ? error : JSON.stringify(error)}
        </div>
      )}

      <section className="space-y-3" data-testid="completed-matches-learning-table">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#737373]">
          Completed matches — predictions vs results
        </h2>
        <p className="text-[11px] text-[#525252] leading-relaxed">
          Pre-match <span className="text-[#A3A3A3]">team1_win_prob</span> and last stored live{" "}
          <span className="text-[#A3A3A3]">combinedPrediction.team1_pct</span> vs schedule winner and score fields.{" "}
          <span className="text-[#737373]">Incorporate</span> applies the same merge as “Incorporate fixes” below (
          <code className="text-[#525252]">prematch_calibration.json</code>). Combined % is not scored when the live
          snapshot SportMonks status is already finished.
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button
            type="button"
            onClick={runSyncLearnings}
            disabled={syncBusy}
            className="text-[11px] font-semibold uppercase tracking-wide px-3 py-1.5 rounded-md bg-[#007AFF]/90 text-white border border-[#0066CC] hover:opacity-90 disabled:opacity-50"
          >
            {syncBusy ? "Syncing learnings…" : "Sync learnings (all completed)"}
          </button>
          <label className="flex items-center gap-2 text-[11px] text-[#737373] cursor-pointer select-none">
            <input
              type="checkbox"
              className="rounded border-[#404040] bg-[#1A1A1A]"
              checked={syncForceLive}
              onChange={(e) => setSyncForceLive(e.target.checked)}
            />
            Force reprocess live rows (<code className="text-[#525252]">force_live</code>)
          </label>
        </div>
        {syncLast && (
          <p className="text-[11px] font-mono text-[#737373]">
            processed {syncLast.processed} · new pre outcomes +{syncLast.pre_match_outcomes_new} · live proposals +
            {syncLast.live_proposals_created} · live skips {syncLast.live_already_recorded_skips} · no snapshot{" "}
            {syncLast.live_rows_without_snapshot_hint}
          </p>
        )}
        {reportRows.length === 0 ? (
          <p className="text-sm text-[#737373]">No completed fixtures in the schedule yet.</p>
        ) : (
          <div className="rounded-xl border border-[#262626] bg-[#141414] overflow-x-auto">
            <table className="w-full text-left text-[10px] sm:text-xs text-[#A3A3A3] border-collapse min-w-[920px]">
              <thead>
                <tr className="border-b border-[#262626] text-[#525252] uppercase tracking-wider">
                  <th className="py-2 pr-2 font-bold">#</th>
                  <th className="py-2 pr-2 font-bold">Fixture</th>
                  <th className="py-2 pr-2 font-bold">Scores</th>
                  <th className="py-2 pr-2 font-bold">Result</th>
                  <th className="py-2 pr-2 font-bold">Winner</th>
                  <th className="py-2 pr-2 font-bold">Pre t1%</th>
                  <th className="py-2 pr-2 font-bold">Comb t1%</th>
                  <th className="py-2 pr-2 font-bold">Pre</th>
                  <th className="py-2 pr-2 font-bold">Comb</th>
                  <th className="py-2 pr-2 font-bold min-w-[200px]">Learning</th>
                  <th className="py-2 pr-2 font-bold">Incorporate</th>
                </tr>
              </thead>
              <tbody>
                {reportRows.map((r) => (
                  <tr key={r.matchId} className="border-b border-[#1F1F1F] align-top">
                    <td className="py-2 pr-2 font-mono text-white whitespace-nowrap">
                      {r.match_number != null ? r.match_number : "—"}
                    </td>
                    <td className="py-2 pr-2 text-white max-w-[140px]">
                      <div className="leading-tight">
                        <div className="truncate" title={r.team1}>
                          {r.team1}
                        </div>
                        <div className="truncate text-[#737373]" title={r.team2}>
                          v {r.team2}
                        </div>
                      </div>
                    </td>
                    <td className="py-2 pr-2 font-mono text-[10px] leading-tight max-w-[120px]">
                      {r.team1_score || r.team2_score ? (
                        <>
                          <div className="truncate" title={r.team1_score}>
                            {r.team1_score || "—"}
                          </div>
                          <div className="truncate" title={r.team2_score}>
                            {r.team2_score || "—"}
                          </div>
                        </>
                      ) : r.schedule_score ? (
                        <span className="text-[#737373]" title={r.schedule_score}>
                          {r.schedule_score.length > 32 ? `${r.schedule_score.slice(0, 32)}…` : r.schedule_score}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-2 pr-2 max-w-[100px]">
                      <span className="line-clamp-2" title={r.result_note || ""}>
                        {r.result_note || "—"}
                      </span>
                    </td>
                    <td className="py-2 pr-2 max-w-[100px]">
                      <div className="text-white truncate" title={r.winner_name}>
                        {r.winner_name || r.winner_side || "—"}
                      </div>
                      {r.winner_side && (
                        <div className="text-[#525252] font-mono text-[10px]">{r.winner_side}</div>
                      )}
                    </td>
                    <td className="py-2 pr-2 font-mono whitespace-nowrap">
                      {r.pre_match_team1_pct != null ? r.pre_match_team1_pct : "—"}
                    </td>
                    <td className="py-2 pr-2 font-mono whitespace-nowrap">
                      {r.live_combined_team1_pct != null ? r.live_combined_team1_pct : "—"}
                    </td>
                    <td className="py-2 pr-2">
                      {r.pre_match_team1_pct == null && "—"}
                      {r.pre_match_team1_pct != null && r.pre_match_correct === true && (
                        <span className="text-[#34C759] font-semibold">✓</span>
                      )}
                      {r.pre_match_team1_pct != null && r.pre_match_correct === false && (
                        <span className="text-[#FF3B30] font-semibold">✗</span>
                      )}
                      {r.pre_match_team1_pct != null && r.pre_match_correct == null && (
                        <span className="text-[#525252]">?</span>
                      )}
                    </td>
                    <td className="py-2 pr-2">
                      {r.live_combined_team1_pct == null && "—"}
                      {r.live_combined_team1_pct != null && r.live_combined_eval_note === "finished_snapshot" && (
                        <span className="text-[#525252]" title="Not scored vs result (finished snapshot)">
                          N/A
                        </span>
                      )}
                      {r.live_combined_team1_pct != null &&
                        r.live_combined_eval_note !== "finished_snapshot" &&
                        r.live_combined_correct === true && (
                          <span className="text-[#34C759] font-semibold">✓</span>
                        )}
                      {r.live_combined_team1_pct != null &&
                        r.live_combined_eval_note !== "finished_snapshot" &&
                        r.live_combined_correct === false && (
                          <span className="text-[#FF3B30] font-semibold">✗</span>
                        )}
                      {r.live_combined_team1_pct != null &&
                        r.live_combined_eval_note !== "finished_snapshot" &&
                        r.live_combined_correct == null && <span className="text-[#525252]">?</span>}
                    </td>
                    <td className="py-2 pr-2">
                      <p className="line-clamp-3 text-[10px] leading-snug" title={r.learning_summary}>
                        {r.learning_summary}
                      </p>
                    </td>
                    <td className="py-2 pr-2">
                      {r.pending_proposals?.length ? (
                        <div className="flex flex-col gap-1.5">
                          {r.pending_proposals.map((pp) => (
                            <button
                              key={pp.id}
                              type="button"
                              disabled={busyId === pp.id}
                              onClick={() => approve(pp.id)}
                              className="inline-flex items-center justify-center gap-1 px-2 py-1 rounded-md bg-[#34C759] text-black text-[10px] font-bold uppercase tracking-wide hover:opacity-90 disabled:opacity-40 whitespace-nowrap"
                            >
                              <CheckCircle weight="bold" className="w-3 h-3 shrink-0" />
                              {pp.source_track === "live_claude" ? "Live" : "Pre"} incorporate
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[#525252]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-[#262626] bg-[#141414] p-5 space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#737373]">Active calibration</h2>
        {hasOverrides ? (
          <pre className="text-[11px] font-mono text-[#A3A3A3] overflow-x-auto">
            {JSON.stringify(wo, null, 2)}
          </pre>
        ) : (
          <p className="text-sm text-[#737373]">No weight overrides — base 30/30/10/20/10 weights apply.</p>
        )}
        {addendum ? (
          <div className="text-xs text-[#A3A3A3] border-t border-[#262626] pt-3 mt-3 whitespace-pre-wrap">
            <span className="text-[#525252] font-bold uppercase tracking-wider block mb-1">Claude addendum</span>
            {addendum}
          </div>
        ) : (
          <p className="text-xs text-[#525252] pt-2">No Claude prompt addendum yet.</p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#737373]">Pending proposals</h2>
        {proposals.length === 0 ? (
          <p className="text-sm text-[#737373]">No pending fixes. When the algo favours the wrong side by enough margin after a result sync, a proposal appears here.</p>
        ) : (
          <ul className="space-y-4">
            {proposals.map((p) => (
              <li
                key={p.id}
                className="rounded-xl border border-[#262626] bg-[#141414] p-5 space-y-3"
                data-testid={`learning-proposal-${p.id}`}
              >
                <p className="text-sm text-white font-medium">{p.summary}</p>
                {p.source_track && (
                  <p className="text-[10px] font-mono text-[#A78BFA]">Source: {p.source_track}</p>
                )}
                <p className="text-[11px] text-[#737373] font-mono">{p.created_at}</p>
                {Array.isArray(p.learning_notes) && p.learning_notes.length > 0 && (
                  <ul className="text-xs text-[#A3A3A3] list-disc pl-4 space-y-1">
                    {p.learning_notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                )}
                <div>
                  <span className="text-[10px] font-bold uppercase text-[#525252]">Suggested weights</span>
                  <pre className="text-[11px] font-mono text-[#34C759]/90 mt-1 overflow-x-auto">
                    {JSON.stringify(p.proposed_weight_overrides || {}, null, 2)}
                  </pre>
                </div>
                {p.proposed_claude_addendum ? (
                  <div className="text-xs text-[#A3A3A3] whitespace-pre-wrap border border-[#262626] rounded-lg p-3 bg-black/30">
                    <span className="text-[#525252] font-bold uppercase tracking-wider block mb-1">Prompt addendum</span>
                    {p.proposed_claude_addendum}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    type="button"
                    disabled={busyId === p.id}
                    onClick={() => approve(p.id)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#34C759] text-black text-xs font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-40"
                  >
                    <CheckCircle weight="bold" className="w-4 h-4" />
                    Incorporate fixes
                  </button>
                  <button
                    type="button"
                    disabled={busyId === p.id}
                    onClick={() => dismiss(p.id)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[#404040] text-[#A3A3A3] text-xs font-bold uppercase tracking-wider hover:bg-[#1A1A1A] disabled:opacity-40"
                  >
                    <XCircle weight="bold" className="w-4 h-4" />
                    Dismiss
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-xs font-bold uppercase tracking-widest text-[#737373]">Live snapshot vs result</h2>
          <button
            type="button"
            onClick={runLiveBackfill}
            disabled={liveBackfillBusy}
            className="text-[11px] font-semibold uppercase tracking-wide px-3 py-1.5 rounded-md bg-[#262626] text-white border border-[#404040] hover:bg-[#333] disabled:opacity-50"
          >
            {liveBackfillBusy ? "Running backfill…" : "Run live backfill"}
          </button>
        </div>
        <p className="text-[11px] text-[#525252]">
          Last stored <span className="text-[#A3A3A3]">live_snapshots</span> (refresh-Claude + combined blend) compared to
          the final schedule. If the snapshot SportMonks status is <span className="text-[#A3A3A3]">finished</span>, headline
          Claude % is not scored vs the winner (it would almost always look “right”). Use{" "}
          <span className="text-[#A3A3A3]">pre-match</span> on that row instead, or refresh Claude only while the fixture is
          live. API: <code className="text-[#737373]">POST /api/learning/live-backfill</code>{" "}
          <span className="text-[#737373]">(?force=true to reprocess)</span>.
        </p>
        {liveBackfillLast && (
          <p className="text-[11px] font-mono text-[#737373]">
            processed {liveBackfillLast.processed} · proposals +{liveBackfillLast.proposals_created} · skips{" "}
            {liveBackfillLast.already_recorded_skips} · no snapshot {liveBackfillLast.rows_without_snapshot_hint}
          </p>
        )}
        {liveOutcomes.length === 0 ? (
          <p className="text-sm text-[#737373]">No live learning rows yet. Run live-backfill after matches complete.</p>
        ) : (
          <ul className="space-y-3 text-xs text-[#A3A3A3]">
            {liveOutcomes.map((o) => (
              <li key={o.matchId} className="border-b border-[#1F1F1F] pb-3 space-y-1">
                <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono">
                  <span className="text-white">{o.matchId?.slice(0, 8)}…</span>
                  <span>winner {o.actual_winner_side}</span>
                  {o.claude_team1_win_pct != null && <span>live Claude t1% {o.claude_team1_win_pct}</span>}
                  {o.combined_team1_win_pct != null && <span>combined t1% {o.combined_team1_win_pct}</span>}
                  {o.pre_match_team1_win_pct != null && (
                    <span>pre-match t1% {o.pre_match_team1_win_pct}</span>
                  )}
                  {o.snapshot_finished_context && (
                    <span className="text-[#737373]">Claude vs result N/A (finished snapshot)</span>
                  )}
                  {!o.snapshot_finished_context && o.claude_correct != null && (
                    <span className={o.claude_correct ? "text-[#34C759]" : "text-[#FF3B30]"}>
                      Claude {o.claude_correct ? "right" : "wrong"}
                    </span>
                  )}
                  {o.pre_match_correct != null && (
                    <span className={o.pre_match_correct ? "text-[#34C759]" : "text-[#FF3B30]"}>
                      Pre-match {o.pre_match_correct ? "right" : "wrong"}
                    </span>
                  )}
                </div>
                {o.claude_eval_note && (
                  <p className="text-[10px] text-[#525252] leading-snug">{o.claude_eval_note}</p>
                )}
                {o.claude_reason?.sentence_1_key_factor && (
                  <p className="text-[10px] leading-snug text-[#737373] border-l-2 border-[#262626] pl-2">
                    {o.claude_reason.sentence_1_key_factor}
                  </p>
                )}
                {o.schedule_digest?.score && (
                  <p className="text-[10px] font-mono text-[#525252]">Scorecard: {o.schedule_digest.score}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#737373]">Recent outcomes</h2>
        {outcomes.length === 0 ? (
          <p className="text-sm text-[#737373]">No recorded outcomes yet.</p>
        ) : (
          <ul className="space-y-2 text-xs font-mono text-[#A3A3A3]">
            {outcomes.map((o) => (
              <li key={o.matchId} className="flex flex-wrap gap-x-3 gap-y-1 border-b border-[#1F1F1F] pb-2">
                <span className="text-white">{o.matchId?.slice(0, 8)}…</span>
                <span>winner {o.actual_winner_side}</span>
                {o.algo_team1_win_prob != null && <span>algo t1% {o.algo_team1_win_prob}</span>}
                <span className={o.algo_correct ? "text-[#34C759]" : "text-[#FF3B30]"}>
                  {o.algo_correct ? "algo right" : "algo wrong"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
