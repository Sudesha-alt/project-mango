import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useMatchData() {
  const [liveMatches, setLiveMatches] = useState([]);
  const [fixtures, setFixtures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLiveMatches = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/matches/live`);
      setLiveMatches(res.data.matches || []);
      setError(null);
    } catch (e) {
      setError("Failed to fetch live matches");
      console.error(e);
    }
  }, []);

  const fetchFixtures = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/matches/fixtures`);
      setFixtures(res.data.fixtures || []);
    } catch (e) {
      console.error("Fixtures fetch error:", e);
    }
  }, []);

  const fetchMatchDetail = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}`);
      return res.data;
    } catch (e) {
      console.error("Match detail error:", e);
      return null;
    }
  }, []);

  const fetchScorecard = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/scorecard`);
      return res.data;
    } catch (e) {
      console.error("Scorecard error:", e);
      return null;
    }
  }, []);

  const fetchSquad = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/squad`);
      return res.data;
    } catch (e) {
      console.error("Squad error:", e);
      return null;
    }
  }, []);

  const fetchPredictions = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/predictions`);
      return res.data;
    } catch (e) {
      console.error("Predictions error:", e);
      return null;
    }
  }, []);

  const fetchOdds = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/odds`);
      return res.data;
    } catch (e) {
      console.error("Odds error:", e);
      return null;
    }
  }, []);

  const triggerCalculation = useCallback(async (matchId) => {
    try {
      const res = await axios.post(`${API}/matches/${matchId}/calculate`);
      return res.data;
    } catch (e) {
      console.error("Calculation error:", e);
      return null;
    }
  }, []);

  const fetchPlayerPredictions = useCallback(async (matchId) => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/player-predictions`);
      return res.data;
    } catch (e) {
      console.error("Player predictions error:", e);
      return null;
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchLiveMatches(), fetchFixtures()]);
      setLoading(false);
    };
    load();
    const interval = setInterval(fetchLiveMatches, 30000);
    return () => clearInterval(interval);
  }, [fetchLiveMatches, fetchFixtures]);

  return {
    liveMatches, fixtures, loading, error,
    fetchLiveMatches, fetchFixtures, fetchMatchDetail,
    fetchScorecard, fetchSquad, fetchPredictions,
    fetchOdds, triggerCalculation, fetchPlayerPredictions
  };
}
