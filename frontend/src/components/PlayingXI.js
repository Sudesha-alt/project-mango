import { User, Shield, Star } from "@phosphor-icons/react";

export default function PlayingXI({ squad = [], team1 = "", team2 = "" }) {
  if (!squad || !Array.isArray(squad) || squad.length === 0) {
    return (
      <div data-testid="playing-xi" className="bg-[#141414] border border-white/10 rounded-md p-4">
        <h4
          className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
          style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
        >
          Playing XI
        </h4>
        <p className="text-sm text-[#71717A]">Squad data unavailable</p>
      </div>
    );
  }

  return (
    <div data-testid="playing-xi" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-4"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Playing XI
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {squad.slice(0, 2).map((team, idx) => (
          <div key={idx}>
            <p className="text-sm font-bold mb-2 flex items-center gap-1.5">
              <Shield weight="fill" className="w-4 h-4 text-[#007AFF]" />
              {team.teamName || (idx === 0 ? team1 : team2)}
            </p>
            <div className="space-y-1">
              {(team.players || []).slice(0, 11).map((player, pi) => (
                <div
                  key={pi}
                  data-testid={`player-${idx}-${pi}`}
                  className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-[#1E1E1E] transition-colors"
                >
                  <div className="w-6 h-6 rounded-full bg-[#1E1E1E] flex items-center justify-center">
                    <User weight="bold" className="w-3.5 h-3.5 text-[#A1A1AA]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{player.name || "Unknown"}</p>
                  </div>
                  {player.isCaptain && (
                    <span className="text-[9px] font-bold bg-[#EAB308]/20 text-[#EAB308] px-1.5 py-0.5 rounded">C</span>
                  )}
                  {player.isKeeper && (
                    <span className="text-[9px] font-bold bg-[#007AFF]/20 text-[#007AFF] px-1.5 py-0.5 rounded">WK</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
