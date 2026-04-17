import { useEffect, useMemo, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { UsersThree, Spinner, ArrowLeft, CaretUp, CaretDown } from "@phosphor-icons/react";
import { API_BASE } from "@/lib/apiBase";
import { buildPlayersDirectoryUrl } from "@/lib/playersApi";

const API = API_BASE;

const SORTS = [
  { id: "name", label: "Name" },
  { id: "BatIP", label: "Bat IP" },
  { id: "BowlIP", label: "Bowl IP" },
];

function fmtImpactPt(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(1);
}

export default function Players() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [sortKey, setSortKey] = useState("BatIP");
  const [sortDir, setSortDir] = useState("desc");
  const [squadShorts, setSquadShorts] = useState([]);

  useEffect(() => {
    if (!API) return;
    axios
      .get(`${API}/squads`, { timeout: 20000 })
      .then((r) => {
        const s = (r.data.squads || []).map((x) => x.teamShort).filter(Boolean);
        setSquadShorts([...new Set(s)].sort());
      })
      .catch(() => setSquadShorts([]));
  }, []);

  const load = useCallback(async () => {
    if (!API) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const url = buildPlayersDirectoryUrl({ limit: 5000, skip: 0, teamShort: teamFilter, q: search });
      const res = await axios.get(url, { timeout: 120000 });
      setRows(res.data.players || []);
      setMeta(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Failed to load players");
      setRows([]);
      setMeta(null);
    }
    setLoading(false);
  }, [teamFilter, search]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      load();
    }, 320);
    return () => window.clearTimeout(t);
  }, [load]);

  const sortPlayerList = useCallback((list) => {
    const copy = [...(list || [])];
    const dir = sortDir === "asc" ? 1 : -1;
    copy.sort((a, b) => {
      if (sortKey === "BatIP" || sortKey === "BowlIP") {
        const rawA = a.impact_points?.[sortKey];
        const rawB = b.impact_points?.[sortKey];
        const na = rawA == null || Number.isNaN(Number(rawA)) ? null : Number(rawA);
        const nb = rawB == null || Number.isNaN(Number(rawB)) ? null : Number(rawB);
        if (na == null && nb == null) return (a.name || "").localeCompare(b.name || "");
        if (na == null) return 1;
        if (nb == null) return -1;
        if (na !== nb) return dir * (na - nb);
        return (a.name || "").localeCompare(b.name || "");
      }
      const av = a.name || "";
      const bv = b.name || "";
      return dir * String(av).localeCompare(String(bv));
    });
    return copy;
  }, [sortKey, sortDir]);

  const sorted = useMemo(() => sortPlayerList(rows), [rows, sortPlayerList]);

  const groupedByTeam = useMemo(() => {
    const UNK = "__UNASSIGNED__";
    const bucket = new Map();
    for (const r of sorted) {
      const key = r.team_short && String(r.team_short).trim() ? String(r.team_short).trim() : UNK;
      if (!bucket.has(key)) bucket.set(key, []);
      bucket.get(key).push(r);
    }
    const seen = new Set();
    const order = [];
    for (const t of squadShorts) {
      if (bucket.has(t)) {
        order.push(t);
        seen.add(t);
      }
    }
    for (const k of bucket.keys()) {
      if (k !== UNK && !seen.has(k)) order.push(k);
    }
    if (bucket.has(UNK)) order.push(UNK);
    return order.map((key) => {
      const players = bucket.get(key) || [];
      const first = players[0];
      if (key === UNK) {
        return {
          key,
          short: null,
          title: "Other / unmatched",
          subtitle:
            "No IPL 2026 squad row for this SportMonks id or name — check squad seed or sync coverage",
          players,
        };
      }
      return {
        key,
        short: key,
        title: key,
        subtitle: first?.team || "",
        players,
      };
    });
  }, [sorted, squadShorts]);

  /** Prefer API `teams` (full list + stable grouping); fallback to client grouping from paginated rows */
  const sections = useMemo(() => {
    const apiTeams = meta?.teams;
    if (Array.isArray(apiTeams) && apiTeams.length > 0) {
      const seen = new Set();
      const ordered = [];
      for (const t of squadShorts) {
        const block = apiTeams.find((x) => x.team_short === t);
        if (block && (block.players || []).length > 0) {
          ordered.push(block);
          seen.add(t);
        }
      }
      for (const block of apiTeams) {
        const ts = block.team_short;
        if (ts && !seen.has(ts)) {
          ordered.push(block);
          seen.add(ts);
        }
      }
      const unassigned = apiTeams.find((x) => !x.team_short);
      const finalOrder = [...ordered];
      if (unassigned && (unassigned.players || []).length > 0) finalOrder.push(unassigned);

      return finalOrder.map((t) => {
        const key = t.team_short || "__UNASSIGNED__";
        const players = sortPlayerList(t.players || []);
        if (!t.team_short) {
          return {
            key,
            short: null,
            title: "Other / unmatched",
            subtitle:
              "No IPL 2026 squad match (id / name) — ensure squads are loaded and names align with SportMonks",
            players,
          };
        }
        return {
          key,
          short: t.team_short,
          title: t.team_short,
          subtitle: t.team || "",
          players,
        };
      });
    }
    return groupedByTeam.map((g) => ({
      ...g,
      players: sortPlayerList(g.players),
    }));
  }, [meta?.teams, groupedByTeam, squadShorts, sortPlayerList]);

  const toggleSort = (id) => {
    if (sortKey === id) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(id);
      setSortDir(id === "name" ? "asc" : "desc");
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 lg:px-8 py-6 space-y-4" data-testid="players-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#737373] hover:text-[#007AFF]"
          >
            <ArrowLeft className="w-3.5 h-3.5" weight="bold" /> Matches
          </Link>
          <div className="flex items-center gap-2">
            <UsersThree weight="fill" className="w-6 h-6 text-[#22D3EE]" />
            <div>
              <h1
                className="text-xl font-black uppercase tracking-tight text-white"
                style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
              >
                Players
              </h1>
              <p className="text-[10px] text-[#737373] font-mono">
                Squad role (Batsman / Bowler / WK / All-rounder) · impact columns match role; unused metrics are —
              </p>
            </div>
          </div>
        </div>
        {meta && (
          <p className="text-[10px] text-[#525252] font-mono">
            {meta.teams?.length
              ? `${meta.total_matching} players in ${meta.teams.length} groups · ${meta.total_in_db} docs in DB`
              : `Showing ${meta.returned} of ${meta.total_matching} matching · ${meta.total_in_db} docs in DB`}
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="search"
          placeholder="Search name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-[#262626] bg-[#141414] px-3 py-2 text-xs text-[#E5E5E5] w-full sm:w-56"
          data-testid="players-search"
        />
        <select
          value={teamFilter}
          onChange={(e) => setTeamFilter(e.target.value)}
          className="rounded-md border border-[#262626] bg-[#141414] px-3 py-2 text-xs text-[#E5E5E5]"
          data-testid="players-team-filter"
        >
          <option value="">All teams</option>
          {squadShorts.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="text-[10px] font-bold uppercase tracking-wider px-3 py-2 rounded-md border border-[#22D3EE]/40 text-[#A5F3FC] hover:bg-[#22D3EE]/10 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {meta?.note && (
        <p className="text-[10px] text-[#525252] border border-[#262626] rounded-md px-3 py-2 bg-[#0A0A0A]">{meta.note}</p>
      )}

      {error && (
        <div className="rounded-md border border-[#FF3B30]/40 bg-[#FF3B30]/10 px-3 py-2 text-xs text-[#FCA5A5]" data-testid="players-error">
          {typeof error === "string" ? error : JSON.stringify(error)}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-20 text-[#737373] text-sm rounded-lg border border-[#262626] bg-[#141414]">
          <Spinner className="w-5 h-5 animate-spin" /> Loading players…
        </div>
      ) : sections.length === 0 ? (
        <div className="rounded-lg border border-[#262626] bg-[#141414]">
          <p className="py-16 text-center text-sm text-[#737373]">
            No rows yet. Run <span className="text-[#22D3EE] font-mono">Sync player stats</span> on the pre-match screen, then refresh.
          </p>
        </div>
      ) : (
        <div className="space-y-4" data-testid="players-by-team">
          {sections.map((group) => (
            <div
              key={group.key}
              className="rounded-lg border border-[#262626] overflow-hidden bg-[#141414]"
              data-testid={`players-team-section-${group.short || "unassigned"}`}
            >
              <div className="px-3 py-2.5 bg-[#0A0A0A] border-b border-[#262626] flex flex-col gap-0.5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="text-xs font-black uppercase tracking-wide text-[#22D3EE]" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
                    {group.title}
                  </span>
                  {group.subtitle ? (
                    <span className="text-[10px] text-[#737373] ml-2 font-normal normal-case">{group.subtitle}</span>
                  ) : null}
                </div>
                <span className="text-[10px] font-mono text-[#525252]">{group.players.length} players</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]" data-testid={`players-table-${group.short || "unassigned"}`}>
                  <thead className="bg-[#0A0A0A] text-[#737373] uppercase tracking-wider font-bold border-b border-[#1E1E1E]">
                    <tr>
                      {SORTS.map((col) => (
                        <th key={col.id} className="px-3 py-2 whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() => toggleSort(col.id)}
                            className="inline-flex items-center gap-0.5 hover:text-[#A3A3A3]"
                          >
                            {col.label}
                            {sortKey === col.id ? (
                              sortDir === "asc" ? (
                                <CaretUp className="w-3 h-3" weight="bold" />
                              ) : (
                                <CaretDown className="w-3 h-3" weight="bold" />
                              )
                            ) : null}
                          </button>
                        </th>
                      ))}
                      <th className="px-3 py-2">Role</th>
                      <th className="px-3 py-2 text-right">Bat R/I</th>
                      <th className="px-3 py-2 text-right">Bowl W/I</th>
                      <th className="px-3 py-2">Conf</th>
                      <th className="px-3 py-2 text-right">BPR bat</th>
                      <th className="px-3 py-2 text-right">BPR bowl</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.players.map((r) => (
                      <tr key={`${r.player_id ?? "x"}-${r.name}`} className="border-b border-[#1E1E1E] hover:bg-[#1A1A1A]/80">
                        <td className="px-3 py-2 text-[#E5E5E5] font-medium">{r.name}</td>
                        <td className="px-3 py-2 font-mono text-[#34C759]">{fmtImpactPt(r.impact_points?.BatIP)}</td>
                        <td className="px-3 py-2 font-mono text-[#FBBF24]">{fmtImpactPt(r.impact_points?.BowlIP)}</td>
                        <td className="px-3 py-2 font-mono text-[#737373]">{r.primary_role ?? "—"}</td>
                        <td className="px-3 py-2 text-right font-mono text-[#A3A3A3]">
                          {r.batting_summary?.runs ?? 0}/{r.batting_summary?.innings ?? 0}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-[#A3A3A3]">
                          {r.bowling_summary?.wickets ?? 0}/{r.bowling_summary?.innings ?? 0}
                        </td>
                        <td
                          className="px-3 py-2 text-[9px] text-[#525252] max-w-[120px] truncate"
                          title={`${r.impact_points?.batting_confidence ?? "—"} / ${r.impact_points?.bowling_confidence ?? "—"}`}
                        >
                          {r.impact_points?.batting_confidence == null && r.impact_points?.bowling_confidence == null
                            ? "—"
                            : `${r.impact_points?.batting_confidence ?? "—"} / ${r.impact_points?.bowling_confidence ?? "—"}`}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-[#525252]">{fmtImpactPt(r.impact_points?.BPR_bat)}</td>
                        <td className="px-3 py-2 text-right font-mono text-[#525252]">{fmtImpactPt(r.impact_points?.BPR_bowl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
