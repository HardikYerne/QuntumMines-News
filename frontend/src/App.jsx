import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Header from "./components/Header.jsx";
import RightPanel from "./components/RightPanel.jsx";
import Composer from "./components/Composer.jsx";
import Message, { Typing } from "./components/Message.jsx";
import { HistoryView, AboutView, SettingsView } from "./components/Views.jsx";
import { sendMessage } from "./api.js";

const now = () => new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
let uid = 0;
const id = () => `${Date.now()}-${uid++}`;

const load = (key, fallback) => {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
};
const save = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
};

const WELCOME = {
  id: "welcome",
  role: "bot",
  kind: "text",
  text: "Hi! I'm QuntumMines, your Fake News Detector.\nYou can ask me anything, share a news claim, or just chat!\nHow can I help you today?",
  time: now(),
};

export default function App() {
  const [view, setView] = useState("chat");
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(true);
  const [history, setHistory] = useState(() => load("qm:history", []));
  const [settings, setSettings] = useState(() => load("qm:settings", { saveHistory: true }));
  const scroller = useRef(null);

  useEffect(() => save("qm:settings", settings), [settings]);
  useEffect(() => {
    if (settings.saveHistory) save("qm:history", history);
  }, [history, settings.saveHistory]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, view]);

  // Donut numbers: the reference values until real claims have been checked.
  const stats = useMemo(() => {
    if (history.length < 3) return { reliable: 68, fake: 32 };
    const real = history.filter((h) => h.verdict === "real").length;
    const reliable = Math.round((real / history.length) * 100);
    return { reliable, fake: 100 - reliable };
  }, [history]);

  function handleClear() {
    setMessages([{ ...WELCOME, time: now() }]);
    setInput("");
    setFile(null);
  }

  async function handleSend(text) {
    const clean = text.trim();
    if ((!clean && !file) || busy) return;
    const attached = file;

    setMessages((m) => [...m, { id: id(), role: "user", kind: "text", text: clean || attached.name, time: now() }]);
    setInput("");
    setFile(null);
    setBusy(true);

    try {
      const res = await sendMessage(clean, attached);
      setOnline(true);
      if (res.type === "analysis") {
        setMessages((m) => [
          ...m,
          { id: id(), role: "bot", kind: "analysis", text: res.intro, data: res, time: now() },
        ]);
        setHistory((h) => [{ id: id(), claim: clean, verdict: res.verdict, time: now() }, ...h].slice(0, 50));
      } else {
        setMessages((m) => [...m, { id: id(), role: "bot", kind: "text", text: res.text, time: now() }]);
      }
    } catch (err) {
      setOnline(false);
      setMessages((m) => [
        ...m,
        {
          id: id(),
          role: "bot",
          kind: "text",
          text: "I couldn't reach the server. Check that the backend is running, then send your message again.",
          time: now(),
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <Sidebar view={view} setView={setView} online={online} />

      <div className="center">
        <Header />

        <main className="panel chat">
          <div className="scroller" ref={scroller}>
            {view === "chat" && (
              <>
                {messages.map((m) => (
                  <Message key={m.id} m={m} />
                ))}
                {busy && <Typing />}
              </>
            )}
            {view === "history" && (
              <HistoryView history={history} onClear={() => setHistory([])} onOpen={() => setView("chat")} />
            )}
            {view === "about" && <AboutView />}
            {view === "settings" && <SettingsView settings={settings} setSettings={setSettings} />}
          </div>
        </main>

        <Composer value={input} setValue={setInput} onSend={handleSend} busy={busy} file={file} setFile={setFile} onClear={handleClear} canClear={messages.length > 1 && !busy} />
      </div>

      <RightPanel reliable={stats.reliable} fake={stats.fake} />
    </div>
  );
}
