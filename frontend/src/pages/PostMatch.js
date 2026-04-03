import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useMatchData } from "@/hooks/useMatchData";
import { Trophy, MapPin } from "@phosphor-icons/react";

export default function PostMatch() {
  const { matchId } = useParams();
  const { getTeamSquad } = useMatchData();
  const [matchInfo, setMatchInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/matches/${matchId}/state`);
        const data = await res.json();
        setMatchInfo(data.info || data);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    if (matchId) load();
  }, [matchId]);

  const team1 = matchInfo?.team1 || "Team A";
  const team2 = matchInfo?.team2 || "Team B";
  const t1Short = matchInfo?.team1Short || team1.slice(0, 3).toUpperCase();
  const t2Short = matchInfo?.team2Short || team2.slice(0, 3).toUpperCase();

  return (
    <div data-testid="post-match-page" className="max-w-[1440px] mx-auto px-4 lg:px-6 py-6">
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#007AFF] mb-1">Post-Match</p>
            <h2 className="text-2xl sm:text-3xl font-bold uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed', sans-serif" }} data-testid="postmatch-title">
              {t1Short} vs {t2Short}
            </h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-[#141414] border border-white/10 rounded-md p-6 text-center" data-testid="result-card">
              <Trophy weight="fill" className="w-10 h-10 text-[#EAB308] mx-auto mb-3" />
              <p className="text-sm text-[#A1A1AA] mb-2">Match Result</p>
              {matchInfo?.winner ? (
                <p className="text-xl font-bold text-[#22C55E]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{matchInfo.winner} Won</p>
              ) : (
                <p className="text-lg font-bold" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>{matchInfo?.status || "Completed"}</p>
              )}
              {matchInfo?.score && <p className="text-xs font-mono text-[#A1A1AA] mt-2 tabular-nums">{matchInfo.score}</p>}
              {matchInfo?.manOfMatch && <p className="text-xs text-[#EAB308] mt-2">Man of the Match: {matchInfo.manOfMatch}</p>}
            </div>

            <div className="bg-[#141414] border border-white/10 rounded-md p-4">
              <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Match Details</h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-[#71717A]">Match #</span><span>{matchInfo?.match_number || "—"}</span></div>
                <div className="flex justify-between"><span className="text-[#71717A]">Venue</span><span className="text-right max-w-[200px] truncate">{matchInfo?.venue || "—"}</span></div>
                <div className="flex justify-between"><span className="text-[#71717A]">Date</span><span>{matchInfo?.dateTimeGMT ? new Date(matchInfo.dateTimeGMT).toLocaleDateString() : "—"}</span></div>
                <div className="flex justify-between"><span className="text-[#71717A]">Series</span><span>{matchInfo?.series || "IPL 2026"}</span></div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
