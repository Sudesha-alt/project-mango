import { useState, useRef, useEffect } from "react";
import {
  Crosshair, Spinner, PaperPlaneTilt, ShieldCheck,
  Warning, XCircle, Clock, TrendUp, CaretDown, CaretUp
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

function WinGauge({ probability }) {
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
        <InfoTooltip text="Win probability from the 6-layer decision engine: features, logistic model, live model, 10K negative-binomial simulations, Platt calibration, and odds comparison." />
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

function SignalBadge({ signal }) {
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

function EdgeMeter({ edge }) {
  if (edge === null || edge === undefined) return null;
  const clamped = Math.max(-15, Math.min(15, edge));
  const pct = ((clamped + 15) / 30) * 100;
  const color = edge > 4 ? "#34C759" : edge > 0 ? "#FFCC00" : "#FF3B30";
  return (
    <div data-testid="edge-meter" className="space-y-1">
      <div className="flex justify-between text-[10px] uppercase tracking-wider font-semibold">
        <span className="text-[#FF3B30]">AVOID</span>
        <span className="text-[#A3A3A3] flex items-center gap-1">EDGE <InfoTooltip text="Edge = your model's probability minus the bookmaker's implied probability. Positive edge means the market is undervaluing this team — a potential value bet." /></span>
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

function OddsComparison({ data }) {
  if (!data) return null;
  return (
    <div data-testid="odds-comparison" className="space-y-2">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-wider font-semibold mb-0.5 flex items-center gap-1">Fair Odds <InfoTooltip text="Decimal odds calculated from the model's calibrated win probability. If the bookmaker offers higher odds, it's a value bet." /></p>
          <p className="text-2xl font-black font-mono tabular-nums text-white" style={{ fontFamily: "'Barlow Condensed'" }}>{data.fair_decimal_odds}</p>
          <p className="text-[10px] text-[#A3A3A3] font-mono">{data.fair_probability}% implied</p>
        </div>
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-wider font-semibold mb-0.5">Market Odds</p>
          <p className="text-2xl font-black font-mono tabular-nums text-white" style={{ fontFamily: "'Barlow Condensed'" }}>{data.market_decimal_odds || "—"}</p>
          {data.normalized_market_probability && <p className="text-[10px] text-[#A3A3A3] font-mono">{data.normalized_market_probability}% normalized</p>}
          {data.overround && <p className="text-[10px] text-[#FFCC00] font-mono">Overround: {data.overround}%</p>}
        </div>
      </div>
    </div>
  );
}

function DriversPanel({ drivers }) {
  if (!drivers || drivers.length === 0) return null;
  return (
    <div data-testid="top-drivers" className="space-y-1.5">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Top Drivers <InfoTooltip text="Key factors driving the current prediction — wickets in hand, run rate comparison, chase difficulty, collapse risk, and momentum patterns." /></p>
      {drivers.map((d, i) => (
        <div key={i} className="flex items-start gap-2 text-xs text-[#A3A3A3]">
          <TrendUp weight="bold" className="w-3.5 h-3.5 text-[#007AFF] flex-shrink-0 mt-0.5" />
          <span>{d}</span>
        </div>
      ))}
    </div>
  );
}

function PlayerImpact({ players }) {
  if (!players || players.length === 0) return null;
  return (
    <div data-testid="player-impact" className="space-y-1.5">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Player Impact <InfoTooltip text="Individual player predictions from the weighted formula: 40% Last-5 avg, 30% venue average, 20% opponent-adjusted, 10% form momentum. Includes a luck biasness variance (+-12%) for realism." /></p>
      <div className="space-y-1">
        {players.map((p, i) => (
          <div key={i} className="flex items-center justify-between py-1 border-b border-[#262626] last:border-0">
            <div className="flex items-center gap-2">
              <span className="text-xs text-white font-medium">{p.name}</span>
              <span className="text-[9px] text-[#737373] font-mono">{p.role?.slice(0, 3).toUpperCase()}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono tabular-nums">
              <span className="text-[#007AFF]">{p.predicted_runs}r</span>
              <span className="text-[#FF3B30]">{p.predicted_wickets}w</span>
              <span className={`${p.confidence >= 70 ? "text-[#34C759]" : p.confidence >= 50 ? "text-[#FFCC00]" : "text-[#737373]"}`}>{p.confidence}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function UncertaintyBand({ band, confidence }) {
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

function ChatBox({ matchId, sendChat, riskTolerance, marketOdds }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", text: q }]);
    setLoading(true);
    const res = await sendChat(matchId, q, {
      riskTolerance,
      marketPctTeam1: marketOdds?.team1 || null,
      marketPctTeam2: marketOdds?.team2 || null,
    });
    if (res) {
      setMessages(prev => [...prev, { role: "ai", text: res.answer, summary: res.consultation_summary }]);
    } else {
      setMessages(prev => [...prev, { role: "ai", text: "Sorry, couldn't process that. Try again." }]);
    }
    setLoading(false);
  };

  return (
    <div data-testid="consultant-chat" className="bg-[#141414] border border-[#262626] rounded-lg flex flex-col h-full min-h-[300px]">
      <div className="px-4 py-3 border-b border-[#262626]">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#A3A3A3]" style={{ fontFamily: "'Barlow Condensed'" }}>Ask the Consultant</p>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[400px]">
        {messages.length === 0 && (
          <div className="text-center py-6">
            <Crosshair weight="duotone" className="w-8 h-8 text-[#007AFF] mx-auto mb-2" />
            <p className="text-xs text-[#737373]">Ask anything about this match.</p>
            <p className="text-[10px] text-[#737373] mt-1">"Should I bet on this?" / "Is it safe to go in now?"</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            {m.role === "user" ? (
              <div className="bg-[#1F1F1F] text-white p-3 rounded-lg max-w-[85%] text-sm" style={{ fontFamily: "'IBM Plex Sans'" }}>{m.text}</div>
            ) : (
              <div className="border-l-2 border-[#007AFF] pl-4 py-2 max-w-[95%]">
                <p className="text-sm text-[#A3A3A3] leading-relaxed" style={{ fontFamily: "'IBM Plex Sans'" }}>{m.text}</p>
                {m.summary && (
                  <div className="mt-2 flex gap-2 flex-wrap">
                    <span className="text-[9px] font-mono bg-[#1F1F1F] px-1.5 py-0.5 rounded text-[#007AFF]">{m.summary.win_probability}% win</span>
                    <span className="text-[9px] font-mono bg-[#1F1F1F] px-1.5 py-0.5 rounded text-[#A3A3A3]">{m.summary.value_signal}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-[#737373]">
            <Spinner className="w-4 h-4 animate-spin" /> Analyzing...
          </div>
        )}
        <div ref={scrollRef} />
      </div>
      <div className="px-4 py-3 border-t border-[#262626]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Should I bet now? Is this a good opportunity?"
            data-testid="chat-input"
            className="flex-1 bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2 text-sm text-white placeholder:text-[#737373] focus:border-[#007AFF] focus:outline-none"
            style={{ fontFamily: "'IBM Plex Sans'" }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            data-testid="chat-submit-button"
            className="bg-[#007AFF] text-white px-4 py-2 rounded-md hover:bg-blue-600 transition-colors disabled:opacity-40"
          >
            <PaperPlaneTilt weight="fill" className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function SimulationSummary({ sim, team1, team2 }) {
  if (!sim) return null;
  return (
    <div data-testid="simulation-summary" className="space-y-2">
      <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">{sim.simulations?.toLocaleString()} Simulations (Neg. Binomial) <InfoTooltip text="10,000 match simulations using Negative Binomial distribution for each innings. Right-skewed like real cricket scores. Chase pressure adjusts the chasing team's expected score." /></p>
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: team1, data: sim.team1_scores, prob: sim.team1_win_prob, color: "#007AFF" },
          { label: team2, data: sim.team2_scores, prob: sim.team2_win_prob, color: "#FF3B30" },
        ].map(({ label, data, prob, color }) => (
          <div key={label} className="bg-[#0A0A0A] border border-[#262626] rounded-md p-2.5">
            <p className="text-[10px] text-[#737373] mb-1">{label}</p>
            <p className="text-lg font-black font-mono" style={{ color, fontFamily: "'Barlow Condensed'" }}>{(prob * 100).toFixed(1)}%</p>
            <p className="text-[9px] text-[#737373] font-mono">Mean: {data?.mean} | Med: {data?.median}</p>
            <p className="text-[9px] text-[#737373] font-mono">P10–P90: {data?.p10}–{data?.p90}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonViewer({ data }) {
  const [open, setOpen] = useState(false);
  return (
    <div data-testid="json-viewer" className="border border-[#262626] rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-2 bg-[#141414] text-[10px] text-[#737373] uppercase tracking-wider font-semibold hover:text-white transition-colors">
        <span>Raw JSON Output</span>
        {open ? <CaretUp weight="bold" className="w-3.5 h-3.5" /> : <CaretDown weight="bold" className="w-3.5 h-3.5" />}
      </button>
      {open && (
        <pre className="p-4 bg-[#0A0A0A] text-[10px] text-[#A3A3A3] font-mono overflow-x-auto max-h-[300px] overflow-y-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function ConsultantDashboard({ matchId, team1, team2, fetchConsultation, sendChat }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [risk, setRisk] = useState("balanced");
  const [marketOdds, setMarketOdds] = useState({ team1: "", team2: "" });

  const handleConsult = async () => {
    setLoading(true);
    const opts = {
      riskTolerance: risk,
      marketPctTeam1: marketOdds.team1 ? parseFloat(marketOdds.team1) : null,
      marketPctTeam2: marketOdds.team2 ? parseFloat(marketOdds.team2) : null,
    };
    const res = await fetchConsultation(matchId, opts);
    if (res && !res.error) setData(res);
    setLoading(false);
  };

  const riskOptions = [
    { key: "safe", label: "Play Safe" },
    { key: "balanced", label: "Balanced" },
    { key: "aggressive", label: "Risk Taker" },
  ];

  return (
    <div data-testid="consultant-dashboard" className="space-y-4">
      {/* Config Panel */}
      <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-4">
        {/* Risk Tolerance */}
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">Risk Tolerance <InfoTooltip text="Your betting style. 'Play Safe' flags even small edges as risky. 'Balanced' follows model signals. 'Risk Taker' leans into marginal edges." /></p>
          <div className="flex gap-1 bg-[#0A0A0A] rounded-md p-1" data-testid="risk-tolerance-toggle">
            {riskOptions.map((o) => (
              <button key={o.key} onClick={() => setRisk(o.key)}
                data-testid={`risk-${o.key}`}
                className={`flex-1 py-2 text-xs font-bold uppercase tracking-wider rounded transition-colors ${
                  risk === o.key ? "bg-[#007AFF] text-white" : "text-[#737373] hover:text-white"
                }`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>

        {/* Market Odds — 0-100 probability scale */}
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">Bookmaker Win % (0-100) <InfoTooltip text="Enter the bookmaker's implied win probability for each team on a 0-100 scale. E.g., if odds are 1.80, that's ~56%. The engine compares this to its own probability to find value bets." /></p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] text-[#737373] block mb-0.5">{team1} win %</label>
              <input type="number" step="1" min="0" max="100" placeholder="e.g. 55" value={marketOdds.team1}
                onChange={(e) => setMarketOdds(p => ({ ...p, team1: e.target.value }))}
                data-testid="market-odds-input-team1"
                className="w-full bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none" />
            </div>
            <div>
              <label className="text-[9px] text-[#737373] block mb-0.5">{team2} win %</label>
              <input type="number" step="1" min="0" max="100" placeholder="e.g. 45" value={marketOdds.team2}
                onChange={(e) => setMarketOdds(p => ({ ...p, team2: e.target.value }))}
                data-testid="market-odds-input-team2"
                className="w-full bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none" />
            </div>
          </div>
        </div>

        <button onClick={handleConsult} disabled={loading} data-testid="run-consultation-btn"
          className="w-full flex items-center justify-center gap-2 bg-[#007AFF] text-white py-3 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-blue-600 transition-colors disabled:opacity-50">
          {loading ? <><Spinner className="w-4 h-4 animate-spin" /> Running Analysis...</>
            : <><Crosshair weight="fill" className="w-4 h-4" /> Run Consultation</>}
        </button>
      </div>

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left: Main metrics */}
          <div className="lg:col-span-5 space-y-4">
            {/* Win Gauge + Signal */}
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5">
              <WinGauge probability={data.win_probability} />
              <div className="flex items-center justify-center gap-3 mt-3">
                <SignalBadge signal={data.value_signal} />
              </div>
              <p className="text-center text-xs text-[#A3A3A3] mt-2" style={{ fontFamily: "'IBM Plex Sans'" }}>{data.bet_recommendation}</p>
              <UncertaintyBand band={data.uncertainty_band} confidence={data.confidence} />
            </div>

            {/* Odds Comparison */}
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5">
              <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-3">Odds Comparison</p>
              <OddsComparison data={data.odds_detail} />
              <div className="mt-3">
                <EdgeMeter edge={data.edge_pct} />
              </div>
            </div>

            {/* Simulation */}
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5">
              <SimulationSummary sim={data.simulation} team1={data.team1Short || team1} team2={data.team2Short || team2} />
            </div>
          </div>

          {/* Middle: Drivers + Players */}
          <div className="lg:col-span-4 space-y-4">
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5">
              <DriversPanel drivers={data.top_drivers} />
            </div>
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5">
              <PlayerImpact players={data.player_impact} />
            </div>
            {/* Features */}
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-5 space-y-2">
              <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold flex items-center gap-1">Match State <InfoTooltip text="Live match features: CRR (Current Run Rate), RRR (Required Run Rate), Pressure Index, Batting Depth remaining, and Collapse Risk probability." /></p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Phase", value: data.features?.phase?.toUpperCase() },
                  { label: "CRR", value: data.features?.current_run_rate },
                  { label: "RRR", value: data.features?.required_run_rate || "—" },
                  { label: "Pressure", value: data.features?.pressure_index },
                  { label: "Depth", value: data.features?.batting_depth_index },
                  { label: "Collapse", value: data.features?.collapse_risk },
                ].map((f, i) => (
                  <div key={i} className="text-center">
                    <p className="text-[9px] text-[#737373] uppercase">{f.label}</p>
                    <p className="text-sm font-mono font-bold text-white">{f.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Chat */}
          <div className="lg:col-span-3">
            <ChatBox matchId={matchId} sendChat={sendChat} riskTolerance={risk} marketOdds={{
              team1: marketOdds.team1 ? parseFloat(marketOdds.team1) : null,
              team2: marketOdds.team2 ? parseFloat(marketOdds.team2) : null,
            }} />
          </div>
        </div>
      )}

      {data && <JsonViewer data={data} />}

      {!data && !loading && (
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-10 text-center">
          <Crosshair weight="duotone" className="w-12 h-12 text-[#007AFF] mx-auto mb-3" />
          <p className="text-sm text-[#A3A3A3]" style={{ fontFamily: "'IBM Plex Sans'" }}>Set your risk tolerance and bookmaker odds, then run the consultation.</p>
          <p className="text-xs text-[#737373] mt-1">The engine will run 10,000 simulations, calibrate probabilities, and give you a clear signal.</p>
        </div>
      )}
    </div>
  );
}
