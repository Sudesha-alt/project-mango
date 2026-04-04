import { useState } from "react";
import { Crosshair, Spinner, CaretDown, CaretUp } from "@phosphor-icons/react";
import InfoTooltip from "./InfoTooltip";
import ChatBox from "./ChatBox";
import {
  WinGauge, SignalBadge, EdgeMeter, EdgeReasons,
  DriversPanel, PlayerImpact, UncertaintyBand, SimulationSummary,
} from "./ConsultantWidgets";

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
  const [oddsTrend, setOddsTrend] = useState({ increasing: "", decreasing: "" });

  const handleConsult = async () => {
    setLoading(true);
    const opts = {
      riskTolerance: risk,
      marketPctTeam1: marketOdds.team1 ? parseFloat(marketOdds.team1) : null,
      marketPctTeam2: marketOdds.team2 ? parseFloat(marketOdds.team2) : null,
      oddsTrendIncreasing: oddsTrend.increasing || null,
      oddsTrendDecreasing: oddsTrend.decreasing || null,
    };
    const res = await fetchConsultation(matchId, opts);
    if (res && !res.error) setData(res);
    setLoading(false);
  };

  const handleTrendChange = (direction, team) => {
    if (direction === "increasing") {
      setOddsTrend({ increasing: team, decreasing: team === team1 ? team2 : team1 });
    } else {
      setOddsTrend({ decreasing: team, increasing: team === team1 ? team2 : team1 });
    }
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
        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">Risk Tolerance <InfoTooltip text="Your betting style." /></p>
          <div className="flex gap-1 bg-[#0A0A0A] rounded-md p-1" data-testid="risk-tolerance-toggle">
            {riskOptions.map((o) => (
              <button key={o.key} onClick={() => setRisk(o.key)} data-testid={`risk-${o.key}`}
                className={`flex-1 py-2 text-xs font-bold uppercase tracking-wider rounded transition-colors ${
                  risk === o.key ? "bg-[#007AFF] text-white" : "text-[#737373] hover:text-white"
                }`}>{o.label}</button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">Bookmaker Win % (0-100) <InfoTooltip text="Enter the bookmaker's implied win probability." /></p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] text-[#737373] block mb-0.5">{team1} win %</label>
              <input type="number" step="1" min="0" max="100" placeholder="e.g. 55" value={marketOdds.team1}
                onChange={(e) => setMarketOdds(p => ({ ...p, team1: e.target.value }))} data-testid="market-odds-input-team1"
                className="w-full bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none" />
            </div>
            <div>
              <label className="text-[9px] text-[#737373] block mb-0.5">{team2} win %</label>
              <input type="number" step="1" min="0" max="100" placeholder="e.g. 45" value={marketOdds.team2}
                onChange={(e) => setMarketOdds(p => ({ ...p, team2: e.target.value }))} data-testid="market-odds-input-team2"
                className="w-full bg-[#0A0A0A] border border-[#262626] rounded-md px-3 py-2 text-xs font-mono text-white placeholder:text-[#333] focus:border-[#007AFF] focus:outline-none" />
            </div>
          </div>
        </div>

        <div>
          <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">
            Market Momentum <InfoTooltip text="Which team's odds are rising/falling?" />
          </p>
          <div className="grid grid-cols-2 gap-2" data-testid="odds-trend-selector">
            <div>
              <label className="text-[9px] text-[#34C759] block mb-1 font-bold uppercase tracking-wider flex items-center gap-1">
                <CaretUp weight="bold" className="w-2.5 h-2.5" /> Odds Rising
              </label>
              <div className="flex gap-1 bg-[#0A0A0A] rounded-md p-0.5">
                {[team1, team2].map(t => (
                  <button key={t} onClick={() => handleTrendChange("increasing", t)} data-testid={`trend-increasing-${t}`}
                    className={`flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded transition-colors ${
                      oddsTrend.increasing === t ? "bg-[#34C759]/20 text-[#34C759] border border-[#34C759]/40" : "text-[#525252] hover:text-[#737373]"
                    }`}>{t}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-[9px] text-[#FF3B30] block mb-1 font-bold uppercase tracking-wider flex items-center gap-1">
                <CaretDown weight="bold" className="w-2.5 h-2.5" /> Odds Falling
              </label>
              <div className="flex gap-1 bg-[#0A0A0A] rounded-md p-0.5">
                {[team1, team2].map(t => (
                  <button key={t} onClick={() => handleTrendChange("decreasing", t)} data-testid={`trend-decreasing-${t}`}
                    className={`flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded transition-colors ${
                      oddsTrend.decreasing === t ? "bg-[#FF3B30]/20 text-[#FF3B30] border border-[#FF3B30]/40" : "text-[#525252] hover:text-[#737373]"
                    }`}>{t}</button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <button onClick={handleConsult} disabled={loading} data-testid="run-consultation-btn"
          className="w-full flex items-center justify-center gap-2 bg-[#007AFF] text-white py-3 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-blue-600 transition-colors disabled:opacity-50">
          {loading ? <><Spinner className="w-4 h-4 animate-spin" /> Running 50K Simulations...</>
            : <><Crosshair weight="fill" className="w-4 h-4" /> Run Consultation</>}
        </button>
      </div>

      {data && (
        <div className="space-y-3">
          {data.verdict && (
            <div className={`rounded-lg p-4 border ${
              data.verdict.strength === "DOMINANT" ? "bg-[#34C759]/10 border-[#34C759]/30" :
              data.verdict.strength === "STRONG" ? "bg-[#007AFF]/10 border-[#007AFF]/30" :
              data.verdict.strength === "SLIGHT" ? "bg-[#FFCC00]/10 border-[#FFCC00]/30" :
              "bg-[#262626]/50 border-[#525252]/30"
            }`} data-testid="verdict-section">
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <span className={`text-2xl font-black tracking-tight ${
                  data.verdict.strength === "DOMINANT" ? "text-[#34C759]" :
                  data.verdict.strength === "STRONG" ? "text-[#007AFF]" :
                  data.verdict.strength === "SLIGHT" ? "text-[#FFCC00]" : "text-[#A3A3A3]"
                }`} style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                  {data.verdict.winner_short} WINS
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-widest bg-white/5 text-[#A3A3A3]">{data.verdict.strength}</span>
                <SignalBadge signal={data.value_signal} />
              </div>
              <p className="text-xs text-[#D4D4D4] leading-relaxed">{data.verdict.text}</p>
              <p className="text-[10px] text-[#737373] mt-1.5 font-mono">{data.bet_recommendation}</p>
              <div className="mt-2"><EdgeReasons reasons={data.edge_reasons} signal={data.value_signal} /></div>
            </div>
          )}

          <div className="bg-[#141414] border border-[#262626] rounded-lg p-4">
            <WinGauge probability={data.win_probability} />
            <UncertaintyBand band={data.uncertainty_band} confidence={data.confidence} />
            <div className="mt-3"><EdgeMeter edge={data.edge_pct} /></div>
          </div>

          <div className="bg-[#141414] border border-[#262626] rounded-lg p-4">
            <SimulationSummary sim={data.simulation} team1={data.team1Short || team1} team2={data.team2Short || team2} />
          </div>

          <div className="bg-[#141414] border border-[#262626] rounded-lg p-4">
            <DriversPanel drivers={data.top_drivers} />
          </div>

          {data.betting_scenarios?.length > 0 && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-4" data-testid="betting-scenarios">
              <p className="text-[10px] text-[#737373] uppercase tracking-[0.2em] font-semibold mb-2 flex items-center gap-1">
                Betting Scenarios <InfoTooltip text="AI-generated betting windows." />
              </p>
              <div className="space-y-2">
                {data.betting_scenarios.map((sc, i) => (
                  <div key={i} className={`p-2.5 rounded-md border ${
                    sc.confidence === "HIGH" ? "border-[#34C759]/30 bg-[#34C759]/5" : "border-[#FFCC00]/30 bg-[#FFCC00]/5"
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-white">{sc.title}</span>
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        sc.confidence === "HIGH" ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FFCC00]/20 text-[#FFCC00]"
                      }`}>{sc.confidence}</span>
                    </div>
                    <p className="text-[10px] text-[#A3A3A3] leading-relaxed">{sc.description}</p>
                    <p className="text-[8px] text-[#525252] font-mono mt-1">{sc.timing}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.player_impact?.length > 0 && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-4">
              <PlayerImpact players={data.player_impact} />
            </div>
          )}

          <ChatBox matchId={matchId} sendChat={sendChat} riskTolerance={risk} marketOdds={{
            team1: marketOdds.team1 ? parseFloat(marketOdds.team1) : null,
            team2: marketOdds.team2 ? parseFloat(marketOdds.team2) : null,
          }} />
        </div>
      )}

      {data && <JsonViewer data={data} />}

      {!data && !loading && (
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-10 text-center">
          <Crosshair weight="duotone" className="w-12 h-12 text-[#007AFF] mx-auto mb-3" />
          <p className="text-sm text-[#A3A3A3]" style={{ fontFamily: "'IBM Plex Sans'" }}>Set your risk tolerance and bookmaker odds, then run the consultation.</p>
          <p className="text-xs text-[#737373] mt-1">The engine will run 50,000 simulations, calibrate probabilities, and give you a clear winner.</p>
        </div>
      )}
    </div>
  );
}
