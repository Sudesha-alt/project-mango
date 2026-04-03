export default function BallLog({ balls = [] }) {
  const getBallClass = (ball) => {
    if (ball.isWicket) return "ball-w";
    if (ball.runs === 6) return "ball-6";
    if (ball.runs === 4) return "ball-4";
    if (ball.isWide) return "ball-wd";
    if (ball.isNoBall) return "ball-nb";
    if (ball.runs === 0) return "ball-dot";
    return `ball-${ball.runs}`;
  };

  const getBallText = (ball) => {
    if (ball.isWicket) return "W";
    if (ball.isWide) return "WD";
    if (ball.isNoBall) return "NB";
    if (ball.runs === 0) return "\u2022";
    return ball.runs;
  };

  const displayBalls = balls.slice(-30);

  return (
    <div data-testid="ball-log" className="bg-[#141414] border border-white/10 rounded-md p-4">
      <h4
        className="text-xs uppercase tracking-[0.2em] font-bold text-[#A1A1AA] mb-3"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Ball Log
      </h4>
      {displayBalls.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {displayBalls.map((ball, i) => (
            <div
              key={i}
              data-testid={`ball-${i}`}
              className={`w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold ${getBallClass(ball)}`}
            >
              {getBallText(ball)}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[#71717A]">No ball data available yet</p>
      )}
    </div>
  );
}
