import { Link, useLocation } from "react-router-dom";
import { Pulse, ChartLine, Target, Crosshair, UsersThree, Brain } from "@phosphor-icons/react";

export default function Header({ selectedMatch }) {
  const location = useLocation();
  const path = location.pathname;

  const navItems = [
    { path: "/", label: "MATCHES", icon: Target },
    { path: "/live", label: "LIVE", icon: Pulse },
    { path: "/players", label: "PLAYERS", icon: UsersThree },
    { path: "/analysis", label: "ANALYSIS", icon: ChartLine },
    { path: "/model-learning", label: "LEARN", icon: Brain },
  ];

  return (
    <header
      data-testid="main-header"
      className="sticky top-0 z-50 bg-black/60 backdrop-blur-xl border-b border-white/10"
    >
      <div className="max-w-[1600px] mx-auto px-4 lg:px-8 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="logo-link">
          <Crosshair weight="fill" className="text-[#007AFF] w-6 h-6" />
          <span
            className="text-lg font-black uppercase tracking-tight"
            style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
          >
            Predictability
          </span>
        </Link>

        <nav className="flex items-center gap-1" data-testid="main-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              path === item.path ||
              (item.path === "/live" && path.startsWith("/live")) ||
              (item.path === "/players" && path.startsWith("/players")) ||
              (item.path === "/model-learning" && path.startsWith("/model-learning"));
            return (
              <Link
                key={item.path}
                to={item.path === "/live" && selectedMatch ? `/live/${selectedMatch}` : item.path}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider transition-colors ${
                  isActive
                    ? "bg-[#007AFF] text-white"
                    : "text-[#A1A1AA] hover:text-white hover:bg-[#1E1E1E]"
                }`}
              >
                <Icon weight={isActive ? "fill" : "bold"} className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          {selectedMatch && (
            <span className="text-xs font-mono text-[#A1A1AA]" data-testid="selected-match-id">
              #{selectedMatch.slice(0, 8)}
            </span>
          )}
          <div className="flex items-center gap-1.5" data-testid="live-indicator">
            <span className="w-2 h-2 rounded-full bg-[#22C55E] animate-live-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-[#A1A1AA]">LIVE</span>
          </div>
        </div>
      </div>
    </header>
  );
}
