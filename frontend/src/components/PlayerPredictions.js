import { useState } from "react";
import { Cricket, TrendUp, Trophy } from "@phosphor-icons/react";

export default function PlayerPredictions({ players = [] }) {
  const [filter, setFilter] = useState("all");

  if (!players.length) {
    return (
      <div data-testid="player-predictions" className="bg-[#141414] border border-white/10 rounded-md p-4">
        <h4
          className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
          style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
        >
          Player Predictions
        </h4>
        <p className="text-sm text-[#71717A]">Loading player predictions...</p>
      </div>
    );
  }

  const filtered = filter === "all" ? players : players.filter((p) => p.team === filter);
  const teams = [...new Set(players.map((p) => p.team))];

  return (
    <div data-testid="player-predictions" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <div className="flex items-center justify-between mb-4">
        <h4
          className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA]"
          style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
        >
          Player Predictions
        </h4>
        <div className="flex gap-1">
          <button
            onClick={() => setFilter("all")}
            data-testid="filter-all"
            className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${
              filter === "all" ? "bg-[#007AFF] text-white" : "bg-[#1E1E1E] text-[#A1A1AA]"
            }`}
          >
            All
          </button>
          {teams.map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              data-testid={`filter-${t}`}
              className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${
                filter === t ? "bg-[#007AFF] text-white" : "bg-[#1E1E1E] text-[#A1A1AA]"
              }`}
            >
              {t.slice(0, 6)}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {filtered.map((p, i) => {
          const bat = p.prediction?.batting || {};
          const bowl = p.prediction?.bowling || {};
          return (
            <div
              key={i}
              data-testid={`player-pred-${i}`}
              className="flex items-center gap-3 py-2 px-3 bg-[#1E1E1E] rounded-md hover:bg-[#252525] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{p.name}</p>
                <p className="text-[10px] text-[#71717A]">{p.team}</p>
              </div>
              <div className="flex gap-3 text-center">
                <div>
                  <p className="text-[10px] text-[#71717A]">Runs</p>
                  <p className="text-xs font-mono font-bold tabular-nums text-[#007AFF]">{bat.predictedRuns || "--"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-[#71717A]">SR</p>
                  <p className="text-xs font-mono font-bold tabular-nums">{bat.strikeRate || "--"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-[#71717A]">Wkts</p>
                  <p className="text-xs font-mono font-bold tabular-nums text-[#FF3B30]">{bowl.predictedWickets || "--"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-[#71717A]">Econ</p>
                  <p className="text-xs font-mono font-bold tabular-nums">{bowl.economy || "--"}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
