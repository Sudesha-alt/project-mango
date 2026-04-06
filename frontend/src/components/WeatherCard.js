import { useState, useEffect } from "react";
import { CloudRain, Sun, Wind, Drop, Thermometer, CloudFog } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export function WeatherCard({ matchId, city, compact = false }) {
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchWeather = async () => {
      if (!matchId && !city) return;
      setLoading(true);
      try {
        const url = matchId
          ? `${API}/matches/${matchId}/weather`
          : `${API}/weather/${encodeURIComponent(city)}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.available) setWeather(data);
      } catch (e) {
        console.error("Weather fetch failed:", e);
      }
      setLoading(false);
    };
    fetchWeather();
  }, [matchId, city]);

  if (loading) {
    return (
      <div data-testid="weather-loading" className="bg-[#141414] border border-white/10 rounded-md p-4">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-[#71717A]">Loading weather...</span>
        </div>
      </div>
    );
  }

  if (!weather) return null;

  const cur = weather.current || {};
  const impact = weather.cricket_impact || {};
  const condition = cur.condition || "Unknown";

  const getWeatherIcon = () => {
    const c = condition.toLowerCase();
    if (c.includes("rain") || c.includes("drizzle") || c.includes("shower")) return <CloudRain weight="fill" className="w-5 h-5 text-blue-400" />;
    if (c.includes("fog")) return <CloudFog weight="fill" className="w-5 h-5 text-gray-400" />;
    if (c.includes("cloud") || c.includes("overcast")) return <CloudRain weight="fill" className="w-5 h-5 text-gray-300" />;
    return <Sun weight="fill" className="w-5 h-5 text-yellow-400" />;
  };

  const getDewBadge = () => {
    if (impact.dew_factor === "heavy") return <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-bold">HEAVY DEW</span>;
    if (impact.dew_factor === "moderate") return <span className="text-[10px] bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded font-bold">MODERATE DEW</span>;
    return null;
  };

  if (compact) {
    return (
      <div data-testid="weather-compact" className="flex items-center gap-3 text-xs">
        {getWeatherIcon()}
        <span>{cur.temperature}C</span>
        <span className="text-[#71717A]">{condition}</span>
        {getDewBadge()}
      </div>
    );
  }

  return (
    <div data-testid="weather-card" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4 className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>
        Weather Conditions
      </h4>

      <div className="flex items-center gap-3 mb-3">
        {getWeatherIcon()}
        <div>
          <p className="text-sm font-bold">{condition}</p>
          <p className="text-xs text-[#71717A]">{weather.city}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="flex items-center gap-2 text-xs">
          <Thermometer weight="bold" className="w-3.5 h-3.5 text-red-400" />
          <span className="text-[#71717A]">Temp</span>
          <span className="ml-auto font-mono">{cur.temperature}C</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Drop weight="bold" className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-[#71717A]">Humidity</span>
          <span className="ml-auto font-mono">{cur.humidity}%</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Wind weight="bold" className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[#71717A]">Wind</span>
          <span className="ml-auto font-mono">{cur.wind_speed_kmh} km/h</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <CloudRain weight="bold" className="w-3.5 h-3.5 text-blue-300" />
          <span className="text-[#71717A]">Rain</span>
          <span className="ml-auto font-mono">{cur.rain_mm || 0} mm</span>
        </div>
      </div>

      {/* Dew factor badge */}
      {getDewBadge() && (
        <div className="mb-2">{getDewBadge()}</div>
      )}

      {/* Cricket impact */}
      {impact.summary && (
        <div className="bg-white/5 rounded p-2 mt-2">
          <p className="text-[10px] uppercase tracking-wider text-[#A1A1AA] mb-1 font-bold">Cricket Impact</p>
          <p className="text-xs text-[#D4D4D8]">{impact.summary}</p>
          <div className="flex gap-2 mt-1.5">
            {!impact.play_likely && (
              <span className="text-[10px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded font-bold">RAIN RISK</span>
            )}
            {impact.swing_conditions === "favorable" && (
              <span className="text-[10px] bg-green-500/20 text-green-300 px-1.5 py-0.5 rounded font-bold">SWING</span>
            )}
            {impact.batting_conditions === "good" && (
              <span className="text-[10px] bg-yellow-500/20 text-yellow-300 px-1.5 py-0.5 rounded font-bold">BATTING-FRIENDLY</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default WeatherCard;
