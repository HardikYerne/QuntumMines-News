import { TriangleAlert, ShieldCheck, CircleHelp } from "lucide-react";
import Donut from "./Donut.jsx";

const VERDICTS = {
  fake: { title: "LIKELY FAKE", cls: "fake", Icon: TriangleAlert },
  real: { title: "LIKELY REAL", cls: "real", Icon: ShieldCheck },
  uncertain: { title: "UNVERIFIED", cls: "unsure", Icon: CircleHelp },
};

export default function ResultCard({ data }) {
  const v = VERDICTS[data.verdict] || VERDICTS.uncertain;
  const { Icon } = v;
  // Green always marks the side that matches a "real" outcome, red the "fake" side.
  // Likely Real -> True is green / False is red. Likely Fake (and Unverified) keep the reference look.
  const isReal = data.verdict === "real";
  const trueColor = isReal ? "#19f56a" : "#ff4d57";
  const falseColor = isReal ? "#ff4d57" : "#19f56a";
  return (
    <section className={`result ${v.cls}`}>
      <div className="result-head">
        <span className="result-icon">
          <Icon size={22} strokeWidth={2.4} />
        </span>
        <h4>{v.title}</h4>
      </div>
      <p className="result-summary">{data.summary}</p>

      <div className="result-grid">
        <div className="conf">
          <Donut value={data.confidenceTrue} color={trueColor} size={112} font={28} />
          <span>Confidence</span>
          <span>(Claim is True)</span>
        </div>

        <div className="box">
          <h5>Explanation</h5>
          <p>{data.explanation}</p>
        </div>

        <div className="box">
          <h5>Corrected Version</h5>
          <p>{data.corrected}</p>
        </div>

        <div className="conf">
          <Donut value={data.confidenceFalse} color={falseColor} size={112} font={28} />
          <span>Confidence</span>
          <span>(Claim is False)</span>
        </div>
      </div>
    </section>
  );
}
