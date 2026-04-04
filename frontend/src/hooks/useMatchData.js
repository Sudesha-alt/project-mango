import { useState, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useMatchData() {
  const [schedule, setSchedule] = useState({ matches: [], live: [], upcoming: [], completed: [], loaded: false });
  const [squads, setSquads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/`);
      setApiStatus(res.data);
      return res.data;
    } catch (e) { console.error(e); }
  }, []);

  const loadSchedule = useCallback(async (force = false) => {
    setLoading(true);
    try {
      // Trigger GPT load if needed
      await axios.get(`${API}/schedule/load${force ? "?force=true" : ""}`);
      const res = await axios.get(`${API}/schedule`);
      setSchedule(res.data);
      return res.data;
    } catch (e) {
      console.error("Schedule load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSquads = useCallback(async (force = false) => {
    try {
      await axios.get(`${API}/squads/load${force ? "?force=true" : ""}`);
      const res = await axios.get(`${API}/squads`);
      setSquads(res.data.squads || []);
      return res.data.squads;
    } catch (e) { console.error("Squads load error:", e); }
  }, []);

  const getTeamSquad = useCallback(async (teamShort) => {
    try {
      const res = await axios.get(`${API}/squads/${teamShort}`);
      return res.data.squad;
    } catch (e) { return null; }
  }, []);

  const fetchLiveData = useCallback(async (matchId, bettingOdds = null) => {
    try {
      const body = bettingOdds || {};
      const res = await axios.post(`${API}/matches/${matchId}/fetch-live`, body);
      return res.data;
    } catch (e) {
      console.error("Live fetch error:", e);
      return null;
    }
  }, []);

  const getMatchState = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/state`);
      return res.data;
    } catch (e) { return null; }
  }, []);

  const fetchPlayerPredictions = useCallback(async (matchId) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/player-predictions`);
      return res.data;
    } catch (e) { return null; }
  }, []);

  const fetchMatchPrediction = useCallback(async (matchId) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/predict`);
      return res.data;
    } catch (e) { return null; }
  }, []);

  const fetchBetaPrediction = useCallback(async (matchId, marketOdds = {}) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/beta-predict`, {
        market_team1_pct: marketOdds.team1 || null,
        market_team2_pct: marketOdds.team2 || null,
      });
      return res.data;
    } catch (e) {
      console.error("Beta prediction error:", e);
      return null;
    }
  }, []);

  const fetchConsultation = useCallback(async (matchId, opts = {}) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/consult`, {
        market_pct_team1: opts.marketPctTeam1 || null,
        market_pct_team2: opts.marketPctTeam2 || null,
        risk_tolerance: opts.riskTolerance || "balanced",
        odds_trend_increasing: opts.oddsTrendIncreasing || null,
        odds_trend_decreasing: opts.oddsTrendDecreasing || null,
      });
      return res.data;
    } catch (e) {
      console.error("Consultation error:", e);
      return null;
    }
  }, []);

  const sendChat = useCallback(async (matchId, question, opts = {}) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/chat`, {
        question,
        risk_tolerance: opts.riskTolerance || "balanced",
        market_pct_team1: opts.marketPctTeam1 || null,
        market_pct_team2: opts.marketPctTeam2 || null,
      });
      return res.data;
    } catch (e) {
      console.error("Chat error:", e);
      return null;
    }
  }, []);

  const fetchClaudeAnalysis = useCallback(async (matchId, forceRefresh = false) => {
    try {
      if (forceRefresh) {
        // POST triggers generation (with web scraping)
        const res = await axios.post(`${API}/matches/${matchId}/claude-analysis`);
        return res.data;
      } else {
        // GET retrieves cached only
        const res = await axios.get(`${API}/matches/${matchId}/claude-analysis`);
        return res.data;
      }
    } catch (e) {
      console.error("Claude analysis error:", e);
      return null;
    }
  }, []);

  const clearClaudeAnalysis = useCallback(async (matchId) => {
    try {
      await axios.delete(`${API}/matches/${matchId}/claude-analysis`);
    } catch (e) { console.error(e); }
  }, []);

  const fetchClaudeLive = useCallback(async (matchId) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/claude-live`);
      return res.data;
    } catch (e) {
      console.error("Claude live error:", e);
      return null;
    }
  }, []);

  return {
    schedule, squads, loading, apiStatus,
    fetchStatus, loadSchedule, loadSquads, getTeamSquad,
    fetchLiveData, getMatchState, fetchPlayerPredictions, fetchMatchPrediction,
    fetchBetaPrediction, fetchConsultation, sendChat,
    fetchClaudeAnalysis, clearClaudeAnalysis, fetchClaudeLive,
  };
}
