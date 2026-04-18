import { Scales, Sparkle, ChartBar } from "@phosphor-icons/react";

function PredictionBox({ label, icon: Icon, team1, team2, t1Prob, t2Prob, accentColor, subLabel }) {
  const t1Color = t1Prob > t2Prob ? "#34C759" : "#FF3B30";
  const t2Color = t2Prob > t1Prob ? "#34C759" : "#FF3B30";

  return (
    <div className="bg-[#0A0A0A] border border-[#262626] rounded-lg p-4 flex-1 min-w-0" data-testid={`prediction-box-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center gap-1.5 mb-3">
        <Icon weight="fill" className="w-3.5 h-3.5" style={{ color: accentColor }} />
        <span className="text-[10px] font-bold uppercase tracking-[0.15em]" style={{ color: accentColor }}>{label}</span>
      </div>
      {subLabel && <p className="text-[9px] text-[#525252] mb-2 font-mono">{subLabel}</p>}
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-base font-black font-mono" style={{ color: t1Color, fontFamily: "'Barlow Condensed'" }}>
          {team1} {t1Prob}%
        </span>
        <span className="text-base font-black font-mono" style={{ color: t2Color, fontFamily: "'Barlow Condensed'" }}>
          {t2Prob}% {team2}
        </span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-[#1A1A1A]">
        <div className="h-full transition-all duration-700 rounded-l-full" style={{ width: `${t1Prob}%`, backgroundColor: t1Color }} />
        <div className="h-full transition-all duration-700 rounded-r-full" style={{ width: `${t2Prob}%`, backgroundColor: t2Color }} />
      </div>
    </div>
  );
}

export default function CombinedPredictionBlock({ algoData, claudeData, team1, team2 }) {
  const algoPred = algoData?.prediction;
  const claudeAnalysis = claudeData?.analysis;

  const algoT1Raw = algoPred?.team1_win_prob;
  const algoT2Raw = algoPred?.team2_win_prob;
  const algoT1 =
    algoT1Raw == null || algoT1Raw === "" ? null : Number.isFinite(Number(algoT1Raw)) ? Number(algoT1Raw) : null;
  const algoT2 =
    algoT2Raw == null || algoT2Raw === "" ? null : Number.isFinite(Number(algoT2Raw)) ? Number(algoT2Raw) : null;
  const claudeT1 = claudeAnalysis?.team1_win_pct;
  const claudeT2 = claudeAnalysis?.team2_win_pct;

  const hasAlgo = algoT1 != null && algoT2 != null;
  const hasClaude = claudeT1 != null && claudeT2 != null;

  if (!hasAlgo && !hasClaude) return null;

  // Calculate average
  let avgT1 = null, avgT2 = null;
  if (hasAlgo && hasClaude) {
    avgT1 = Math.round(((algoT1 + claudeT1) / 2) * 10) / 10;
    avgT2 = Math.round((100 - avgT1) * 10) / 10;
  }

  const primaryT1 = avgT1 ?? algoT1 ?? claudeT1;
  const primaryT2 = avgT2 ?? algoT2 ?? claudeT2;
  const primaryColor = primaryT1 > primaryT2 ? "#34C759" : "#FF3B30";
  const primaryColorT2 = primaryT2 > primaryT1 ? "#34C759" : "#FF3B30";

  // Consensus
  let consensus = null;
  if (hasAlgo && hasClaude) {
    const diff = Math.abs(algoT1 - claudeT1);
    if (diff <= 5) consensus = { label: "HIGH CONSENSUS", color: "#34C759" };
    else if (diff <= 15) consensus = { label: "MODERATE CONSENSUS", color: "#EAB308" };
    else consensus = { label: "LOW CONSENSUS", color: "#FF3B30" };
  }

  return (
    <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4" data-testid="combined-prediction-block">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1.5">
          <ChartBar weight="fill" className="w-3.5 h-3.5 text-[#007AFF]" />
          Combined Prediction
        </p>
        {consensus && (
          <span className="text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider"
            style={{ backgroundColor: consensus.color + "15", color: consensus.color }}
            data-testid="model-consensus">
            {consensus.label}
          </span>
        )}
      </div>

      {/* Main Average Display */}
      {(avgT1 != null) ? (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-2xl font-black font-mono" style={{ color: primaryColor, fontFamily: "'Barlow Condensed'" }} data-testid="avg-team1-prob">
              {team1} {avgT1}%
            </span>
            <span className="text-[10px] text-[#525252] font-mono uppercase tracking-wider">Average</span>
            <span className="text-2xl font-black font-mono" style={{ color: primaryColorT2, fontFamily: "'Barlow Condensed'" }} data-testid="avg-team2-prob">
              {avgT2}% {team2}
            </span>
          </div>
          <div className="flex h-3.5 rounded-full overflow-hidden bg-[#1A1A1A]">
            <div className="h-full transition-all duration-700 rounded-l-full" style={{ width: `${avgT1}%`, backgroundColor: primaryColor }} />
            <div className="h-full transition-all duration-700 rounded-r-full" style={{ width: `${avgT2}%`, backgroundColor: primaryColorT2 }} />
          </div>
        </div>
      ) : (
        <p className="text-xs text-[#525252]">Run both Algorithm and Claude predictions to see the combined average.</p>
      )}

      {/* Individual Model Boxes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {hasAlgo && (
          <PredictionBox
            label="Algorithm"
            icon={Scales}
            team1={team1}
            team2={team2}
            t1Prob={algoT1}
            t2Prob={algoT2}
            accentColor="#007AFF"
            subLabel="5-factor logistic model"
          />
        )}
        {hasClaude && (
          <PredictionBox
            label="Claude Opus"
            icon={Sparkle}
            team1={team1}
            team2={team2}
            t1Prob={claudeT1}
            t2Prob={claudeT2}
            accentColor="#A855F7"
            subLabel="AI narrative analysis"
          />
        )}
      </div>

      {/* Difference indicator when both available */}
      {hasAlgo && hasClaude && (
        <div className="flex items-center justify-center gap-2 py-1">
          <span className="text-[9px] text-[#525252] font-mono">
            Model spread: {Math.abs(algoT1 - claudeT1).toFixed(1)}% difference
          </span>
        </div>
      )}
    </div>
  );
}
