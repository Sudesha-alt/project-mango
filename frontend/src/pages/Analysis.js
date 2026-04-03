import { useState, useEffect } from "react";
import { useMatchData } from "@/hooks/useMatchData";
import AlgorithmPanel from "@/components/AlgorithmPanel";
import OddsPanel from "@/components/OddsPanel";
import { WinProbabilityChart, AlgorithmRadarChart } from "@/components/Charts";
import { ChartLine, Lightning, Broadcast } from "@phosphor-icons/react";

export default function Analysis() {
  const { liveMatches, fetchLiveMatches } = useMatchData();
  const [selectedMatch, setSelectedMatch] = useState(null);

  useEffect(() => {
    fetchLiveMatches();
  }, [fetchLiveMatches]);

  useEffect(() => {
    if (liveMatches.length > 0 && !selectedMatch) {
      const live = liveMatches.find((m) => m.isLive);
      setSelectedMatch(live || liveMatches[0]);
    }
  }, [liveMatches, selectedMatch]);

  const probs = selectedMatch?.probabilities || {};
  const odds = selectedMatch?.odds || {};

  return (
    <div data-testid="analysis-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-6">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-1">
          <ChartLine weight="bold" className="inline w-3.5 h-3.5 mr-1" />
          Analytics Dashboard
        </p>
        <h2
          className="text-2xl sm:text-3xl font-bold uppercase tracking-tight"
          style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
        >
          Match Analysis
        </h2>
      </div>

      {/* Match Selector */}
      {liveMatches.length > 0 && (
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2" data-testid="analysis-match-selector">
          {liveMatches.slice(0, 10).map((m, i) => (
            <button
              key={m.matchId || i}
              onClick={() => setSelectedMatch(m)}
              data-testid={`analysis-match-${i}`}
              className={`flex-shrink-0 px-3 py-2 rounded-md text-xs font-bold border transition-colors ${
                selectedMatch?.matchId === m.matchId
                  ? "bg-[#007AFF] border-[#007AFF] text-white"
                  : "bg-[#141414] border-white/10 text-[#A1A1AA] hover:border-[#007AFF]/40"
              }`}
            >
              {m.team1Short || "?"} vs {m.team2Short || "?"}
              {m.isLive && <Broadcast weight="fill" className="inline ml-1 w-3 h-3 text-[#FF3B30]" />}
            </button>
          ))}
        </div>
      )}

      {selectedMatch ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-8 space-y-4">
            <WinProbabilityChart
              data={[probs]}
              team1={selectedMatch.team1Short || "T1"}
              team2={selectedMatch.team2Short || "T2"}
            />
            <AlgorithmRadarChart probabilities={probs} />

            {/* Summary Card */}
            <div className="bg-[#141414] border border-white/10 rounded-md p-4" data-testid="match-summary">
              <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                Match Summary
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                  <p className="text-[10px] text-[#71717A]">Score</p>
                  <p className="text-sm font-mono font-bold tabular-nums truncate">{selectedMatch.score || "--"}</p>
                </div>
                <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                  <p className="text-[10px] text-[#71717A]">Venue</p>
                  <p className="text-sm truncate">{selectedMatch.venue || "--"}</p>
                </div>
                <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                  <p className="text-[10px] text-[#71717A]">Type</p>
                  <p className="text-sm">{selectedMatch.matchType || "--"}</p>
                </div>
                <div className="bg-[#1E1E1E] rounded-md p-3 text-center">
                  <p className="text-[10px] text-[#71717A]">Status</p>
                  <p className="text-sm truncate">{selectedMatch.isLive ? "LIVE" : selectedMatch.matchEnded ? "Completed" : "Upcoming"}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 space-y-4">
            <AlgorithmPanel
              probabilities={probs}
              team1={selectedMatch.team1Short || "T1"}
              team2={selectedMatch.team2Short || "T2"}
            />
            <OddsPanel
              odds={odds}
              history={[]}
              team1={selectedMatch.team1Short || "T1"}
              team2={selectedMatch.team2Short || "T2"}
            />
          </div>
        </div>
      ) : (
        <div className="text-center py-16">
          <Lightning weight="duotone" className="w-12 h-12 text-[#333] mx-auto mb-4" />
          <p className="text-sm text-[#71717A]">No matches available for analysis</p>
        </div>
      )}
    </div>
  );
}
