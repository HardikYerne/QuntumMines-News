import { useRef } from "react";
import { Paperclip, Send, Search, MessageCircle, Settings, Lightbulb, X, Trash2 } from "lucide-react";

const QUICK = [
  { label: "Analyze News", Icon: Search, action: "focus" },
  { label: "What is Fake News?", Icon: MessageCircle, action: "send" },
  { label: "How do you work?", Icon: Settings, action: "send" },
  { label: "Give me tips", Icon: Lightbulb, action: "send" },
];

export default function Composer({ value, setValue, onSend, busy, file, setFile, onClear, canClear }) {
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  const submit = (e) => {
    e.preventDefault();
    onSend(value);
  };

  return (
    <div className="panel composer">
      {file && (
        <div className="file-chip">
          {file.name}
          <button type="button" onClick={() => setFile(null)} aria-label="Remove attachment">
            <X size={14} />
          </button>
        </div>
      )}

      <form className="composer-row" onSubmit={submit}>
        <button type="button" className="icon-btn" onClick={() => fileRef.current?.click()} aria-label="Attach a file">
          <Paperclip size={26} strokeWidth={1.6} />
        </button>
        <input
          ref={fileRef}
          type="file"
          hidden
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <input
          ref={inputRef}
          className="text-input"
          placeholder="Type your message here..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label="Message"
        />
        <button className="send" type="submit" disabled={busy || (!value.trim() && !file)}>
          <Send size={22} strokeWidth={1.8} /> Send
        </button>
      </form>

      <div className="chips">
        {QUICK.map(({ label, Icon, action }) => (
          <button
            key={label}
            type="button"
            className="chip"
            disabled={busy}
            onClick={() => (action === "send" ? onSend(label) : inputRef.current?.focus())}
          >
            <Icon size={20} strokeWidth={1.6} /> {label}
          </button>
        ))}
        <button type="button" className="chip clear" title="Clear chat" aria-label="Clear chat" onClick={onClear} disabled={!canClear}>
          <Trash2 size={20} strokeWidth={1.6} />
        </button>
      </div>
    </div>
  );
}
