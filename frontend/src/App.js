import { useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Header from "@/components/Header";
import UserGuide from "@/components/UserGuide";
import MatchSelector from "@/pages/MatchSelector";
import PreMatch from "@/pages/PreMatch";
import LiveMatch from "@/pages/LiveMatch";
import PostMatch from "@/pages/PostMatch";
import Analysis from "@/pages/Analysis";
import ComparisonDashboard from "@/pages/ComparisonDashboard";
import Players from "@/pages/Players";

function App() {
  const [selectedMatch, setSelectedMatch] = useState(null);

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <BrowserRouter>
        <Header selectedMatch={selectedMatch} />
        <UserGuide />
        <main>
          <Routes>
            <Route path="/" element={<MatchSelector />} />
            <Route path="/pre-match/:matchId" element={<PreMatch />} />
            <Route path="/live/:matchId" element={<LiveMatch />} />
            <Route path="/live" element={<MatchSelector />} />
            <Route path="/post-match/:matchId" element={<PostMatch />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/compare" element={<ComparisonDashboard />} />
            <Route path="/players" element={<Players />} />
          </Routes>
        </main>
      </BrowserRouter>
    </div>
  );
}

export default App;
