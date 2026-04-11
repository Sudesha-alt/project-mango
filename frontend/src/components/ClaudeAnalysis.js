import { useState } from "react";
import { Sparkle, CaretRight, CaretDown, Warning, ArrowRight, Lightning, Trophy, Target, Crosshair, Sword, ShieldCheck, UsersFour, Strategy } from "@phosphor-icons/react";

const LAYER_ICONS = {
  1: UsersFour,    // Squad Strength
  2: Crosshair,    // Key Matchups
  3: Target,        // Venue & Pitch
  4: Sword,         // Bowling Depth
  5: Lightning,     // Death Bowling
  6: Strategy,      // H2H
  7: ShieldCheck,   // Impact Player
};

function LayerCard({ layer, t1Short, t2Short }) {
  const [open, setOpen] = useState(false);
  const advantageT1 = layer.advantage === t1Short;
  const advantageT2 = layer.advantage === t2Short;
  const Icon = LAYER_ICONS[layer.layer_num] || Target;

  return (
    <div
      className={`rounded-lg border overflow-hidden ${
        advantageT1 ? "border-[#007AFF]/30" :
        advantageT2 ? "border-[#FF3B30]/30" :
        "border-[#525252]/30"
      }`}
      data-testid={`claude-layer-${layer.layer_num}`}
    >
      <div
        className={`flex items-center justify-between px-3 py-2.5 cursor-pointer ${
          advantageT1 ? "bg-[#007AFF]/5" :
          advantageT2 ? "bg-[#FF3B30]/5" :
          "bg-[#262626]/30"
        }`}
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className={`flex items-center justify-center w-5 h-5 rounded text-[9px] font-black ${
            advantageT1 ? "bg-[#007AFF]/20 text-[#007AFF]" :
            advantageT2 ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
            "bg-[#525252]/20 text-[#A3A3A3]"
          }`}>
            <Icon size={12} weight="bold" />
          </div>
          <span className="text-[10px] font-bold text-white uppercase tracking-wider truncate">
            L{layer.layer_num} — {layer.title}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${
            advantageT1 ? "bg-[#007AFF]/20 text-[#007AFF]" :
            advantageT2 ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
            "bg-[#525252]/20 text-[#A3A3A3]"
          }`}>
            {layer.advantage}
          </span>
          {open ? <CaretDown size={12} className="text-[#737373]" /> : <CaretRight size={12} className="text-[#737373]" />}
        </div>
      </div>
      {open && (
        <div className="px-3 pb-3 pt-2 bg-[#0A0A0A]">
          <p className="text-[11px] text-[#D4D4D4] leading-relaxed whitespace-pre-line">{layer.analysis}</p>
          <p className={`text-[9px] font-mono mt-2 pt-1.5 border-t border-[#262626] ${
            advantageT1 ? "text-[#007AFF]/70" : advantageT2 ? "text-[#FF3B30]/70" : "text-[#737373]"
          }`}>
            ADVANTAGE: {layer.advantage} — {layer.advantage_reason}
          </p>
        </div>
      )}
    </div>
  );
}

function InjuryCard({ injury }) {
  const isOut = injury.status === "Out";
  const isDoubtful = injury.status === "Doubtful";
  return (
    <div className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border ${
      isOut ? "border-[#FF3B30]/30 bg-[#FF3B30]/5" :
      isDoubtful ? "border-[#FFCC00]/30 bg-[#FFCC00]/5" :
      "border-[#34C759]/30 bg-[#34C759]/5"
    }`} data-testid="injury-card">
      <Warning size={12} className={isOut ? "text-[#FF3B30]" : isDoubtful ? "text-[#FFCC00]" : "text-[#34C759]"} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold text-white">{injury.player}</span>
          <span className="text-[8px] text-[#737373]">({injury.team})</span>
          <span className={`text-[8px] px-1 py-0.5 rounded font-bold uppercase ${
            isOut ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
            isDoubtful ? "bg-[#FFCC00]/20 text-[#FFCC00]" :
            "bg-[#34C759]/20 text-[#34C759]"
          }`}>{injury.status}</span>
        </div>
        <p className="text-[9px] text-[#A3A3A3] truncate">{injury.impact}</p>
      </div>
    </div>
  );
}

export default function ClaudeAnalysis({ data, matchInfo, loading, onFetch }) {
  const [expanded, setExpanded] = useState(true);

  if (!data && !loading) {
    return (
      <div className="bg-[#0A0A0A] border border-[#262626] rounded-xl p-6" data-testid="claude-analysis-empty">
        <div className="flex items-center gap-2 mb-3">
          <Sparkle size={18} className="text-[#A78BFA]" weight="fill" />
          <span className="text-sm font-bold text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>CLAUDE OPUS ANALYSIS</span>
        </div>
        <p className="text-xs text-[#737373] mb-4">
          7-layer contextual match preview — squad strength, key matchups, venue, bowling depth, death overs, H2H, and impact player analysis powered by Claude Opus + SportMonks data.
        </p>
        <button
          onClick={onFetch}
          className="px-4 py-2 rounded-lg bg-[#A78BFA] hover:bg-[#8B5CF6] text-white text-xs font-bold transition-colors"
          data-testid="fetch-claude-analysis-btn"
        >
          Generate Claude Analysis
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-[#0A0A0A] border border-[#A78BFA]/30 rounded-xl p-6 animate-pulse" data-testid="claude-analysis-loading">
        <div className="flex items-center gap-2 mb-3">
          <Sparkle size={18} className="text-[#A78BFA] animate-spin" weight="fill" />
          <span className="text-sm font-bold text-white">CLAUDE OPUS ANALYZING...</span>
        </div>
        <p className="text-xs text-[#A3A3A3]">Running 7-layer analysis — expected XI, algorithm data, player form, venue stats, weather, H2H, matchups...</p>
        <p className="text-[10px] text-[#737373] mt-1">This may take 30-60 seconds.</p>
        <div className="mt-4 space-y-2">
          {[1,2,3,4,5,6,7].map(i => <div key={i} className="h-10 bg-[#1A1A1A] rounded-lg" />)}
        </div>
      </div>
    );
  }

  const a = data?.analysis || data || {};
  const t1Short = matchInfo?.team1Short || data?.team1Short || "T1";
  const t2Short = matchInfo?.team2Short || data?.team2Short || "T2";

  // Support both old format (factors) and new format (layers)
  const layers = a.layers || [];
  const factors = a.factors || [];
  const injuries = a.key_injuries || [];
  const batFirst = a.batting_first_scenario || {};
  const algoPredictions = a.algorithm_predictions || {};
  const analystPotm = a.analyst_potm || {};
  const isNewFormat = layers.length > 0;

  return (
    <div className="bg-[#0A0A0A] border border-[#A78BFA]/20 rounded-xl overflow-hidden" data-testid="claude-analysis">
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3 bg-gradient-to-r from-[#A78BFA]/10 to-transparent cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <Sparkle size={16} className="text-[#A78BFA]" weight="fill" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">Claude Opus Analysis</span>
          <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#A78BFA]/20 text-[#A78BFA] font-bold uppercase">
            {a.confidence || "Medium"}
          </span>
          {isNewFormat && (
            <span className="text-[7px] px-1 py-0.5 rounded bg-[#34C759]/15 text-[#34C759] font-bold uppercase">7-Layer</span>
          )}
        </div>
        <CaretRight size={14} className={`text-[#737373] transition-transform ${expanded ? "rotate-90" : ""}`} />
      </div>

      {expanded && (
        <div className="px-5 pb-5 space-y-4">
          {/* Win Probability Bar */}
          <div className="pt-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-[#007AFF]">{t1Short} {a.team1_win_pct || 50}%</span>
              <span className="text-[8px] text-[#737373] uppercase">Analyst</span>
              <span className="text-xs font-bold text-[#FF3B30]">{a.team2_win_pct || 50}% {t2Short}</span>
            </div>
            <div className="h-3 bg-[#1A1A1A] rounded-full overflow-hidden flex">
              <div
                className="bg-gradient-to-r from-[#007AFF] to-[#007AFF]/70 rounded-l-full transition-all"
                style={{ width: `${a.team1_win_pct || 50}%` }}
              />
              <div
                className="bg-gradient-to-l from-[#FF3B30] to-[#FF3B30]/70 rounded-r-full transition-all"
                style={{ width: `${a.team2_win_pct || 50}%` }}
              />
            </div>
            {/* Algorithm probability comparison */}
            {algoPredictions.algo_team1_win_pct > 0 && (
              <div className="mt-1.5">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[9px] text-[#007AFF]/60">{t1Short} {algoPredictions.algo_team1_win_pct}%</span>
                  <span className="text-[8px] text-[#737373] uppercase">Algorithm</span>
                  <span className="text-[9px] text-[#FF3B30]/60">{algoPredictions.algo_team2_win_pct}% {t2Short}</span>
                </div>
                <div className="h-1.5 bg-[#1A1A1A] rounded-full overflow-hidden flex">
                  <div className="bg-[#007AFF]/30 rounded-l-full" style={{ width: `${algoPredictions.algo_team1_win_pct}%` }} />
                  <div className="bg-[#FF3B30]/30 rounded-r-full" style={{ width: `${algoPredictions.algo_team2_win_pct}%` }} />
                </div>
              </div>
            )}
          </div>

          {/* Headline */}
          {a.headline && (
            <div className="bg-[#A78BFA]/10 border border-[#A78BFA]/20 rounded-lg px-3 py-2">
              <div className="flex items-center gap-1.5">
                <Lightning size={12} className="text-[#A78BFA]" weight="fill" />
                <span className="text-[11px] font-bold text-[#A78BFA]">KEY FACTOR</span>
              </div>
              <p className="text-xs text-white mt-0.5">{a.headline}</p>
            </div>
          )}

          {/* Divergence Note */}
          {a.algo_divergence_note && (
            <div className="bg-[#FFCC00]/5 border border-[#FFCC00]/20 rounded-lg px-3 py-2">
              <span className="text-[9px] font-bold text-[#FFCC00] uppercase">Algorithm vs Analyst Divergence</span>
              <p className="text-[10px] text-[#D4D4D4] mt-0.5">{a.algo_divergence_note}</p>
            </div>
          )}

          {/* 7 Layers */}
          {isNewFormat && (
            <div className="space-y-1.5">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold">Contextual Layer Analysis</p>
              {layers.map((layer, i) => (
                <LayerCard key={i} layer={layer} t1Short={t1Short} t2Short={t2Short} />
              ))}
            </div>
          )}

          {/* Old-format factors (backward compat) */}
          {!isNewFormat && factors.length > 0 && (
            <div className="space-y-2">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold">Analysis Factors</p>
              {factors.map((f, i) => (
                <div key={i} className={`rounded-lg border p-3.5 ${
                  f.favors === t1Short ? "border-[#007AFF]/30 bg-[#007AFF]/5" :
                  f.favors === t2Short ? "border-[#FF3B30]/30 bg-[#FF3B30]/5" :
                  "border-[#525252]/30 bg-[#262626]/30"
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-bold text-white">{f.title}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                      f.favors === t1Short ? "bg-[#007AFF]/20 text-[#007AFF]" :
                      f.favors === t2Short ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
                      "bg-[#525252]/20 text-[#A3A3A3]"
                    }`}>{f.favors || "NEUTRAL"}</span>
                  </div>
                  <p className="text-[11px] text-[#D4D4D4] leading-relaxed">{f.analysis}</p>
                  {f.tag && <p className="text-[9px] font-mono mt-1.5 text-[#737373]">{f.tag}</p>}
                </div>
              ))}
            </div>
          )}

          {/* Algorithm Predictions Table */}
          {algoPredictions.algo_potm && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-3">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2">Algorithm Predictions [SPORTMONKS]</p>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div>
                  <span className="text-[#737373]">POTM:</span>
                  <span className="text-white ml-1 font-bold">{algoPredictions.algo_potm}</span>
                </div>
                <div>
                  <span className="text-[#737373]">Top Batters:</span>
                  <span className="text-white ml-1">{(algoPredictions.algo_top_batters || []).join(", ") || "N/A"}</span>
                </div>
                <div>
                  <span className="text-[#737373]">Top Bowlers:</span>
                  <span className="text-white ml-1">{(algoPredictions.algo_top_bowlers || []).join(", ") || "N/A"}</span>
                </div>
              </div>
            </div>
          )}

          {/* Analyst POTM */}
          {analystPotm.player && (
            <div className="bg-[#A78BFA]/5 border border-[#A78BFA]/20 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Trophy size={12} className="text-[#A78BFA]" weight="fill" />
                <span className="text-[9px] font-bold text-[#A78BFA] uppercase tracking-wider">Analyst's Player of the Match</span>
              </div>
              <p className="text-sm font-bold text-white">{analystPotm.player}</p>
              {(analystPotm.reasons || []).map((r, i) => (
                <p key={i} className="text-[10px] text-[#D4D4D4] mt-0.5">{i+1}. {r}</p>
              ))}
            </div>
          )}

          {/* Injuries */}
          {injuries.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold">Injury & Availability</p>
              {injuries.map((inj, i) => (
                <InjuryCard key={i} injury={inj} />
              ))}
            </div>
          )}

          {/* Batting First Scenarios */}
          {batFirst.if_team1_bats && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-3">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2">Toss Scenarios</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="text-center">
                  <p className="text-[9px] text-[#A3A3A3]">If {t1Short} bats first</p>
                  <p className="text-lg font-black text-[#007AFF] font-mono">{t1Short} ~{batFirst.if_team1_bats?.team1_win_pct || 50}%</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-[#A3A3A3]">If {t2Short} bats first</p>
                  <p className="text-lg font-black text-[#FF3B30] font-mono">{t2Short} ~{batFirst.if_team2_bats?.team2_win_pct || 50}%</p>
                </div>
              </div>
            </div>
          )}

          {/* Deciding Factor */}
          {a.deciding_factor && (
            <div className="bg-[#1A1A1A] rounded-lg p-3 border border-[#262626]">
              <p className="text-[9px] text-[#FF9500] uppercase tracking-[0.2em] font-semibold mb-1">The Decisive Factor</p>
              <p className="text-[11px] text-[#D4D4D4] leading-relaxed">{a.deciding_factor}</p>
            </div>
          )}

          {/* First 6 Overs Signal */}
          {a.first_6_overs_signal && (
            <div className="bg-[#1A1A1A] rounded-lg p-3 border border-[#262626]">
              <p className="text-[9px] text-[#34C759] uppercase tracking-[0.2em] font-semibold mb-1">First 6 Overs Signal</p>
              <p className="text-[11px] text-[#D4D4D4] leading-relaxed">{a.first_6_overs_signal}</p>
            </div>
          )}

          {/* Deciding Logic */}
          {a.deciding_logic && (
            <div className="bg-[#1A1A1A] rounded-lg p-3 border border-[#262626]">
              <p className="text-[9px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-1">Deciding Logic</p>
              <p className="text-[11px] text-[#D4D4D4] leading-relaxed">{a.deciding_logic}</p>
            </div>
          )}

          {/* Prediction Summary */}
          {a.prediction_summary && (
            <div className="bg-gradient-to-r from-[#A78BFA]/10 to-[#7C3AED]/10 border border-[#A78BFA]/30 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <ArrowRight size={12} className="text-[#A78BFA]" />
                <span className="text-[9px] font-bold text-[#A78BFA] uppercase tracking-wider">Prediction</span>
              </div>
              <p className="text-xs font-bold text-white leading-relaxed">{a.prediction_summary}</p>
              <p className="text-[9px] text-[#737373] mt-1 font-mono">
                Confidence: {a.confidence} — {a.confidence_reason}
              </p>
            </div>
          )}

          {/* Refresh button */}
          <button
            onClick={onFetch}
            className="w-full px-3 py-1.5 rounded-lg border border-[#A78BFA]/30 text-[#A78BFA] text-[10px] font-bold hover:bg-[#A78BFA]/10 transition-colors"
            data-testid="refresh-claude-analysis-btn"
          >
            Refresh Analysis (re-run 7-layer analysis)
          </button>
        </div>
      )}
    </div>
  );
}
