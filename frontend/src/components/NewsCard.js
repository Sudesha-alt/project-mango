import { useState, useEffect } from "react";
import { Newspaper, ArrowSquareOut } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export function NewsCard({ matchId }) {
  const [news, setNews] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchNews = async () => {
      if (!matchId) return;
      setLoading(true);
      try {
        const res = await fetch(`${API}/matches/${matchId}/news`);
        const data = await res.json();
        if (data.articles?.length > 0) setNews(data);
      } catch (e) {
        console.error("News fetch failed:", e);
      }
      setLoading(false);
    };
    fetchNews();
  }, [matchId]);

  if (loading) {
    return (
      <div data-testid="news-loading" className="bg-[#141414] border border-white/10 rounded-md p-4">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-[#71717A]">Loading match news...</span>
        </div>
      </div>
    );
  }

  if (!news || !news.articles?.length) return null;

  const articles = expanded ? news.articles : news.articles.slice(0, 3);

  return (
    <div data-testid="news-card" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3 flex items-center gap-1.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        <Newspaper weight="bold" className="w-3.5 h-3.5 text-[#007AFF]" />
        Match News
        <span className="text-[9px] font-mono text-[#525252] ml-auto">{news.count} articles</span>
      </h4>

      <div className="space-y-2.5">
        {articles.map((article, i) => (
          <a
            key={i}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            data-testid={`news-article-${i}`}
            className="block bg-[#1E1E1E] rounded-md p-2.5 hover:bg-[#252525] transition-colors group"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-white group-hover:text-[#007AFF] transition-colors line-clamp-2 leading-relaxed">
                  {article.title}
                </p>
                {article.body && (
                  <p className="text-[10px] text-[#71717A] mt-1 line-clamp-2">{article.body}</p>
                )}
                <div className="flex items-center gap-2 mt-1.5">
                  {article.source && (
                    <span className="text-[9px] text-[#525252] font-mono">{article.source}</span>
                  )}
                  {article.date && (
                    <span className="text-[9px] text-[#525252] font-mono">
                      {new Date(article.date).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              <ArrowSquareOut weight="bold" className="w-3.5 h-3.5 text-[#525252] group-hover:text-[#007AFF] transition-colors flex-shrink-0 mt-0.5" />
            </div>
          </a>
        ))}
      </div>

      {news.articles.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          data-testid="news-expand-btn"
          className="w-full mt-2 text-[10px] font-bold uppercase tracking-wider text-[#007AFF] hover:text-white transition-colors py-1"
        >
          {expanded ? "Show Less" : `Show ${news.articles.length - 3} More`}
        </button>
      )}
    </div>
  );
}

export default NewsCard;
