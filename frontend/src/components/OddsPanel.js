import { TrendUp, TrendDown, Equals } from "@phosphor-icons/react";

export default function OddsPanel({ odds = {}, history = [], team1 = "T1", team2 = "T2" }) {
  const t1Odds = odds.team1 || 2.0;
  const t2Odds = odds.team2 || 2.0;
  const t1Implied = ((1 / t1Odds) * 100).toFixed(1);
  const t2Implied = ((1 / t2Odds) * 100).toFixed(1);

  const trend1 = history.length >= 2
    ? history[history.length - 1]?.team1 - history[history.length - 2]?.team1
    : 0;
  const trend2 = history.length >= 2
    ? history[history.length - 1]?.team2 - history[history.length - 2]?.team2
    : 0;

  const TrendIcon = ({ val }) => {
    if (val < -0.01) return <TrendDown weight="bold" className="w-3 h-3 text-[#22C55E]" />;
    if (val > 0.01) return <TrendUp weight="bold" className="w-3 h-3 text-[#FF3B30]" />;
    return <Equals weight="bold" className="w-3 h-3 text-[#71717A]" />;
  };

  return (
    <div data-testid="odds-panel" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-4"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Odds Engine
      </h4>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#1E1E1E] rounded-md p-3 text-center border border-white/5 hover:border-[#007AFF]/30 transition-colors">
          <p className="text-xs text-[#A1A1AA] mb-1">{team1}</p>
          <p className="text-2xl font-bold font-mono tabular-nums" data-testid="odds-team1">
            {t1Odds.toFixed(2)}
          </p>
          <div className="flex items-center justify-center gap-1 mt-1">
            <TrendIcon val={trend1} />
            <span className="text-[10px] font-mono text-[#A1A1AA]">{t1Implied}%</span>
          </div>
        </div>
        <div className="bg-[#1E1E1E] rounded-md p-3 text-center border border-white/5 hover:border-[#FF3B30]/30 transition-colors">
          <p className="text-xs text-[#A1A1AA] mb-1">{team2}</p>
          <p className="text-2xl font-bold font-mono tabular-nums" data-testid="odds-team2">
            {t2Odds.toFixed(2)}
          </p>
          <div className="flex items-center justify-center gap-1 mt-1">
            <TrendIcon val={trend2} />
            <span className="text-[10px] font-mono text-[#A1A1AA]">{t2Implied}%</span>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-white/10">
        <div className="flex justify-between text-xs">
          <span className="text-[#71717A]">Market Edge</span>
          <span className={`font-mono font-bold tabular-nums ${
            parseFloat(t1Implied) + parseFloat(t2Implied) > 100 ? "text-[#EAB308]" : "text-[#22C55E]"
          }`}>
            {(parseFloat(t1Implied) + parseFloat(t2Implied) - 100).toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
