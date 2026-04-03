import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from "recharts";
import { Lightning, TrendUp, Warning, ShieldCheck, ArrowsClockwise, Spinner, Target, ChartBar } from "@phosphor-icons/react";

const SEVERITY_STYLES = {
  high: "bg-[#FF3B30]/10 border-[#FF3B30]/30 text-[#FF3B30]",
  medium: "bg-amber-500/10 border-amber-500/30 text-amber-400",
  low: "bg-[#007AFF]/10 border-[#007AFF]/30 text-[#007AFF]",
};

const ALERT_ICONS = {
  wicket: Warning,
  boundary: TrendUp,
  rate: Lightning,
  pressure: Warning,
  value_bet: ShieldCheck,
};

function PoissonChart({ data, label }) {
  if (!data || data.length === 0) return null;
  const maxP = Math.max(...data.map(d => d.probability));
  return (
    <div data-testid="poisson-chart">
      <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{label}</p>
      <div style={{ height: 120 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey={data[0]?.runs !== undefined ? "runs" : "wickets"} tick={{ fill: "#71717A", fontSize: 8 }} interval={Math.max(Math.floor(data.length / 8), 1)} />
            <YAxis hide />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-[#0A0A0A] border border-white/20 rounded px-2 py-1 text-[10px]">
                    <span className="text-white font-mono">{d.runs !== undefined ? `${d.runs} runs` : `${d.wickets} wkts`}</span>
                    <span className="text-[#A1A1AA] ml-2">{(d.probability * 100).toFixed(1)}%</span>
                  </div>
                );
              }}
            />
            <Bar dataKey="probability" radius={[2, 2, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.probability === maxP ? "#007AFF" : "#333"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PlayerTable({ players }) {
  if (!players || players.length === 0) return null;
  return (
    <div data-testid="player-prediction-table" className="overflow-x-auto">
      <table className="w-full text-[10px]">
        <thead>
          <tr className="border-b border-white/10 text-[#71717A] uppercase tracking-wider">
            <th className="text-left py-2 pr-2">Player</th>
            <th className="text-right py-2 px-1">Pred Runs</th>
            <th className="text-right py-2 px-1">Pred Wkts</th>
            <th className="text-right py-2 px-1">Conf%</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-1.5 pr-2">
                <span className="text-white font-medium">{p.name}</span>
                <span className="text-[#71717A] ml-1.5 text-[9px]">{p.role?.slice(0, 3).toUpperCase()}</span>
              </td>
              <td className="text-right py-1.5 px-1 font-mono tabular-nums text-[#007AFF]">{p.predicted_runs}</td>
              <td className="text-right py-1.5 px-1 font-mono tabular-nums text-[#FF3B30]">{p.predicted_wickets}</td>
              <td className="text-right py-1.5 px-1">
                <span className={`font-mono tabular-nums ${p.confidence >= 70 ? "text-[#22C55E]" : p.confidence >= 50 ? "text-amber-400" : "text-[#71717A]"}`}>
                  {p.confidence}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OddsEngine({ odds, team1, team2 }) {
  if (!odds) return null;
  return (
    <div data-testid="odds-engine" className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        {[
          { key: "team1", label: team1, data: odds.team1 },
          { key: "team2", label: team2, data: odds.team2 },
        ].map(({ key, label, data }) => (
          <div key={key} className="bg-[#1E1E1E] rounded-md p-3 space-y-1.5">
            <p className="text-[10px] text-[#71717A] uppercase tracking-wider">{label}</p>
            <p className="text-lg font-bold font-mono tabular-nums text-white">{data?.house_odds}</p>
            <div className="space-y-0.5">
              <div className="flex justify-between text-[9px]">
                <span className="text-[#71717A]">True Prob</span>
                <span className="text-[#A1A1AA] font-mono">{data?.true_probability}%</span>
              </div>
              <div className="flex justify-between text-[9px]">
                <span className="text-[#71717A]">True Odds</span>
                <span className="text-[#A1A1AA] font-mono">{data?.true_odds}</span>
              </div>
              <div className="flex justify-between text-[9px]">
                <span className="text-[#71717A]">House Odds</span>
                <span className="text-white font-mono font-bold">{data?.house_odds}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between text-[9px] px-1">
        <span className="text-[#71717A]">House Edge: <span className="text-amber-400 font-mono">{odds.house_edge_pct}%</span></span>
        <span className="text-[#71717A]">Overround: <span className="text-amber-400 font-mono">{odds.overround}%</span></span>
      </div>
    </div>
  );
}

function AlertsPanel({ alerts, valueBets }) {
  const allAlerts = [...(alerts || []), ...(valueBets || []).map(vb => ({
    type: vb.type,
    severity: vb.type === "HIGH_VALUE" ? "high" : "medium",
    message: `${vb.message} on ${vb.team} — ${vb.edge_pct}% edge`,
    icon: "value_bet",
  }))];

  if (allAlerts.length === 0) {
    return (
      <div className="text-center py-4 text-[10px] text-[#71717A]">
        No active alerts
      </div>
    );
  }

  return (
    <div data-testid="alerts-panel" className="space-y-1.5">
      {allAlerts.map((alert, i) => {
        const Icon = ALERT_ICONS[alert.icon] || Lightning;
        return (
          <div key={i} className={`flex items-start gap-2 rounded-md border p-2.5 ${SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.low}`}>
            <Icon weight="fill" className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider">{alert.type?.replace(/_/g, " ")}</p>
              <p className="text-[10px] opacity-80">{alert.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MonteCarloSummary({ mc, team1, team2 }) {
  if (!mc) return null;
  return (
    <div data-testid="monte-carlo-summary" className="space-y-2">
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-[#71717A]">Simulations</span>
        <span className="text-white font-mono font-bold">{mc.simulations?.toLocaleString()}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: team1, prob: mc.team1_win_prob, avg: mc.team1_avg_score, range: mc.team1_score_range, color: "#007AFF" },
          { label: team2, prob: mc.team2_win_prob, avg: mc.team2_avg_score, range: mc.team2_score_range, color: "#FF3B30" },
        ].map(({ label, prob, avg, range, color }) => (
          <div key={label} className="bg-[#1E1E1E] rounded-md p-2.5">
            <p className="text-[10px] text-[#71717A] mb-1">{label}</p>
            <p className="text-xl font-bold font-mono tabular-nums" style={{ color }}>{(prob * 100).toFixed(1)}%</p>
            <p className="text-[9px] text-[#71717A] font-mono">Avg: {avg} | Med: {range?.p50}</p>
            <p className="text-[9px] text-[#71717A] font-mono">Range: {range?.p10}–{range?.p90}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ContextBadge({ context }) {
  if (!context) return null;
  const phaseColors = { powerplay: "#007AFF", middle: "#71717A", death: "#FF3B30" };
  const pressureColors = { low: "#22C55E", medium: "#EAB308", high: "#FF3B30", critical: "#FF3B30" };
  return (
    <div data-testid="match-context" className="flex flex-wrap gap-1.5">
      <span className="text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider"
        style={{ borderColor: phaseColors[context.phase] || "#71717A", color: phaseColors[context.phase] || "#71717A" }}>
        {context.phase}
      </span>
      <span className="text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider"
        style={{ borderColor: pressureColors[context.pressure] || "#71717A", color: pressureColors[context.pressure] || "#71717A" }}>
        Pressure: {context.pressure}
      </span>
      {context.wickets_pressure !== "normal" && (
        <span className="text-[9px] px-2 py-0.5 rounded-full border border-[#FF3B30] text-[#FF3B30] font-bold uppercase tracking-wider">
          Wkts: {context.wickets_pressure}
        </span>
      )}
      {context.required_run_rate && (
        <span className="text-[9px] px-2 py-0.5 rounded-full border border-amber-400 text-amber-400 font-mono">
          RRR: {context.required_run_rate}
        </span>
      )}
    </div>
  );
}

export default function BetaPrediction({ matchId, team1, team2, fetchBetaPrediction }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [marketOdds, setMarketOdds] = useState({ team1: "", team2: "" });
  const [activeSection, setActiveSection] = useState("overview");

  const handlePredict = async () => {
    setLoading(true);
    const odds = {};
    if (marketOdds.team1 && parseFloat(marketOdds.team1) > 1) odds.team1 = parseFloat(marketOdds.team1);
    if (marketOdds.team2 && parseFloat(marketOdds.team2) > 1) odds.team2 = parseFloat(marketOdds.team2);
    const result = await fetchBetaPrediction(matchId, odds);
    if (result && !result.error) setData(result);
    setLoading(false);
  };

  const sections = [
    { key: "overview", label: "Overview" },
    { key: "players", label: "Players" },
    { key: "poisson", label: "Poisson" },
    { key: "alerts", label: "Alerts" },
  ];

  const t1 = data?.team1Short || team1;
  const t2 = data?.team2Short || team2;

  return (
    <div data-testid="beta-prediction" className="space-y-3">
      {/* Market odds input */}
      <div className="bg-[#141414] border border-white/10 rounded-md p-3">
        <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-2">Market Odds (optional — for value bet detection)</p>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div>
            <label className="text-[9px] text-[#71717A] block mb-0.5">{team1} Odds</label>
            <input
              type="number" step="0.01" min="1.01" placeholder="e.g. 1.85"
              value={marketOdds.team1}
              onChange={(e) => setMarketOdds(prev => ({ ...prev, team1: e.target.value }))}
              data-testid="market-odds-team1"
              className="w-full bg-[#0A0A0A] border border-white/10 rounded px-2 py-1.5 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none"
            />
          </div>
          <div>
            <label className="text-[9px] text-[#71717A] block mb-0.5">{team2} Odds</label>
            <input
              type="number" step="0.01" min="1.01" placeholder="e.g. 2.10"
              value={marketOdds.team2}
              onChange={(e) => setMarketOdds(prev => ({ ...prev, team2: e.target.value }))}
              data-testid="market-odds-team2"
              className="w-full bg-[#0A0A0A] border border-white/10 rounded px-2 py-1.5 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none"
            />
          </div>
        </div>
        <button
          onClick={handlePredict}
          disabled={loading}
          data-testid="run-beta-predict-btn"
          className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#007AFF] to-[#7F77DD] text-white py-2 rounded-md text-xs font-bold uppercase tracking-wider hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? (
            <><Spinner className="w-4 h-4 animate-spin" /> Running 10K Simulations...</>
          ) : (
            <><Target weight="fill" className="w-4 h-4" /> Run Beta Prediction</>
          )}
        </button>
      </div>

      {data && (
        <>
          {/* Section tabs */}
          <div className="flex gap-1 bg-[#141414] border border-white/10 rounded-md p-1">
            {sections.map((s) => (
              <button key={s.key} onClick={() => setActiveSection(s.key)}
                data-testid={`beta-tab-${s.key}`}
                className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded transition-colors ${
                  activeSection === s.key ? "bg-[#7F77DD] text-white" : "text-[#A1A1AA] hover:text-white"
                }`}>
                {s.label}
                {s.key === "alerts" && data.alerts?.length > 0 && (
                  <span className="ml-1 text-[8px] bg-[#FF3B30] text-white px-1 rounded-full">{data.alerts.length + (data.value_bets?.length || 0)}</span>
                )}
              </button>
            ))}
          </div>

          {/* Context badges */}
          <ContextBadge context={data.match_context} />

          {/* GPT Analysis */}
          {data.gpt_analysis && (
            <div className="bg-[#141414] border border-[#7F77DD]/20 rounded-md p-3">
              <p className="text-[10px] uppercase tracking-wider text-[#7F77DD] mb-1 font-bold">GPT-5.4 Analysis</p>
              <p className="text-xs text-[#A1A1AA]">{data.gpt_analysis.tactical_insight}</p>
              {data.gpt_analysis.pattern_detected && (
                <p className="text-[10px] text-amber-400 mt-1">Pattern: {data.gpt_analysis.pattern_detected}</p>
              )}
              {data.gpt_analysis.recommended_strategy && (
                <p className="text-[10px] text-[#22C55E] mt-1">Strategy: {data.gpt_analysis.recommended_strategy}</p>
              )}
            </div>
          )}

          {/* Sections */}
          {activeSection === "overview" && (
            <div className="space-y-3">
              <div className="bg-[#141414] border border-white/10 rounded-md p-3">
                <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-2 font-bold flex items-center gap-1.5">
                  <ChartBar weight="bold" className="w-3.5 h-3.5" /> Monte Carlo 10K
                </p>
                <MonteCarloSummary mc={data.monte_carlo} team1={t1} team2={t2} />
              </div>
              <div className="bg-[#141414] border border-white/10 rounded-md p-3">
                <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-2 font-bold">Odds Engine (10% House Edge)</p>
                <OddsEngine odds={data.odds} team1={t1} team2={t2} />
              </div>
            </div>
          )}

          {activeSection === "players" && (
            <div className="bg-[#141414] border border-white/10 rounded-md p-3">
              <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-2 font-bold">
                Player Predictions (0.4*Last5 + 0.3*Venue + 0.2*Opp + 0.1*Form)
              </p>
              <PlayerTable players={data.player_predictions} />
            </div>
          )}

          {activeSection === "poisson" && (
            <div className="bg-[#141414] border border-white/10 rounded-md p-3 space-y-3">
              <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-1 font-bold">Poisson Distribution</p>
              {data.poisson?.projected_total && (
                <p className="text-xs text-white font-mono">Projected Total: <span className="text-[#007AFF] font-bold">{data.poisson.projected_total}</span></p>
              )}
              <p className="text-[9px] text-[#71717A]">Expected remaining: <span className="font-mono text-white">{data.poisson.expected_remaining_runs} runs</span>, <span className="font-mono text-white">{data.poisson.expected_remaining_wickets} wickets</span></p>
              <PoissonChart data={data.poisson?.runs_distribution} label="Remaining Runs Probability" />
              <PoissonChart data={data.poisson?.wickets_distribution} label="Remaining Wickets Probability" />
            </div>
          )}

          {activeSection === "alerts" && (
            <div className="bg-[#141414] border border-white/10 rounded-md p-3">
              <p className="text-[10px] uppercase tracking-wider text-[#71717A] mb-2 font-bold">Active Alerts & Value Bets</p>
              <AlertsPanel alerts={data.alerts} valueBets={data.value_bets} />
            </div>
          )}
        </>
      )}

      {!data && !loading && (
        <div className="bg-[#141414] border border-white/10 rounded-md p-6 text-center">
          <Target weight="duotone" className="w-8 h-8 text-[#7F77DD] mx-auto mb-2" />
          <p className="text-xs text-[#A1A1AA] mb-1">Beta Prediction Engine</p>
          <p className="text-[10px] text-[#71717A]">
            Poisson Distribution + 10K Monte Carlo + Player Predictions + Odds Engine + Value Bet Alerts
          </p>
        </div>
      )}
    </div>
  );
}
