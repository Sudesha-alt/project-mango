import {
  ShieldCheck, XCircle, Clock, TrendUp, Info, ArrowRight
} from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";

const SIGNAL_STYLES = {
  STRONG_VALUE: { bg: "bg-[#34C759]/10", border: "border-[#34C759]/50", text: "text-[#34C759]", label: "STRONG VALUE" },
  VALUE: { bg: "bg-[#34C759]/10", border: "border-[#34C759]/30", text: "text-[#34C759]", label: "VALUE" },
  SMALL_EDGE: { bg: "bg-[#FFCC00]/10", border: "border-[#FFCC00]/30", text: "text-[#FFCC00]", label: "SMALL EDGE" },
  NO_BET: { bg: "bg-[#FF3B30]/10", border: "border-[#FF3B30]/30", text: "text-[#FF3B30]", label: "NO BET" },
  AVOID: { bg: "bg-[#FF3B30]/15", border: "border-[#FF3B30]/50", text: "text-[#FF3B30]", label: "AVOID" },
  WAIT_FOR_MORE_DATA: { bg: "bg-[#A3A3A3]/10", border: "border-[#A3A3A3]/30", text: "text-[#A3A3A3]", label: "WAIT" },
  NO_MARKET: { bg: "bg-[#A3A3A3]/10", border: "border-[#A3A3A3]/30", text: "text-[#A3A3A3]", label: "NO MARKET" },
};

export { SIGNAL_STYLES };

export function WinGauge({ probability }) {
  const p = probability || 50;
  const angle = (p / 100) * 180;
  const r = 80;
  const cx = 100, cy = 95;
  const rad = (angle * Math.PI) / 180;
  const x = cx - r * Math.cos(rad);
  const y = cy - r * Math.sin(rad);
  const color = p > 60 ? "#34C759" : p > 45 ? "#FFCC00" : "#FF3B30";
  return (
    <div data-testid="win-probability-gauge" className="flex flex-col items-center">
      <div className="flex items-center gap-1 mb-1">
        <InfoTooltip text="Win probability from the 6-layer decision engine: features, logistic model, live model, 50K negative-binomial simulations, Platt calibration, and odds comparison." />
      </div>
      <svg viewBox="0 0 200 110" className="w-full max-w-[220px]">
        <path d="M 20 95 A 80 80 0 0 1 180 95" fill="none" stroke="#262626" strokeWidth="10" strokeLinecap="round" />
        <path d={`M 20 95 A 80 80 0 ${angle > 90 ? 1 : 0} 1 ${x} ${y}`} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" />
        <text x="100" y="85" textAnchor="middle" fill="white" fontSize="32" fontWeight="900" fontFamily="'Barlow Condensed', sans-serif">{p}%</text>
        <text x="100" y="102" textAnchor="middle" fill="#737373" fontSize="9" fontFamily="'IBM Plex Sans', sans-serif" fontWeight="600" textTransform="uppercase" letterSpacing="0.15em">WIN PROBABILITY</text>
      </svg>
    </div>
  );
}

export function SignalBadge({ signal }) {
  const s = SIGNAL_STYLES[signal] || SIGNAL_STYLES.NO_MARKET;
  return (
    <span data-testid="value-signal-badge" className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-mono text-xs font-bold uppercase tracking-wider ${s.bg} ${s.border} ${s.text}`}>
      {signal === "STRONG_VALUE" || signal === "VALUE" ? <ShieldCheck weight="fill" className="w-3.5 h-3.5" /> :
       signal === "AVOID" || signal === "NO_BET" ? <XCircle weight="fill" className="w-3.5 h-3.5" /> :
       <Clock weight="fill" className="w-3.5 h-3.5" />}
      {s.label}
    </span>
  );
}

export function EdgeMeter({ edge }) {
  if (edge === null || edge === undefined) return null;
  const clamped = Math.max(-15, Math.min(15, edge));
  const pct = ((clamped + 15) / 30) * 100;
  const color = edge > 4 ? "#34C759" : edge > 0 ? "#FFCC00" : "#FF3B30";
  return (
    <div data-testid="edge-meter" className="space-y-1">
      <div className="flex justify-between text-[10px] uppercase tracking-wider font-semibold">
        <span className="text-[#FF3B30]">AVOID</span>
        <span className="text-[#A3A3A3] flex items-center gap-1">EDGE <InfoTooltip text="Edge = your model's probability minus the bookmaker's implied probability." /></span>
        <span className="text-[#34C759]">VALUE</span>
      </div>
      <div className="h-2 bg-[#262626] rounded-full relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-[#FF3B30] via-[#262626] to-[#34C759] opacity-30 rounded-full" />
        <div className="absolute top-0 h-full w-1 bg-white rounded-full transition-all duration-500" style={{ left: `${pct}%` }} />
      </div>
      <p className="text-center font-mono text-sm font-bold" style={{ color }}>{edge > 0 ? "+" : ""}{edge}%</p>
    </div>
  );
}

export function EdgeReasons({ reasons, signal }) {
  if (!reasons || reasons.length === 0) return null;
  const s = SIGNAL_STYLES[signal] || SIGNAL_STYLES.NO_MARKET;
  return (
    <div data-testid="edge-reasons" className={`rounded-md border p-3 space-y-1.5 ${s.bg} ${s.border}`}>
      <p className="text-[10px] uppercase tracking-[0.2em] font-semibold flex items-center gap-1.5 text-[#A3A3A3]">
        <Info weight="fill" className="w-3.5 h-3.5" /> Why this signal?
      </p>
      {reasons.map((r, i) => (
        <div key={i} className="flex items-start gap-2 text-[11px] leading-relaxed">
          <ArrowRight weight="bold" className={`w-3 h-3 flex-shrink-0 mt-0.5 ${s.text}`} />
          <span className="text-[#D4D4D4]">{r}</span>
        </div>
      ))}
    </div>
  );
}

export function DriversPanel({ drivers }) {
  if (!drivers || drivers.length === 0) return null;
  return (
    <div data-testid="top-drivers" className="space-y-1.5">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Top Drivers <InfoTooltip text="Key factors driving the current prediction." /></p>
      {drivers.map((d, i) => (
        <div key={i} className="flex items-start gap-2 text-xs text-[#A3A3A3]">
          <TrendUp weight="bold" className="w-3.5 h-3.5 text-[#007AFF] flex-shrink-0 mt-0.5" />
          <span>{d}</span>
        </div>
      ))}
    </div>
  );
}

export function PlayerImpact({ players }) {
  if (!players || players.length === 0) return null;
  const buzzColor = (score) => {
    if (score >= 40) return "#34C759";
    if (score >= 10) return "#8BC34A";
    if (score >= -10) return "#737373";
    if (score >= -40) return "#FF9800";
    return "#FF3B30";
  };
  return (
    <div data-testid="player-impact" className="space-y-1.5">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Player Impact <InfoTooltip text="Player predictions from Expected Playing XI." /></p>
      <div className="space-y-1">
        {players.map((p, i) => {
          const bs = p.buzz_score ?? 0;
          const isPos = bs >= 0;
          return (
            <div key={i} className="flex items-center justify-between py-1 border-b border-[#262626] last:border-0" title={p.buzz_reason || ""}>
              <div className="flex items-center gap-2">
                <span className="text-xs text-white font-medium">{p.name}</span>
                <span className="text-[9px] text-[#737373] font-mono">{p.role?.slice(0, 3).toUpperCase()}</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-mono tabular-nums">
                <span className="text-[#007AFF]">{p.predicted_runs}r</span>
                <span className="text-[#FF3B30]">{p.predicted_wickets}w</span>
                <span className="px-1 py-0 rounded text-[9px] font-bold" style={{ color: buzzColor(bs), backgroundColor: buzzColor(bs) + "18" }}>
                  {isPos ? "+" : ""}{bs}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function UncertaintyBand({ band, confidence }) {
  if (!band) return null;
  return (
    <div data-testid="uncertainty-band" className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-[#262626] rounded-full relative">
        <div className="absolute h-full bg-[#007AFF]/30 rounded-full" style={{ left: `${band.low * 100}%`, width: `${(band.high - band.low) * 100}%` }} />
      </div>
      <span className="text-[10px] text-[#A3A3A3] font-mono whitespace-nowrap">
        {(band.low * 100).toFixed(0)}–{(band.high * 100).toFixed(0)}% | conf {(confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}

export function SimulationSummary({ sim, team1, team2 }) {
  if (!sim) return null;
  const t1Win = sim.team1_win_prob > sim.team2_win_prob;
  return (
    <div data-testid="simulation-summary" className="space-y-2">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">{sim.simulations?.toLocaleString()} Simulations (Neg. Binomial) <InfoTooltip text="50,000 match simulations using Negative Binomial distribution." /></p>
      {(sim.mean_team1_score || sim.mean_team2_score) && (
        <div className="flex items-center justify-between bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2">
          <div className="text-center flex-1">
            <p className="text-[9px] text-[#737373] uppercase tracking-wider">{team1}</p>
            <p className="text-xl font-black font-mono text-white" style={{ fontFamily: "'Barlow Condensed'" }}>{Math.round(sim.mean_team1_score)}</p>
            <p className="text-[8px] text-[#737373]">predicted runs</p>
          </div>
          <div className="text-[10px] text-[#525252] font-bold px-2">vs</div>
          <div className="text-center flex-1">
            <p className="text-[9px] text-[#737373] uppercase tracking-wider">{team2}</p>
            <p className="text-xl font-black font-mono text-white" style={{ fontFamily: "'Barlow Condensed'" }}>{Math.round(sim.mean_team2_score)}</p>
            <p className="text-[8px] text-[#737373]">predicted runs</p>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: team1, data: sim.team1_scores, prob: sim.team1_win_prob, isWinner: t1Win },
          { label: team2, data: sim.team2_scores, prob: sim.team2_win_prob, isWinner: !t1Win },
        ].map(({ label, data, prob, isWinner }) => (
          <div key={label} className={`bg-[#0A0A0A] border rounded-md p-2.5 ${isWinner ? "border-[#34C759]/30" : "border-[#262626]"}`}>
            <p className="text-[10px] text-[#737373] mb-1">{label}</p>
            <p className={`text-lg font-black font-mono ${isWinner ? "text-[#34C759]" : "text-[#FF3B30]"}`} style={{ fontFamily: "'Barlow Condensed'" }}>{(prob * 100).toFixed(1)}%</p>
            <p className="text-[9px] text-[#737373] font-mono">Mean: {data?.mean} | Med: {data?.median}</p>
            <p className="text-[9px] text-[#737373] font-mono">Range: {data?.p10}–{data?.p90}</p>
          </div>
        ))}
      </div>
      {sim.batting_first_win_pct && (
        <p className="text-[9px] text-[#525252] font-mono text-center">Batting first wins {sim.batting_first_win_pct}% of simulations</p>
      )}
    </div>
  );
}
