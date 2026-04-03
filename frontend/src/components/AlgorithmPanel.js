import { Progress } from "@/components/ui/progress";

export default function AlgorithmPanel({ probabilities = {}, team1 = "T1", team2 = "T2" }) {
  const algorithms = [
    { key: "pressure_index", label: "Pressure Index", weight: "25%" },
    { key: "dls_resource", label: "DLS Resource", weight: "30%" },
    { key: "bayesian", label: "Bayesian", weight: "20%" },
    { key: "monte_carlo", label: "Monte Carlo", weight: "25%" },
  ];

  const ensemble = probabilities.ensemble || 0.5;

  return (
    <div data-testid="algorithm-panel" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-4"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Algorithm Models
      </h4>

      <div className="space-y-3">
        {algorithms.map((algo) => {
          const val = probabilities[algo.key] || 0.5;
          const pct = (val * 100).toFixed(1);
          return (
            <div key={algo.key} data-testid={`algo-${algo.key}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-[#A1A1AA]">
                  {algo.label} <span className="text-[#71717A]">({algo.weight})</span>
                </span>
                <span className={`text-xs font-mono font-bold tabular-nums ${val > 0.5 ? "text-[#22C55E]" : val < 0.5 ? "text-[#FF3B30]" : "text-white"}`}>
                  {pct}%
                </span>
              </div>
              <div className="h-1.5 bg-[#1E1E1E] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${pct}%`,
                    background: val > 0.5 ? "#007AFF" : val < 0.5 ? "#FF3B30" : "#71717A"
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-white/10">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
            Ensemble
          </span>
          <span className="font-mono font-bold tabular-nums text-[#007AFF]">
            {(ensemble * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex gap-1 h-3 rounded-full overflow-hidden">
          <div
            className="bg-[#007AFF] transition-all duration-500 rounded-l-full"
            style={{ width: `${ensemble * 100}%` }}
          />
          <div
            className="bg-[#FF3B30] transition-all duration-500 rounded-r-full"
            style={{ width: `${(1 - ensemble) * 100}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-xs font-mono text-[#A1A1AA]">
          <span>{team1}</span>
          <span>{team2}</span>
        </div>
      </div>
    </div>
  );
}
