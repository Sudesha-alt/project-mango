import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from "recharts";

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#141414] border border-white/10 rounded-md px-3 py-2 text-xs">
      <p className="text-[#A1A1AA] mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-mono tabular-nums">
          {p.name}: {typeof p.value === "number" ? (p.value * 100).toFixed(1) + "%" : p.value}
        </p>
      ))}
    </div>
  );
};

export function WinProbabilityChart({ data = [], team1 = "Team A", team2 = "Team B" }) {
  const chartData = data.map((d, i) => ({
    idx: i + 1,
    team1: d.ensemble || 0.5,
    team2: 1 - (d.ensemble || 0.5),
  }));

  if (chartData.length === 0) {
    chartData.push({ idx: 0, team1: 0.5, team2: 0.5 });
  }

  return (
    <div data-testid="win-probability-chart" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Win Probability
      </h4>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#007AFF" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#007AFF" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FF3B30" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#FF3B30" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <XAxis dataKey="idx" hide />
          <YAxis domain={[0, 1]} hide />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="team1" name={team1} stroke="#007AFF" fill="url(#blueGrad)" strokeWidth={2} />
          <Area type="monotone" dataKey="team2" name={team2} stroke="#FF3B30" fill="url(#redGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
      <div className="flex justify-between mt-2 text-xs font-mono">
        <span className="text-[#007AFF]">{team1}: {chartData.length > 0 ? (chartData[chartData.length - 1].team1 * 100).toFixed(1) : 50}%</span>
        <span className="text-[#FF3B30]">{team2}: {chartData.length > 0 ? (chartData[chartData.length - 1].team2 * 100).toFixed(1) : 50}%</span>
      </div>
    </div>
  );
}

export function ManhattanChart({ data = [] }) {
  return (
    <div data-testid="manhattan-chart" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Manhattan
      </h4>
      {data.length > 0 ? (
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data}>
            <XAxis dataKey="over" tick={{ fill: "#71717A", fontSize: 10 }} />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="runs" fill="#007AFF" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-[160px] flex items-center justify-center text-sm text-[#71717A]">
          No over-by-over data yet
        </div>
      )}
    </div>
  );
}

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
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Algorithm Radar
      </h4>
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(255,255,255,0.1)" />
          <PolarAngleAxis dataKey="algo" tick={{ fill: "#A1A1AA", fontSize: 10 }} />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <Radar name="Win%" dataKey="value" stroke="#007AFF" fill="#007AFF" fillOpacity={0.3} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
