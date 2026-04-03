import { motion } from "framer-motion";

export default function LiveScoreboard({ matchData, wsData }) {
  const data = wsData || matchData || {};
  const team1 = data.team1 || data.team1Short || "Team A";
  const team2 = data.team2 || data.team2Short || "Team B";
  const t1Short = data.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = data.team2Short || team2.slice(0, 3).toUpperCase();
  const score = data.score || "";
  const runs = data.runs || 0;
  const overs = data.overs || 0;
  const wickets = data.wickets || 0;
  const innings = data.innings || 1;
  const status = data.status || "";
  const probs = data.probabilities || {};

  const crr = overs > 0 ? (runs / overs).toFixed(1) : "0.0";
  const remainingOvers = 20 - overs;
  let rrr = "--";
  if (innings === 2 && score.includes("Target")) {
    try {
      const target = parseInt(score.split("Target")[1].trim().split(/\s/)[0]);
      const rem = target - runs;
      if (remainingOvers > 0) rrr = (rem / remainingOvers).toFixed(1);
    } catch {}
  }

  return (
    <div data-testid="live-scoreboard" className="bg-[#141414] border border-white/10 rounded-md p-4 lg:p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#FF3B30] animate-live-pulse" />
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-[#A1A1AA]">
            {data.isLive ? "LIVE" : status || "MATCH"}
          </span>
        </div>
        <span className="text-xs text-[#71717A] font-mono">{data.venue || ""}</span>
      </div>

      <div className="grid grid-cols-3 gap-4 items-center mb-4">
        <div className="text-left">
          <p
            className="text-2xl sm:text-3xl font-black uppercase tracking-tight"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
            data-testid="team1-name"
          >
            {t1Short}
          </p>
          <p className="text-xs text-[#A1A1AA] mt-1 truncate">{team1}</p>
        </div>

        <div className="text-center">
          <motion.p
            key={`${runs}-${wickets}-${overs}`}
            initial={{ scale: 1.1, color: "#007AFF" }}
            animate={{ scale: 1, color: "#FFFFFF" }}
            className="text-4xl sm:text-5xl font-black tabular-nums"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
            data-testid="match-score"
          >
            {runs}/{wickets}
          </motion.p>
          <p className="text-sm font-mono text-[#A1A1AA] mt-1 tabular-nums" data-testid="match-overs">
            ({overs} ov)
          </p>
        </div>

        <div className="text-right">
          <p
            className="text-2xl sm:text-3xl font-black uppercase tracking-tight"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
            data-testid="team2-name"
          >
            {t2Short}
          </p>
          <p className="text-xs text-[#A1A1AA] mt-1 truncate">{team2}</p>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-white/10 pt-3">
        <div className="flex gap-4">
          <div>
            <span className="text-xs text-[#71717A] uppercase tracking-wider">CRR</span>
            <p className="font-mono font-bold tabular-nums text-sm" data-testid="crr-value">{crr}</p>
          </div>
          <div>
            <span className="text-xs text-[#71717A] uppercase tracking-wider">RRR</span>
            <p className="font-mono font-bold tabular-nums text-sm" data-testid="rrr-value">{rrr}</p>
          </div>
          <div>
            <span className="text-xs text-[#71717A] uppercase tracking-wider">INN</span>
            <p className="font-mono font-bold tabular-nums text-sm">{innings}</p>
          </div>
        </div>
        {probs.ensemble !== undefined && (
          <div className="flex gap-3">
            <div className="text-right">
              <span className="text-xs text-[#71717A]">{t1Short}</span>
              <p className={`font-mono font-bold tabular-nums text-sm ${probs.ensemble > 0.5 ? "text-[#22C55E]" : "text-[#FF3B30]"}`}>
                {(probs.ensemble * 100).toFixed(1)}%
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-[#71717A]">{t2Short}</span>
              <p className={`font-mono font-bold tabular-nums text-sm ${probs.ensemble < 0.5 ? "text-[#22C55E]" : "text-[#FF3B30]"}`}>
                {((1 - probs.ensemble) * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        )}
      </div>

      {status && (
        <p className="text-xs text-[#A1A1AA] mt-3 text-center italic" data-testid="match-status">
          {status}
        </p>
      )}
    </div>
  );
}
