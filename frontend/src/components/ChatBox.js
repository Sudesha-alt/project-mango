import { useState, useRef, useEffect } from "react";
import { Crosshair, Spinner, PaperPlaneTilt } from "@phosphor-icons/react";

export default function ChatBox({ matchId, sendChat, riskTolerance, marketOdds }) {
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
