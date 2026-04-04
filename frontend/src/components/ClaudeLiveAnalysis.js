import { Sparkle, TrendUp, TrendDown, Equals, Lightning } from "@phosphor-icons/react";

function ThreatBadge({ level }) {
  const colors = {
    HIGH: "bg-[#FF3B30]/20 text-[#FF3B30]",
    MEDIUM: "bg-[#FFCC00]/20 text-[#FFCC00]",
    LOW: "bg-[#34C759]/20 text-[#34C759]",
  };
  return (
    <span className={`text-[8px] px-1 py-0.5 rounded font-bold uppercase ${colors[level] || colors.MEDIUM}`}>
      {level}
    </span>
  );
}

export default function ClaudeLiveAnalysis({ data, loading, onFetch }) {
  if (!data && !loading) {
    return (
      <div className="bg-[#0A0A0A] border border-[#262626] rounded-xl p-4" data-testid="claude-live-empty">
        <div className="flex items-center gap-2 mb-2">
          <Sparkle size={16} className="text-[#A78BFA]" weight="fill" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">Claude Live Analysis</span>
        </div>
        <p className="text-[10px] text-[#737373] mb-3">Real-time expert analysis of current match state, momentum, and betting advice.</p>
        <button
          onClick={onFetch}
          className="px-3 py-1.5 rounded-lg bg-[#A78BFA] hover:bg-[#8B5CF6] text-white text-[10px] font-bold transition-colors"
          data-testid="fetch-claude-live-btn"
        >
          Get Claude Live Analysis
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-[#0A0A0A] border border-[#A78BFA]/30 rounded-xl p-4 animate-pulse" data-testid="claude-live-loading">
        <div className="flex items-center gap-2">
          <Sparkle size={16} className="text-[#A78BFA] animate-spin" weight="fill" />
          <span className="text-xs font-bold text-white">Analyzing live match...</span>
        </div>
        <div className="mt-3 space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-10 bg-[#1A1A1A] rounded-lg" />)}
        </div>
      </div>
    );
  }

  const a = data?.analysis || data || {};
  const MomentumIcon = a.momentum === "EVEN" ? Equals : (a.momentum_reason?.includes("losing") ? TrendDown : TrendUp);
  const winProb = a.win_probability || {};
  const keys = Object.keys(winProb);

  return (
    <div className="bg-[#0A0A0A] border border-[#A78BFA]/20 rounded-xl overflow-hidden" data-testid="claude-live-analysis">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-[#A78BFA]/10 to-transparent">
        <div className="flex items-center gap-2">
          <Sparkle size={14} className="text-[#A78BFA]" weight="fill" />
          <span className="text-[10px] font-bold text-white uppercase tracking-wider">Claude Live Analysis</span>
          {a.confidence && (
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#A78BFA]/20 text-[#A78BFA] font-bold">{a.confidence}</span>
          )}
        </div>
      </div>

      <div className="px-4 pb-4 space-y-3">
        {/* State Summary */}
        {a.current_state_summary && (
          <p className="text-[11px] text-[#D4D4D4] leading-relaxed pt-2">{a.current_state_summary}</p>
        )}

        {/* Momentum */}
        {a.momentum && (
          <div className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border ${
            a.momentum === "EVEN" ? "border-[#525252]/30 bg-[#262626]/30" :
            "border-[#34C759]/30 bg-[#34C759]/5"
          }`}>
            <MomentumIcon size={14} className={a.momentum === "EVEN" ? "text-[#A3A3A3]" : "text-[#34C759]"} weight="bold" />
            <div>
              <span className="text-[10px] font-bold text-white">Momentum: {a.momentum}</span>
              <p className="text-[9px] text-[#A3A3A3]">{a.momentum_reason}</p>
            </div>
          </div>
        )}

        {/* Win Probability */}
        {keys.length >= 2 && (
          <div className="flex items-center gap-2">
            <div className="flex-1 text-center">
              <p className="text-[9px] text-[#737373]">{keys[0]}</p>
              <p className="text-lg font-black text-[#007AFF] font-mono">{winProb[keys[0]]}%</p>
            </div>
            <div className="text-[10px] text-[#525252]">vs</div>
            <div className="flex-1 text-center">
              <p className="text-[9px] text-[#737373]">{keys[1]}</p>
              <p className="text-lg font-black text-[#FF3B30] font-mono">{winProb[keys[1]]}%</p>
            </div>
          </div>
        )}

        {/* Key Batsman Assessment */}
        {a.key_batsman_assessment?.length > 0 && (
          <div>
            <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-1">Batsmen</p>
            <div className="space-y-1">
              {a.key_batsman_assessment.map((b, i) => (
                <div key={i} className="flex items-center justify-between px-2 py-1 bg-[#141414] rounded-md">
                  <div>
                    <span className="text-[10px] font-bold text-white">{b.name}</span>
                    <p className="text-[9px] text-[#A3A3A3]">{b.assessment}</p>
                  </div>
                  <ThreatBadge level={b.threat_level} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Bowler Assessment */}
        {a.key_bowler_assessment?.length > 0 && (
          <div>
            <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-1">Bowlers</p>
            <div className="space-y-1">
              {a.key_bowler_assessment.map((b, i) => (
                <div key={i} className="flex items-center justify-between px-2 py-1 bg-[#141414] rounded-md">
                  <div>
                    <span className="text-[10px] font-bold text-white">{b.name}</span>
                    <p className="text-[9px] text-[#A3A3A3]">{b.assessment}</p>
                  </div>
                  <ThreatBadge level={b.threat_level} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Phase Analysis */}
        {a.phase_analysis && (
          <div className="bg-[#1A1A1A] rounded-lg p-2.5 border border-[#262626]">
            <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-0.5">Phase</p>
            <p className="text-[10px] text-[#D4D4D4] leading-relaxed">{a.phase_analysis}</p>
          </div>
        )}

        {/* Betting Advice */}
        {a.betting_advice && (
          <div className="bg-gradient-to-r from-[#A78BFA]/10 to-[#7C3AED]/10 border border-[#A78BFA]/30 rounded-lg p-2.5">
            <div className="flex items-center gap-1 mb-0.5">
              <Lightning size={11} className="text-[#A78BFA]" weight="fill" />
              <span className="text-[9px] font-bold text-[#A78BFA] uppercase">Betting Advice</span>
            </div>
            <p className="text-[10px] font-bold text-white leading-relaxed">{a.betting_advice}</p>
          </div>
        )}

        {/* Projected Outcome */}
        {a.projected_outcome && (
          <p className="text-[10px] text-[#A3A3A3] italic">{a.projected_outcome}</p>
        )}

        {/* Refresh */}
        <button
          onClick={onFetch}
          className="w-full px-3 py-1.5 rounded-lg border border-[#A78BFA]/30 text-[#A78BFA] text-[10px] font-bold hover:bg-[#A78BFA]/10 transition-colors"
          data-testid="refresh-claude-live-btn"
        >
          Refresh Live Analysis
        </button>
      </div>
    </div>
  );
}
