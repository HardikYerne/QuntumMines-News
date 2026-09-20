import { User } from "lucide-react";
import bot from "../assets/bot.png";
import ResultCard from "./ResultCard.jsx";

export default function Message({ m }) {
  if (m.role === "user") {
    return (
      <div className="msg user">
        <div className="msg-body">
          <div className="bubble user-bubble">{m.text}</div>
          <time>{m.time}</time>
        </div>
        <span className="user-avatar">
          <User size={26} strokeWidth={2.2} />
        </span>
      </div>
    );
  }

  return (
    <div className="msg bot">
      <img src={bot} alt="QuntumMines" className="bot-avatar" />
      <div className="msg-body">
        <div className="bubble bot-bubble">{m.text}</div>
        <time>{m.time}</time>
      </div>
      {m.kind === "analysis" && <ResultCard data={m.data} />}
    </div>
  );
}

export function Typing() {
  return (
    <div className="msg bot">
      <img src={bot} alt="" className="bot-avatar" />
      <div className="msg-body">
        <div className="bubble bot-bubble typing" aria-label="QuntumMines is typing">
          <i /> <i /> <i />
        </div>
      </div>
    </div>
  );
}
