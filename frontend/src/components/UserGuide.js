import { useState } from "react";
import {
  Question, X, Crosshair, Scales, TrendUp, Target,
  ArrowRight, CaretDown, CaretUp, Broadcast, ShieldCheck,
  Lightning, Info, UsersThree, ChartBar
} from "@phosphor-icons/react";

const SECTIONS = [
  {
    id: "getting-started",
    title: "Getting Started",
    icon: Lightning,
    content: [
      {
        q: "What does this app do?",
        a: "The Lucky 11 is an AI-powered IPL 2026 prediction engine. It uses an 8-category algorithm, Claude Opus AI analysis, real-time weather data, and official squad rosters to give you clear win probabilities and match insights."
      },
      {
        q: "How do I start?",
        a: "1. Go to the Matches page (home screen)\n2. Click any upcoming match card\n3. On the pre-match page, look at the Algorithm Prediction on the left — it auto-loads if previously computed\n4. Enter bookmaker odds in the Consultant panel on the right\n5. Hit 'Run Consultation' to get your full verdict"
      },
    ],
  },
  {
    id: "matches",
    title: "Match Selector",
    icon: Target,
    content: [
      {
        q: "What do the tabs mean?",
        a: "LIVE — Matches currently being played. You can fetch real-time data via CricketData.org API (100 hits/day).\nUPCOMING — Future matches. These are what you'll bet on. Each card shows the prediction if available.\nCOMPLETED — Past matches with final scores and results."
      },
      {
        q: "What do the green/red percentages on match cards mean?",
        a: "These are the Algorithm Prediction results — e.g., 'MI 62%' means the model gives Mumbai Indians a 62% win chance. Green = favored team, Red = underdog. The arrow icons show if odds are trending up or down since the last prediction."
      },
      {
        q: "What does 'Predict All' do?",
        a: "It runs the prediction algorithm for every upcoming match that hasn't been predicted yet. Each prediction takes 15-30 seconds (fetches real stats via GPT web search). You'll see the progress count."
      },
      {
        q: "What does 'Re-Predict All' do?",
        a: "It re-runs ALL predictions with fresh data, including updated Playing XI and latest form. This runs in the background — watch the purple progress bar at the top. Use this when news breaks (injury, team change, etc.)."
      },
    ],
  },
  {
    id: "prediction",
    title: "Algorithm Prediction",
    icon: Scales,
    content: [
      {
        q: "What is the Algorithm Prediction?",
        a: "It's a 5-factor model that predicts match winners:\n\n- Head-to-Head (25%) — Last 5 years of results between these teams\n- Venue Performance (20%) — Team scoring averages and win % at this ground\n- Recent Form (25%) — Last 5 IPL 2026 matches for each team\n- Squad Strength (20%) — Batting depth + bowling attack quality ratings\n- Home Advantage (10%) — Playing at home ground gets a small boost\n\nEach factor generates a logit score. The combined score passes through a calibration model for the final probability."
      },
      {
        q: "What does the two-sided factor bar mean?",
        a: "The bar extends LEFT toward Team 1 or RIGHT toward Team 2. GREEN side = advantage for that team. RED side = disadvantage. The longer the bar, the stronger the edge in that factor.\n\nExample: If H2H bar extends far to the left (green), Team 1 has dominated recent head-to-head meetings."
      },
      {
        q: "What does 'Re-Predict' do?",
        a: "Forces a fresh prediction with updated data. Use it before a match if you want the latest stats (new injury news, team changes). Each re-predict costs one GPT web search call."
      },
      {
        q: "What does the odds direction (arrows) mean?",
        a: "The green/red arrows show how the prediction CHANGED since the last run. +6.7% means this team's probability improved by 6.7 percentage points. This is your 'momentum shift' indicator — useful for spotting late value."
      },
    ],
  },
  {
    id: "consultant",
    title: "Consultation Engine",
    icon: Crosshair,
    content: [
      {
        q: "How do I use the Consultant?",
        a: "1. Set your Risk Tolerance (Play Safe / Balanced / Risk Taker)\n2. Enter the bookmaker's win % for each team (0-100 scale)\n   — e.g., If odds are 1.80 decimal, that's ~56% probability\n   — If odds are 2.50, that's ~40%\n3. Optionally set Market Momentum (which team's odds are rising)\n4. Click 'Run Consultation'\n5. Wait 10-15 seconds — the engine runs 50,000 simulations"
      },
      {
        q: "How do I convert decimal odds to win %?",
        a: "Win % = 100 / decimal odds\n\nExamples:\n- Odds 1.50 → 100/1.50 = 67%\n- Odds 1.80 → 100/1.80 = 56%\n- Odds 2.00 → 100/2.00 = 50%\n- Odds 2.50 → 100/2.50 = 40%\n- Odds 3.00 → 100/3.00 = 33%\n\nNote: Bookmaker odds always add up to more than 100% (that's the overround/margin). Enter raw percentages — the engine removes the overround automatically."
      },
      {
        q: "What does Risk Tolerance change?",
        a: "PLAY SAFE — Even small edges are flagged as risky. Recommendations lean toward 'skip' unless edge is large.\nBALANCED — Follows model signals directly. Recommended for most users.\nRISK TAKER — Leans into marginal edges. Will suggest 'calculated punt' on thin edges."
      },
      {
        q: "What is Market Momentum?",
        a: "If you notice odds moving in one direction (e.g., CSK's odds getting shorter), select 'CSK' under 'Odds Rising'. The engine applies a ~3% probability adjustment in that direction. This captures market wisdom that your data might not have."
      },
    ],
  },
  {
    id: "verdict",
    title: "Understanding the Verdict",
    icon: ShieldCheck,
    content: [
      {
        q: "What does the big verdict mean?",
        a: "The verdict (e.g., 'MI WINS') is the engine's clear call. The strength levels are:\n\nDOMINANT (80%+) — Near-certain outcome. Very rare.\nSTRONG (65-80%) — Clear favorite with solid data support.\nSLIGHT (55-65%) — Competitive match, small edge.\nTOSS-UP (<55%) — Coin flip. Wait for live data."
      },
      {
        q: "What do the betting signals mean?",
        a: "STRONG VALUE — Edge 8%+. The market is significantly underpricing this team. High-conviction bet.\nVALUE — Edge 4-8%. Market is underpricing. Worth a bet.\nSMALL EDGE — Edge 1-4%. Marginal value exists. Proceed with caution.\nNO BET — Edge -2% to 1%. Market is fairly priced. No value.\nAVOID — Edge below -2%. Market is overvaluing. Negative expected value."
      },
      {
        q: "What is 'WHY THIS SIGNAL'?",
        a: "These are the engine's reasoning pointers explaining WHY it gave that signal. For example:\n- 'Model rates MI at 66%, market only gives 55% — 11% undervalued'\n- 'Edge of 11% is significant — clear market mispricing'\n\nRead these to understand the logic, not just the label."
      },
      {
        q: "What does Edge % mean?",
        a: "Edge = Your model's probability MINUS the bookmaker's implied probability.\n\nPositive edge = The market is undervaluing this team. You have an advantage.\nNegative edge = The market is overvaluing. Betting has negative expected value.\n\nExample: Model says 66%, bookmaker implies 55% → Edge = +11%. That's strong value."
      },
    ],
  },
  {
    id: "simulation",
    title: "50K Simulations",
    icon: ChartBar,
    content: [
      {
        q: "What are the predicted scores?",
        a: "The engine simulates 50,000 complete matches using Negative Binomial distribution (which matches real cricket score patterns — right-skewed). The 'predicted runs' is the average score across all simulations."
      },
      {
        q: "What do Mean, Median, Range mean?",
        a: "Mean — Average score across 50K simulations.\nMedian — Middle score (50th percentile). Less affected by extreme outcomes.\nRange (P10-P90) — In 80% of simulations, the team scores between these numbers. The wider the range, the more unpredictable the outcome."
      },
      {
        q: "What does 'Batting first wins X%' mean?",
        a: "In simulations where Team 1 bats first, this is how often they win. If it's 70%+, batting first has a significant advantage at this venue. This is useful for toss-related bets."
      },
    ],
  },
  {
    id: "scenarios",
    title: "Betting Scenarios",
    icon: TrendUp,
    content: [
      {
        q: "What are Betting Scenarios?",
        a: "These are AI-generated betting windows — specific moments in the match where you should pay attention. Each scenario tells you WHEN to bet and WHY."
      },
      {
        q: "What do the scenario types mean?",
        a: "PRE_MATCH — Bet before the match starts.\nIN_PLAY_POWERPLAY — Bet after the powerplay based on the score.\nPLAYER_OUTBURST — A specific player is predicted to perform well.\nCHASE_DYNAMIC — Bet during the chase based on predicted scores.\nBET_AGAINST_ODDS — Contrarian bet if the favorite struggles early.\nKEY_DEPENDENCE — Shows which players the result depends on."
      },
      {
        q: "What does HIGH/MEDIUM confidence mean?",
        a: "HIGH confidence — The engine is very sure about this scenario. Act on it if the conditions match.\nMEDIUM confidence — Worth watching, but the outcome is less certain. Wait for confirming signals."
      },
    ],
  },
  {
    id: "playing-xi",
    title: "Playing XI & Players",
    icon: UsersThree,
    content: [
      {
        q: "Where does the Playing XI come from?",
        a: "The expected Playing XI is scraped via GPT-5.4 web search from news sources (Cricbuzz, ESPNcricinfo, Twitter/X, fantasy sites). It checks for:\n- Confirmed lineups or expert predictions\n- Injury news, fitness concerns, dropped players\n- Squad changes and team announcements\n\nUnavailable players are automatically replaced with likely squad members."
      },
      {
        q: "What does Buzz Score mean?",
        a: "Buzz is a SENTIMENT score from -100 to +100:\n\n+70 to +100: Star form, MOTM awards, experts' top pick\n+30 to +69: Good form, trending positively\n-10 to +29: Neutral/mixed signals\n-50 to -10: Poor form, niggle concerns, dropped from fantasy\n-100 to -50: Major injury doubt, controversy, terrible streak\n\nClick a player's buzz badge to see the specific reason (e.g., 'Scored century last match' or 'Recovering from hamstring injury')."
      },
      {
        q: "How are runs/wickets calculated?",
        a: "Performance = Base Stats x Buzz Modifier x Luck Factor\n\n- Base Stats: 60% venue-specific performance + 40% IPL 2026 season form\n- Buzz Modifier: Maps buzz score to ±20% adjustment (positive buzz boosts, negative reduces)\n- Luck Factor: Random ±15% variance simulating match-day unpredictability\n\nA player with buzz -60 (injury doubt) will have their expected runs reduced by ~12%, while +80 (star form) gets a ~16% boost."
      },
      {
        q: "What does Player Impact show?",
        a: "The top impactful players from both teams in the Consultant Dashboard. Shows predicted runs, wickets, and their buzz score. Hover over a player to see the buzz reason. These come from the cached Playing XI — not random squad picks."
      },
    ],
  },
  {
    id: "chat",
    title: "Consultant Chat",
    icon: Question,
    content: [
      {
        q: "What can I ask the chat?",
        a: "Ask anything in plain English:\n- 'Should I bet on this match?'\n- 'Is MI a good bet at 1.80 odds?'\n- 'What's the safest bet here?'\n- 'Should I wait for in-play?'\n\nThe AI has full context of the consultation results and your risk profile."
      },
    ],
  },
  {
    id: "live",
    title: "Live Matches",
    icon: Broadcast,
    content: [
      {
        q: "How does live tracking work?",
        a: "On the Live tab, click 'Fetch Live IPL Details' to pull real-time data from CricketData.org. This costs 1 API hit (100/day limit). You can also use the 'Fetch Live Data' button on individual match pages to get GPT-powered live updates."
      },
      {
        q: "Why is there an API limit?",
        a: "CricketData.org's free tier allows 100 API calls per day. Each 'Fetch' button press uses 1 call. The counter at the top of the Live panel shows how many you've used. Plan your fetches wisely during live matches."
      },
    ],
  },
];

export default function UserGuide() {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedSection, setExpandedSection] = useState(null);
  const [expandedQ, setExpandedQ] = useState({});

  const toggleQ = (sectionId, idx) => {
    const key = `${sectionId}-${idx}`;
    setExpandedQ(prev => ({ ...prev, [key]: !prev[key] }));
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        data-testid="open-user-guide-btn"
        className="fixed bottom-6 left-6 z-50 bg-[#007AFF] text-white w-12 h-12 rounded-full flex items-center justify-center shadow-lg hover:bg-blue-600 transition-all hover:scale-110"
        title="How to use this app"
      >
        <Question weight="bold" className="w-6 h-6" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" data-testid="user-guide-overlay">
      <div className="bg-[#0A0A0A] border border-[#262626] rounded-lg w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#262626]">
          <div>
            <h2 className="text-lg font-black uppercase tracking-tight" style={{ fontFamily: "'Barlow Condensed'" }}>
              How to Use The Lucky 11
            </h2>
            <p className="text-[10px] text-[#737373] mt-0.5">Your guide to making smarter IPL betting decisions</p>
          </div>
          <button onClick={() => setIsOpen(false)} data-testid="close-user-guide-btn"
            className="text-[#737373] hover:text-white transition-colors p-1">
            <X weight="bold" className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {SECTIONS.map((section) => (
            <div key={section.id} className="border-b border-[#262626] last:border-0">
              <button
                onClick={() => setExpandedSection(expandedSection === section.id ? null : section.id)}
                className="w-full flex items-center justify-between px-5 py-3 hover:bg-[#141414] transition-colors"
                data-testid={`guide-section-${section.id}`}
              >
                <div className="flex items-center gap-2.5">
                  <section.icon weight="fill" className="w-4 h-4 text-[#007AFF]" />
                  <span className="text-sm font-bold text-white">{section.title}</span>
                  <span className="text-[9px] text-[#525252] font-mono">{section.content.length} topics</span>
                </div>
                {expandedSection === section.id ?
                  <CaretUp weight="bold" className="w-4 h-4 text-[#525252]" /> :
                  <CaretDown weight="bold" className="w-4 h-4 text-[#525252]" />
                }
              </button>

              {expandedSection === section.id && (
                <div className="px-5 pb-3 space-y-1">
                  {section.content.map((item, idx) => {
                    const key = `${section.id}-${idx}`;
                    const isExpanded = expandedQ[key];
                    return (
                      <div key={idx} className="border border-[#262626] rounded-md overflow-hidden">
                        <button
                          onClick={() => toggleQ(section.id, idx)}
                          className="w-full flex items-center justify-between px-3 py-2 hover:bg-[#1A1A1A] transition-colors text-left"
                        >
                          <span className="text-xs text-[#A3A3A3] font-medium">{item.q}</span>
                          {isExpanded ?
                            <CaretUp weight="bold" className="w-3 h-3 text-[#525252] flex-shrink-0 ml-2" /> :
                            <CaretDown weight="bold" className="w-3 h-3 text-[#525252] flex-shrink-0 ml-2" />
                          }
                        </button>
                        {isExpanded && (
                          <div className="px-3 pb-3 pt-1">
                            <p className="text-[11px] text-[#737373] leading-relaxed whitespace-pre-line" style={{ fontFamily: "'IBM Plex Sans'" }}>
                              {item.a}
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[#262626] flex items-center justify-between">
          <p className="text-[9px] text-[#525252]">Powered by 50K Neg. Binomial Simulations + GPT-5.4 Web Search</p>
          <button onClick={() => setIsOpen(false)} className="text-xs text-[#007AFF] font-bold uppercase tracking-wider hover:text-blue-400 transition-colors">
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
