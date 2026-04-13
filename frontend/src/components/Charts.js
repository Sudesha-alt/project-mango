import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ReferenceLine, Cell
} from "recharts";

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0A0A0A] border border-white/20 rounded-md px-3 py-2 text-xs shadow-lg">
      <p className="text-[#71717A] mb-1 font-mono">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-mono tabular-nums">
          {p.name}: {typeof p.value === "number" ? (p.value > 1 ? p.value : (p.value * 100).toFixed(1) + "%") : p.value}
        </p>
      ))}
    </div>
  );
};

const ALGO_COLORS = {
  pressure_index: "#007AFF",
  dls_resource: "#FF3B30",
  bayesian: "#7F77DD",
  monte_carlo: "#EF9F27",
  ensemble: "#FFFFFF",
};

// CHART 1: Win Probability Over Time (multi-line)
export function WinProbabilityChart({ data = [], team1 = "T1", team2 = "T2" }) {
  const chartData = data.map((d, i) => ({
    ball: i + 1,
    over: `${Math.floor(i / 6)}.${i % 6}`,
    pressure_index: d.pressure_index || d.ensemble || 0.5,
    dls_resource: d.dls_resource || d.ensemble || 0.5,
    bayesian: d.bayesian || d.ensemble || 0.5,
    monte_carlo: d.monte_carlo || d.ensemble || 0.5,
    ensemble: d.ensemble || 0.5,
    conf_upper: Math.min((d.ensemble || 0.5) + (d.confidence_band || 0.05), 0.98),
    conf_lower: Math.max((d.ensemble || 0.5) - (d.confidence_band || 0.05), 0.02),
  }));
  if (chartData.length === 0) chartData.push({ ball: 0, pressure_index: 0.5, dls_resource: 0.5, bayesian: 0.5, monte_carlo: 0.5, ensemble: 0.5, conf_upper: 0.55, conf_lower: 0.45 });

  return (
    <div data-testid="win-probability-chart" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-1" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        Win Probability
      </h4>
      {/* Custom legend */}
      <div className="flex flex-wrap gap-3 mb-2">
        {[
          { key: "pressure_index", label: "Pressure", color: ALGO_COLORS.pressure_index },
          { key: "dls_resource", label: "DLS", color: ALGO_COLORS.dls_resource },
          { key: "bayesian", label: "Bayesian", color: ALGO_COLORS.bayesian, dash: true },
          { key: "monte_carlo", label: "Monte Carlo", color: ALGO_COLORS.monte_carlo, dash: true },
          { key: "ensemble", label: "Ensemble", color: ALGO_COLORS.ensemble, bold: true },
        ].map((item) => (
          <div key={item.key} className="flex items-center gap-1">
            <div className="w-4 h-0.5" style={{ background: item.color, borderTop: item.dash ? `2px dashed ${item.color}` : "none" }} />
            <span className="text-[9px] text-[#A1A1AA]">{item.label}</span>
          </div>
        ))}
      </div>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <defs>
              <linearGradient id="confBand" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFFFFF" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#FFFFFF" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <XAxis dataKey="ball" tick={{ fill: "#71717A", fontSize: 9 }} tickFormatter={(v) => v % 6 === 0 ? `Ov ${v / 6}` : ""} />
            <YAxis domain={[0, 1]} tick={{ fill: "#71717A", fontSize: 9 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <ReferenceLine y={0.5} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
            <Tooltip content={<ChartTooltip />} />
            <Line type="monotone" dataKey="pressure_index" name="Pressure" stroke={ALGO_COLORS.pressure_index} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="dls_resource" name="DLS" stroke={ALGO_COLORS.dls_resource} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="bayesian" name="Bayesian" stroke={ALGO_COLORS.bayesian} strokeWidth={1.5} strokeDasharray="5 3" dot={false} />
            <Line type="monotone" dataKey="monte_carlo" name="Monte Carlo" stroke={ALGO_COLORS.monte_carlo} strokeWidth={1.5} strokeDasharray="5 3" dot={false} />
            <Line type="monotone" dataKey="ensemble" name="Ensemble" stroke={ALGO_COLORS.ensemble} strokeWidth={3} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex justify-between mt-2 text-xs font-mono">
        <span className="text-[#007AFF]">{team1}: {chartData.length > 0 ? (chartData[chartData.length - 1].ensemble * 100).toFixed(1) : 50}%</span>
        <span className="text-[#FF3B30]">{team2}: {chartData.length > 0 ? ((1 - chartData[chartData.length - 1].ensemble) * 100).toFixed(1) : 50}%</span>
      </div>
    </div>
  );
}

// CHART 2: Manhattan (color-coded by run rate)
export function ManhattanChart({ data = [] }) {
  const getBarColor = (entry) => {
    if (!entry) return "#333";
    const rpo = entry.runs || 0;
    if (entry.hasWicket) return "#FF3B30";
    if (rpo > 8) return "#22C55E";
    if (rpo >= 6) return "#EAB308";
    return "#71717A";
  };

  return (
    <div data-testid="manhattan-chart" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-1" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Manhattan</h4>
      <div className="flex gap-3 mb-2">
        {[{ color: "#71717A", label: "< 6 RPO" }, { color: "#EAB308", label: "6-8 RPO" }, { color: "#22C55E", label: "> 8 RPO" }, { color: "#FF3B30", label: "Wicket" }].map((l) => (
          <div key={l.label} className="flex items-center gap-1">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ background: l.color }} />
            <span className="text-[9px] text-[#A1A1AA]">{l.label}</span>
          </div>
        ))}
      </div>
      {data.length > 0 ? (
        <div style={{ height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <XAxis dataKey="over" tick={{ fill: "#71717A", fontSize: 9 }} />
              <YAxis hide />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="runs" radius={[3, 3, 0, 0]}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={getBarColor(entry)} stroke={entry?.hasWicket ? "#FF3B30" : "none"} strokeWidth={entry?.hasWicket ? 2 : 0} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-[180px] flex items-center justify-center text-sm text-[#71717A]">No over-by-over data yet</div>
      )}
    </div>
  );
}

// CHART 3: Algorithm Comparison (horizontal bars)
export function AlgorithmComparisonChart({ probabilities = {}, team1 = "T1", team2 = "T2" }) {
  const algos = [
    { key: "pressure_index", label: "Pressure Index", color: ALGO_COLORS.pressure_index },
    { key: "dls_resource", label: "DLS Resource", color: ALGO_COLORS.dls_resource },
    { key: "bayesian", label: "Bayesian", color: ALGO_COLORS.bayesian },
    { key: "monte_carlo", label: "Monte Carlo", color: ALGO_COLORS.monte_carlo },
    { key: "ensemble", label: "Ensemble", color: ALGO_COLORS.ensemble },
  ];

  return (
    <div data-testid="algo-comparison-chart" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        Algorithm Comparison
      </h4>
      <div className="space-y-2.5">
        {algos.map((algo) => {
          const val = probabilities[algo.key] || 0.5;
          const pct = (val * 100).toFixed(1);
          const isEnsemble = algo.key === "ensemble";
          return (
            <div key={algo.key} data-testid={`algo-bar-${algo.key}`}>
              <div className="flex items-center justify-between mb-0.5">
                <span className={`text-[10px] ${isEnsemble ? "font-bold text-white" : "text-[#A1A1AA]"}`}>{algo.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono tabular-nums" style={{ color: algo.color }}>{pct}%</span>
                  <span className="text-[10px] font-mono tabular-nums text-[#71717A]">{(100 - parseFloat(pct)).toFixed(1)}%</span>
                </div>
              </div>
              <div className={`flex gap-0.5 rounded-full overflow-hidden ${isEnsemble ? "h-3" : "h-2"}`}>
                <div className="rounded-l-full transition-all duration-700" style={{ width: `${pct}%`, background: algo.color }} />
                <div className="rounded-r-full bg-[#333] flex-1" />
              </div>
            </div>
          );
        })}
      </div>
      {probabilities.confidence_band && (
        <p className="text-[10px] text-[#71717A] mt-2 font-mono">
          Confidence band: +/-{(probabilities.confidence_band * 100).toFixed(1)}%
        </p>
      )}
    </div>
  );
}

// CHART 4: Algorithm Radar
export function AlgorithmRadarChart({ probabilities = {} }) {
  const data = [
    { algo: "Pressure", value: probabilities.pressure_index || 0.5 },
    { algo: "DLS", value: probabilities.dls_resource || 0.5 },
    { algo: "Bayesian", value: probabilities.bayesian || 0.5 },
    { algo: "Monte Carlo", value: probabilities.monte_carlo || 0.5 },
    { algo: "Ensemble", value: probabilities.ensemble || 0.5 },
  ];

  return (
    <div data-testid="algorithm-radar" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Algorithm Radar</h4>
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(255,255,255,0.1)" />
          <PolarAngleAxis dataKey="algo" tick={{ fill: "#A1A1AA", fontSize: 10 }} />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <Radar name="Win%" dataKey="value" stroke="#007AFF" fill="#007AFF" fillOpacity={0.2} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// CHART 5: Pre-match Radar (team comparison)
export function PreMatchRadarChart({ team1Data = {}, team2Data = {}, team1 = "T1", team2 = "T2" }) {
  const axes = ["Form", "H2H", "Venue", "Batting", "Bowling", "NRR"];
  const key = (axis) => axis.toLowerCase();
  const data = axes.map((axis) => ({
    axis,
    [team1]: team1Data[key(axis)] ?? 50,
    [team2]: team2Data[key(axis)] ?? 50,
  }));

  return (
    <div data-testid="prematch-radar" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Team Comparison</h4>
      <div className="flex gap-3 mb-2">
        <div className="flex items-center gap-1"><div className="w-3 h-0.5 bg-[#007AFF]" /><span className="text-[9px] text-[#A1A1AA]">{team1}</span></div>
        <div className="flex items-center gap-1"><div className="w-3 h-0.5 bg-[#FF3B30]" /><span className="text-[9px] text-[#A1A1AA]">{team2}</span></div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(255,255,255,0.1)" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "#A1A1AA", fontSize: 10 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar name={team1} dataKey={team1} stroke="#007AFF" fill="#007AFF" fillOpacity={0.15} strokeWidth={2} />
          <Radar name={team2} dataKey={team2} stroke="#FF3B30" fill="#FF3B30" fillOpacity={0.15} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
