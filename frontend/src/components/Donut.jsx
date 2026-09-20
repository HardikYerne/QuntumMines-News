export default function Donut({ value, color, size = 108, stroke = 9, label, font = 28 }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={label || `${v}%`}
      className="donut"
    >
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1b2c3f" strokeWidth={stroke} />
      {v > 0 && <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${(c * v) / 100} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 5px ${color}88)`, transition: "stroke-dasharray .6s ease" }}
      />}
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        fill={color}
        fontFamily="Rajdhani, sans-serif"
        fontWeight="700"
        fontSize={font}
      >
        {Math.round(v)}%
      </text>
    </svg>
  );
}
