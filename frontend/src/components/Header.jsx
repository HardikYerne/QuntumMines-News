import globe from "../assets/globe.png";

export default function Header() {
  return (
    <header className="panel header">
      <div className="header-globe" style={{ backgroundImage: `url(${globe})` }} aria-hidden="true" />
      <div className="header-titles">
        <h1>FAKE NEWS DETECTOR</h1>
        <p className="header-sub">AI CHATBOT</p>
      </div>
      <div className="header-motto">
        <span>REAL FACTS</span>
        <span>SAFER MINDS</span>
        <span>A BETTER TOMORROW</span>
      </div>
    </header>
  );
}
