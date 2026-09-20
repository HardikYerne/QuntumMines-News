import { ShieldCheck, Trash2 } from "lucide-react";

export function HistoryView({ history, onClear, onOpen }) {
  return (
    <div className="view">
      <div className="view-head">
        <h3>History</h3>
        {history.length > 0 && (
          <button className="ghost" onClick={onClear}>
            <Trash2 size={16} /> Clear history
          </button>
        )}
      </div>
      {history.length === 0 ? (
        <p className="muted">No claims checked yet. Go to Chat and ask about a news claim.</p>
      ) : (
        <ul className="hist">
          {history.map((h) => (
            <li key={h.id}>
              <button onClick={onOpen}>
                <span className={`tag ${h.verdict}`}>{h.verdict === "fake" ? "Likely fake" : h.verdict === "real" ? "Likely real" : "Unverified"}</span>
                <span className="hist-text">{h.claim}</span>
                <time>{h.time}</time>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AboutView() {
  return (
    <div className="view">
      <div className="view-head">
        <h3>About QuntumMines</h3>
      </div>
      <p>
        QuntumMines is an AI chatbot that checks news claims, scores how well the evidence supports them,
        and explains its reasoning in plain language.
      </p>
      <p className="muted">
        Results are a guide, not a final ruling. Confirm important claims with trusted sources before you
        share them.
      </p>
      <p className="about-badge">
        <ShieldCheck size={18} /> Real facts. Safer minds. A better tomorrow.
      </p>
    </div>
  );
}

export function SettingsView({ settings, setSettings }) {
  return (
    <div className="view">
      <div className="view-head">
        <h3>Settings</h3>
      </div>
      <label className="setting">
        <span>
          Save chat history on this device
          <small>Keeps your checked claims in the History tab.</small>
        </span>
        <input
          type="checkbox"
          checked={settings.saveHistory}
          onChange={(e) => setSettings({ ...settings, saveHistory: e.target.checked })}
        />
      </label>
    </div>
  );
}
