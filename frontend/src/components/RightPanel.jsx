import { Activity, Target, Lightbulb, CircleCheck } from "lucide-react";
import Donut from "./Donut.jsx";

const TIPS = [
  "Check the source",
  "Look for evidence",
  "Be skeptical of sensational claims",
  "Verify with trusted news outlets",
  "Think before you share",
];

export default function RightPanel({ reliable, fake }) {
  return (
    <aside className="right">
      <section className="panel card">
        <h3 className="card-title with-line">
          <Activity size={22} strokeWidth={1.8} /> ANALYSIS OVERVIEW
        </h3>
        <div className="overview">
          <div className="ov-item">
            <Donut value={reliable} color="#19f56a" size={108} font={26} />
            <b className="ov-name green-text">Reliable News</b>
            <small>Verified Claims</small>
          </div>
          <div className="ov-item">
            <Donut value={fake} color="#ff4d57" size={108} font={26} />
            <b className="ov-name red-text">Likely Fake</b>
            <small>Misinformation</small>
          </div>
        </div>
      </section>

      <section className="panel card mission">
        <h3 className="card-title">
          <Target size={24} strokeWidth={1.8} /> OUR MISSION
        </h3>
        <p>To fight misinformation using AI, fact-checking, and critical thinking.</p>
      </section>

      <section className="panel card tips">
        <h3 className="card-title">
          <Lightbulb size={24} strokeWidth={1.8} /> QUICK TIPS
        </h3>
        <ul>
          {TIPS.map((t) => (
            <li key={t}>
              <CircleCheck size={24} strokeWidth={1.6} />
              {t}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel card quote">
        <p>
          “IN A WORLD OF INFORMATION
          <br />
          BE THE SEEKER OF TRUTH”
        </p>
      </section>
    </aside>
  );
}
