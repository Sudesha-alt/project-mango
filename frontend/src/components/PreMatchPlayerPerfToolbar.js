import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Database, Lightning, Spinner, UserCircle } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import { API_BASE } from "@/lib/apiBase";
import { formatPlayerPerformanceSource, buildSyncCareerProfilesUrl } from "@/lib/preMatchApi";

const API = API_BASE;
const LIVE_PREF_KEY = "prematch_live_player_perf";

export function readLivePlayerPerfPreference() {
  try {
    return sessionStorage.getItem(LIVE_PREF_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeLivePlayerPerfPreference(value) {
  try {
    sessionStorage.setItem(LIVE_PREF_KEY, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

/**
 * On-demand player performance: sync to Mongo, optional live SportMonks for predict runs,
 * and summary from the last prediction payload.
 */
export default function PreMatchPlayerPerfToolbar({
  livePlayerPerf,
  onLivePlayerPerfChange,
  predictionSummary,
  phaseDataReady,
  onBackgroundPlayerJobStarted,
}) {
  const [status, setStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncNote, setSyncNote] = useState(null);
  const [careerBusy, setCareerBusy] = useState(false);
  const [careerNote, setCareerNote] = useState(null);

  const refreshStatus = useCallback(async () => {
    if (!API) return;
    setStatusLoading(true);
    try {
      const res = await axios.get(`${API}/player-performance/status`, { timeout: 20000 });
      setStatus(res.data);
    } catch {
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  const handleSync = async () => {
    if (!API) return;
    setSyncBusy(true);
    setSyncNote(null);
    try {
      const res = await axios.post(`${API}/sync-player-stats`, {}, { timeout: 30000 });
      setSyncNote(res.data?.message || res.data?.status || "Started.");
      await refreshStatus();
      if (res.data?.status === "sync_started" || res.data?.message) {
        onBackgroundPlayerJobStarted?.();
      }
    } catch (e) {
      const d = e?.response?.data?.detail;
      setSyncNote(
        typeof d === "string" ? d : e?.message || "Sync request failed."
      );
    } finally {
      setSyncBusy(false);
    }
  };

  const handleCareerEnrich = async () => {
    const url = buildSyncCareerProfilesUrl(500);
    if (!url) return;
    setCareerBusy(true);
    setCareerNote(null);
    try {
      const res = await axios.post(url, {}, { timeout: 30000 });
      setCareerNote(
        res.data?.message ||
          res.data?.status ||
          "Career enrichment started (runs in background; re-sync or re-predict after a few minutes)."
      );
      if (res.data?.status === "enrichment_started") {
        onBackgroundPlayerJobStarted?.();
      }
    } catch (e) {
      const d = e?.response?.data?.detail;
      setCareerNote(
        typeof d === "string" ? d : e?.message || "Career enrichment request failed."
      );
    } finally {
      setCareerBusy(false);
    }
  };

  if (!API) return null;

  const n = status?.mongodb_player_docs;
  const countLabel =
    n == null || n < 0 ? "—" : `${n} player row${n === 1 ? "" : "s"}`;

  return (
    <div
      className="rounded-md border border-[#262626] bg-[#0A0A0A] p-3 space-y-2"
      data-testid="prematch-player-perf-toolbar"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.15em] font-semibold flex items-center gap-1">
            <Database weight="fill" className="w-3.5 h-3.5 text-[#22D3EE]" />
            Player performance (on demand)
            <InfoTooltip text="Sync: IPL aggregates + last-5 cards + ball-by-ball phases into Mongo. Enrich careers: SportMonks /players/{id} splits (api_profile), background job — re-predict after it finishes. Live checkbox: last-5 from API for this run only." />
          </p>
          <p className="text-[10px] text-[#525252] mt-1">
            MongoDB:{" "}
            {statusLoading ? (
              <span className="inline-flex items-center gap-1">
                <Spinner className="w-3 h-3 animate-spin" /> loading…
              </span>
            ) : (
              <span className="font-mono text-[#A3A3A3]">{countLabel}</span>
            )}
            {status?.recommend_sync && !statusLoading && (
              <span className="text-[#FBBF24]"> · sync recommended</span>
            )}
            {phaseDataReady === true && (
              <span className="text-[#34C759]"> · PP/death factors use ball-by-ball phases</span>
            )}
            {phaseDataReady === false && predictionSummary?.has_data && (
              <span className="text-[#737373]"> · PP/death: run sync + predict to build phase sample</span>
            )}
          </p>
          {!statusLoading && status?.last_player_db_update_at && (
            <p className="text-[9px] text-[#525252] font-mono mt-0.5">
              DB stats last built: {String(status.last_player_db_update_at).slice(0, 19).replace("T", " ")} UTC
              {status.last_db_update_source ? ` · ${status.last_db_update_source}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 justify-end shrink-0">
          <button
            type="button"
            onClick={handleSync}
            disabled={syncBusy}
            data-testid="sync-player-stats-btn"
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-[#22D3EE]/40 bg-[#22D3EE]/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#A5F3FC] hover:bg-[#22D3EE]/20 transition-colors disabled:opacity-50"
          >
            {syncBusy ? (
              <>
                <Spinner className="w-3 h-3 animate-spin" /> Starting…
              </>
            ) : (
              <>
                <Database weight="bold" className="w-3.5 h-3.5" /> Sync player stats
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleCareerEnrich}
            disabled={careerBusy || syncBusy}
            data-testid="sync-career-profiles-btn"
            title="Fetches SportMonks /players career-style splits into Mongo (rate-limited). Run before predict if you want api_profile on each row."
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-[#A78BFA]/40 bg-[#7C3AED]/15 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#DDD6FE] hover:bg-[#7C3AED]/25 transition-colors disabled:opacity-50"
          >
            {careerBusy ? (
              <>
                <Spinner className="w-3 h-3 animate-spin" /> Starting…
              </>
            ) : (
              <>
                <UserCircle weight="bold" className="w-3.5 h-3.5" /> Enrich career profiles
              </>
            )}
          </button>
        </div>
      </div>

      <label className="flex items-start gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={livePlayerPerf}
          onChange={(e) => {
            const v = e.target.checked;
            writeLivePlayerPerfPreference(v);
            onLivePlayerPerfChange(v);
          }}
          data-testid="live-player-perf-checkbox"
          className="mt-0.5 rounded border-[#525252] bg-[#141414] text-[#007AFF] focus:ring-[#007AFF]"
        />
        <span className="text-[10px] text-[#A3A3A3] leading-snug">
          <span className="inline-flex items-center gap-1 font-semibold text-[#E5E5E5]">
            <Lightning weight="fill" className="w-3 h-3 text-[#FBBF24]" />
            Live SportMonks stats for predictions
          </span>
          <span className="block text-[#525252] mt-0.5">
            When checked, Run / Re-Predict / Fetch roles uses last-5 completed matches per team from the
            API instead of Mongo.
          </span>
        </span>
      </label>

      {(syncNote || careerNote) && (
        <div className="text-[10px] text-[#737373] font-mono space-y-1">
          {syncNote && (
            <p data-testid="sync-player-stats-note">{syncNote}</p>
          )}
          {careerNote && (
            <p data-testid="sync-career-profiles-note">{careerNote}</p>
          )}
        </div>
      )}

      {predictionSummary && (
        <div
          className="text-[10px] text-[#525252] border-t border-[#1E1E1E] pt-2 font-mono space-y-0.5"
          data-testid="player-performance-summary"
        >
          <div>
            Last run source:{" "}
            <span className="text-[#A3A3A3]">
              {formatPlayerPerformanceSource(predictionSummary.source)}
            </span>
          </div>
          <div>
            XI coverage: {predictionSummary.team1_players ?? 0} /{" "}
            {predictionSummary.team2_players ?? 0} players ·{" "}
            {predictionSummary.has_data ? (
              <span className="text-[#34C759]">has_data</span>
            ) : (
              <span className="text-[#FBBF24]">no perf blob</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
