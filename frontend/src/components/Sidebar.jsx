import { MessageSquareText, Clock, Info, Settings } from "lucide-react";
import logo from "../assets/logo.png";
import hood from "../assets/hood.png";

const NAV = [
  { id: "chat", label: "Chat", Icon: MessageSquareText },
  { id: "history", label: "History", Icon: Clock },
  { id: "about", label: "About", Icon: Info },
  { id: "settings", label: "Settings", Icon: Settings },
];

export default function Sidebar({ view, setView, online }) {
  return (
    <aside className="panel sidebar">
      <div className="brand">
        <img src={logo} alt="" className="brand-logo" />
        <h2 className="brand-name">QUNTUMMINES</h2>
        <p className="brand-tag">Detect. Verify. Stay Informed.</p>
      </div>

      <nav className="nav" aria-label="Main">
        {NAV.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`nav-item ${view === id ? "active" : ""}`}
            onClick={() => setView(id)}
            aria-current={view === id ? "page" : undefined}
          >
            <Icon size={26} strokeWidth={1.6} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="hood" style={{ "--hood": `url(${hood})` }}>
        <p>
          “QUESTION
          <br />
          INFORMATION
          <br />
          THINK CRITICALLY
          <br />
          STAY AHEAD”
        </p>
      </div>

      <div className="status">
        <div className="status-line">
          <span className={`dot ${online ? "" : "off"}`} />
          <strong>{online ? "System Online" : "System Offline"}</strong>
        </div>
        <small>AI Powered • Real-time Analysis</small>
      </div>
    </aside>
  );
}
