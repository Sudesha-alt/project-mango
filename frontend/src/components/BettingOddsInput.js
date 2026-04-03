import { useState } from "react";
import { Scales, TrendUp, TrendDown } from "@phosphor-icons/react";

export default function BettingOddsInput({ team1 = "T1", team2 = "T2", onOddsChange, currentEdge }) {
  const [t1Odds, setT1Odds] = useState("");
  const [t2Odds, setT2Odds] = useState("");
  const [confidence, setConfidence] = useState(50);

  const handleApply = () => {
    if (onOddsChange) {
      onOddsChange({
        betting_team1_odds: t1Odds ? parseFloat(t1Odds) : null,
        betting_team2_odds: t2Odds ? parseFloat(t2Odds) : null,
        betting_confidence: confidence,
      });
    }
  };

  return (
    <div data-testid="betting-odds-input" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        <Scales weight="bold" className="inline w-4 h-4 mr-1" /> Betting Odds
      </h4>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-[10px] text-[#71717A] mb-1 block">{team1} Odds</label>
          <input
            type="number" step="0.01" placeholder="e.g. 1.65"
            value={t1Odds} onChange={(e) => setT1Odds(e.target.value)}
            data-testid="odds-input-team1"
            className="w-full bg-[#1E1E1E] border border-white/10 rounded px-2 py-1.5 text-xs font-mono text-white placeholder:text-[#71717A] focus:border-[#007AFF] focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[10px] text-[#71717A] mb-1 block">{team2} Odds</label>
          <input
            type="number" step="0.01" placeholder="e.g. 2.30"
            value={t2Odds} onChange={(e) => setT2Odds(e.target.value)}
            data-testid="odds-input-team2"
            className="w-full bg-[#1E1E1E] border border-white/10 rounded px-2 py-1.5 text-xs font-mono text-white placeholder:text-[#71717A] focus:border-[#007AFF] focus:outline-none"
          />
        </div>
      </div>

      <div className="mb-3">
        <div className="flex justify-between mb-1">
          <label className="text-[10px] text-[#71717A]">Confidence in odds</label>
          <span className="text-[10px] font-mono text-[#A1A1AA]">{confidence}%</span>
        </div>
        <input
          type="range" min="0" max="100" value={confidence}
          onChange={(e) => setConfidence(parseInt(e.target.value))}
          data-testid="confidence-slider"
          className="w-full h-1 bg-[#333] rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-[#007AFF] [&::-webkit-slider-thumb]:rounded-full"
        />
      </div>

      <button onClick={handleApply} data-testid="apply-odds-btn"
        className="w-full py-1.5 bg-[#007AFF]/20 text-[#007AFF] rounded text-[10px] font-bold uppercase hover:bg-[#007AFF]/30 transition-colors">
        Apply to Bayesian Model
      </button>

      {/* Edge Display */}
      {currentEdge && (
        <div className="mt-3 pt-3 border-t border-white/10 space-y-2" data-testid="edge-display">
          {currentEdge.team1 && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-[#A1A1AA]">{team1}</span>
              <div className="flex items-center gap-2 text-[10px] font-mono">
                <span className="text-[#71717A]">Mkt: {currentEdge.team1.market_implied}%</span>
                <span className="text-white">Model: {currentEdge.team1.model_prob}%</span>
                <span className={`font-bold flex items-center gap-0.5 ${currentEdge.team1.edge_positive ? "text-[#22C55E]" : "text-[#FF3B30]"}`}>
                  {currentEdge.team1.edge_positive ? <TrendUp weight="bold" className="w-3 h-3" /> : <TrendDown weight="bold" className="w-3 h-3" />}
                  {currentEdge.team1.edge > 0 ? "+" : ""}{currentEdge.team1.edge}%
                </span>
              </div>
            </div>
          )}
          {currentEdge.team2 && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-[#A1A1AA]">{team2}</span>
              <div className="flex items-center gap-2 text-[10px] font-mono">
                <span className="text-[#71717A]">Mkt: {currentEdge.team2.market_implied}%</span>
                <span className="text-white">Model: {currentEdge.team2.model_prob}%</span>
                <span className={`font-bold flex items-center gap-0.5 ${currentEdge.team2.edge_positive ? "text-[#22C55E]" : "text-[#FF3B30]"}`}>
                  {currentEdge.team2.edge_positive ? <TrendUp weight="bold" className="w-3 h-3" /> : <TrendDown weight="bold" className="w-3 h-3" />}
                  {currentEdge.team2.edge > 0 ? "+" : ""}{currentEdge.team2.edge}%
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
