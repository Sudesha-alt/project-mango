import { useState, useEffect } from "react";
import { useMatchData } from "@/hooks/useMatchData";
import { ChartLine, Lightning, UsersThree, Spinner } from "@phosphor-icons/react";

export default function Analysis() {
  const { schedule, loading, loadSchedule, loadSquads, squads } = useMatchData();
  const [squadsLoading, setSquadsLoading] = useState(false);

  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);

  const handleLoadSquads = async () => {
    setSquadsLoading(true);
    await loadSquads();
    setSquadsLoading(false);
  };

  return (
    <div data-testid="analysis-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-6">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-1">
          <ChartLine weight="bold" className="inline w-3.5 h-3.5 mr-1" />Analytics
        </p>
        <h2 className="text-2xl sm:text-3xl font-bold uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
          IPL 2026 Overview
        </h2>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-[#141414] border border-white/10 rounded-md p-4 text-center">
          <p className="text-2xl font-bold font-mono tabular-nums text-[#007AFF]">{schedule.total || 0}</p>
          <p className="text-[10px] text-[#71717A] uppercase tracking-wider">Total Matches</p>
        </div>
        <div className="bg-[#141414] border border-white/10 rounded-md p-4 text-center">
          <p className="text-2xl font-bold font-mono tabular-nums text-[#22C55E]">{schedule.completed?.length || 0}</p>
          <p className="text-[10px] text-[#71717A] uppercase tracking-wider">Completed</p>
        </div>
        <div className="bg-[#141414] border border-white/10 rounded-md p-4 text-center">
          <p className="text-2xl font-bold font-mono tabular-nums text-[#EAB308]">{schedule.upcoming?.length || 0}</p>
          <p className="text-[10px] text-[#71717A] uppercase tracking-wider">Upcoming</p>
        </div>
        <div className="bg-[#141414] border border-white/10 rounded-md p-4 text-center">
          <p className="text-2xl font-bold font-mono tabular-nums text-[#FF3B30]">{schedule.live?.length || 0}</p>
          <p className="text-[10px] text-[#71717A] uppercase tracking-wider">Live</p>
        </div>
      </div>

      {/* Team Squads */}
      <div className="bg-[#141414] border border-white/10 rounded-md p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
            <UsersThree weight="bold" className="inline w-4 h-4 mr-1" /> Team Squads
          </h4>
          <button onClick={handleLoadSquads} disabled={squadsLoading} data-testid="load-squads-btn"
            className="text-[10px] font-bold uppercase px-3 py-1.5 rounded bg-[#007AFF]/20 text-[#007AFF] hover:bg-[#007AFF]/30 transition-colors disabled:opacity-50">
            {squadsLoading ? <><Spinner className="inline w-3 h-3 animate-spin mr-1" />Loading...</> : squads.length > 0 ? "Refresh Squads" : "Load All Squads"}
          </button>
        </div>
        {squads.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {squads.map((s, i) => (
              <div key={i} className="bg-[#1E1E1E] rounded-md p-3 text-center hover:bg-[#252525] transition-colors">
                <p className="text-sm font-bold" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{s.teamShort}</p>
                <p className="text-[10px] text-[#71717A] truncate">{s.teamName}</p>
                <p className="text-[10px] text-[#007AFF] mt-1">C: {s.captain || "TBA"}</p>
                <p className="text-[10px] text-[#A1A1AA]">{s.players?.length || 0} players</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[#71717A]">Click "Load All Squads" to fetch team data via GPT.</p>
        )}
      </div>

      {/* Completed Matches Summary */}
      {schedule.completed?.length > 0 && (
        <div className="bg-[#141414] border border-white/10 rounded-md p-4">
          <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
            Recent Results
          </h4>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {schedule.completed.slice(-20).reverse().map((m, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 bg-[#1E1E1E] rounded-md">
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-[#71717A] font-mono">#{m.match_number}</span>
                  <span className="text-xs font-bold">{m.team1Short} vs {m.team2Short}</span>
                </div>
                <div className="text-right">
                  {m.winner && <p className="text-xs text-[#22C55E] font-medium">{m.winner} won</p>}
                  {m.manOfMatch && <p className="text-[10px] text-[#EAB308]">MoM: {m.manOfMatch}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!schedule.loaded && (
        <div className="text-center py-16">
          <Lightning weight="duotone" className="w-12 h-12 text-[#333] mx-auto mb-4" />
          <p className="text-sm text-[#71717A]">Load the IPL 2026 schedule first from the home page.</p>
        </div>
      )}
    </div>
  );
}
