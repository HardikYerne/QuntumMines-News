/**
 * ────────────────────────────────────────────────────────────────
 *  THE ONLY FILE THAT TALKS TO YOUR BACKEND
 * ────────────────────────────────────────────────────────────────
 *  Your backend logic is untouched. The UI calls `sendMessage(text)`
 *  and expects back one of two shapes (both are produced by
 *  `normalize()` below, so map your backend's JSON there):
 *
 *   1) Plain chat reply
 *      { type: "text", text: "..." }
 *
 *   2) Claim analysis
 *      {
 *        type: "analysis",
 *        intro: "I've analyzed this claim. Here are the results:",
 *        verdict: "fake" | "real" | "uncertain",
 *        summary: "This claim is not supported by ...",
 *        confidenceTrue: 18,      // % that the claim is true
 *        confidenceFalse: 82,     // % that the claim is false
 *        explanation: "...",
 *        corrected: "..."
 *      }
 */

const API_URL =
  import.meta.env.VITE_API_URL ||
  (typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://127.0.0.1:8000/api/analyze"
    : "/api/analyze");

/** ▼ EDIT THIS to match whatever JSON your backend already returns ▼ */
function normalize(data) {
  // Already in the UI shape
  if (data?.type === "analysis" || data?.type === "text") return data;

  // Example mapping for a typical fake-news backend response.
  // Rename the right-hand keys to match your API.
  const label = String(data?.label ?? data?.verdict ?? "").toLowerCase();
  if (label) {
    const fake = /fake|false|misinfo/.test(label);
    const real = /real|true|reliable/.test(label);
    const conf = Number(data.confidence ?? data.score ?? 0);
    const pct = conf <= 1 ? Math.round(conf * 100) : Math.round(conf);
    const confFalse = fake ? pct : real ? 100 - pct : 50;
    return {
      type: "analysis",
      intro: "I've analyzed this claim. Here are the results:",
      verdict: fake ? "fake" : real ? "real" : "uncertain",
      summary:
        data.summary ??
        (fake
          ? "This claim is not supported by credible evidence."
          : real
          ? "This claim is supported by credible sources."
          : "There isn't enough evidence to decide either way."),
      confidenceTrue: 100 - confFalse,
      confidenceFalse: confFalse,
      explanation: data.explanation ?? "",
      corrected: data.corrected ?? data.corrected_version ?? "",
    };
  }

  return { type: "text", text: data?.reply ?? data?.response ?? data?.message ?? String(data) };
}

/** Send a message (and optional attached file) to the backend. */
export async function sendMessage(text, file) {
  const payload = { text: String(text ?? "").trim() };

  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail = "";
    try {
      const errorData = await res.json();
      detail = errorData?.detail ? `: ${errorData.detail}` : "";
    } catch {
      // Ignore non-JSON error responses.
    }
    throw new Error(`Server responded with ${res.status}${detail}`);
  }

  return normalize(await res.json());
}

/* Offline demo so the UI works before the backend is connected. */
async function demoReply(text) {
  await new Promise((r) => setTimeout(r, 900));
  const t = text.toLowerCase();
  if (/what is fake news/.test(t))
    return {
      type: "text",
      text: "Fake news is false or misleading information presented as fact, usually to mislead people, get clicks, or influence opinion.",
    };
  if (/how do you work/.test(t))
    return {
      type: "text",
      text: "I compare your claim against credible sources, score how well the evidence supports it, and explain the result in plain language.",
    };
  if (/tips/.test(t))
    return {
      type: "text",
      text: "Check the source, look for evidence, be skeptical of sensational claims, verify with trusted outlets, and think before you share.",
    };
  if (/cure|miracle|hoax|secret/.test(t))
    return {
      type: "analysis",
      intro: "I've analyzed this claim. Here are the results:",
      verdict: "fake",
      summary: "This claim is not supported by credible scientific evidence.",
      confidenceTrue: 18,
      confidenceFalse: 82,
      explanation:
        "There is no reliable scientific evidence for this claim. While the ingredient or habit may have some health benefits, it is not a proven treatment or cure.",
      corrected:
        "It may be a healthy habit, but it cannot cure the condition. Treatment requires proper medical care from qualified health professionals.",
    };
  return { type: "text", text: "Thanks for the message. Share a news claim and I'll analyze it for you." };
}
