import os
import json
import re
import html
import requests
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_LLM_MODEL = os.environ.get(
    "HF_LLM_MODEL",
    "meta-llama/Llama-3.1-8B-Instruct",
)

HF_API_URL = "https://router.huggingface.co/v1/chat/completions"

# Google News RSS is used only to retrieve current public evidence.
# No API key is required.
NEWS_RSS_URL = "https://news.google.com/rss/search"

app = FastAPI(title="Fake News Detector Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str


SYSTEM_PROMPT = (
    "You are QuntumMines, a fake-news detection assistant.\n\n"
    "You have two modes.\n\n"
    "GENERAL CONVERSATION:\n"
    "For greetings, casual conversation, general questions, or questions "
    "about your capabilities, respond naturally. Do not classify these as news.\n\n"
    "NEWS ANALYSIS:\n"
    "When the user provides a news claim, headline, news snippet, social-media "
    "claim, or asks whether information is true, fake, misleading, or credible, "
    "analyze the claim using the evidence supplied by the application.\n\n"
    "IMPORTANT EVIDENCE RULES:\n"
    "1. Evidence below comes from dynamically retrieved public sources.\n"
    "2. Do not claim that you personally browsed, searched, or verified anything.\n"
    "3. Do not invent sources, facts, dates, or evidence.\n"
    "4. If the supplied evidence does not establish the claim, use UNVERIFIABLE.\n"
    "5. Do not call a claim fake merely because no search result was found.\n"
    "6. Confidence must represent confidence in the verdict, not confidence "
    "that the article exists.\n"
    "7. For REAL, require meaningful supporting evidence from the retrieved results.\n"
    "8. For LIKELY FAKE, require meaningful contradictory evidence or a clear "
    "internal factual contradiction.\n"
    "9. Otherwise return UNVERIFIABLE.\n"
    "10. When a claim says that a person currently holds a public office, "
    "compare the claimed person with evidence identifying the current office-holder. "
    "If reliable retrieved evidence identifies a different current office-holder, "
    "that is meaningful contradictory evidence and the claim should be classified "
    "as LIKELY FAKE.\n"
    "11. Do not treat absence of a person's name in search results as proof that "
    "the person does not hold an office. Use explicit contradictory evidence when available.\n"
    "12. Prefer current and authoritative evidence when the claim concerns a "
    "current office, current role, current event, or other time-sensitive fact.\n"
    "13. Never say 'I couldn't find reliable sources' unless the application "
    "actually supplied no useful evidence. Prefer 'The retrieved evidence is "
    "insufficient to establish the claim.'\n\n"
    "For GENERAL CONVERSATION, return only valid JSON:\n"
    "{\n"
    '  "type": "general",\n'
    '  "response": "<string>"\n'
    "}\n\n"
    "For NEWS ANALYSIS, return only valid JSON:\n"
    "{\n"
    '  "type": "news_analysis",\n'
    '  "verdict": "REAL" | "LIKELY FAKE" | "UNVERIFIABLE",\n'
    '  "confidence": <integer 0-100>,\n'
    '  "explanation": "<string>",\n'
    '  "corrected_version": "<string>"\n'
    "}\n\n"
    "Do not use markdown fences and do not add text outside the JSON."
)

GREETING_RESPONSES = {
    "hi": "Hi! How can I help you today?",
    "hello": "Hello! How can I help you today?",
    "hey": "Hey! How can I help you today?",
    "hii": "Hi! How can I help you today?",
    "hiii": "Hi! How can I help you today?",
    "good morning": "Good morning! How can I help you today?",
    "good afternoon": "Good afternoon! How can I help you today?",
    "good evening": "Good evening! How can I help you today?",
}


def get_local_general_response(user_text: str):
    normalized = re.sub(r"\s+", " ", user_text.strip().lower())
    return GREETING_RESPONSES.get(normalized)


def clean_search_text(user_text: str) -> str:
    text = re.sub(r"\s+", " ", user_text.strip())

    text = re.sub(
        r"^(is it true that|is this true|fact check|fact-check|check this|verify this)\s*[:,-]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text


def extract_search_queries(user_text: str) -> list[str]:
    """Build multiple dynamic search queries without storing individual news."""
    text = clean_search_text(user_text)
    if not text:
        return []

    words = text.split()
    queries = [" ".join(words[:45])]
    normalized = text.lower()

    # For public-office claims, search for the office holder itself as well
    # as the original claim. This is what prevents a claim about an unknown
    # person from becoming UNVERIFIABLE merely because their name has little
    # news coverage.
    office_terms = [
        "prime minister", "pm", "president", "vice president",
        "chief minister", "cm", "governor", "minister", "mayor",
        "chief justice", "chairman", "director", "ceo"
    ]
    office = next((x for x in office_terms if re.search(rf"\b{re.escape(x)}\b", normalized)), None)

    countries = [
        "india", "united states", "usa", "united kingdom", "uk",
        "canada", "australia"
    ]
    country = next((x for x in countries if x in normalized), None)

    if office:
        if country:
            queries.append(f"current {office} of {country}")
            queries.append(f"{office} {country} current office holder")
        else:
            queries.append(f"current {office}")

        # Government-domain searches are useful for official/current roles.
        if country == "india":
            if office in {"prime minister", "pm"}:
                queries.append("site:pmindia.gov.in current Prime Minister of India")
            elif office in {"president"}:
                queries.append("site:presidentofindia.nic.in current President of India")
            else:
                queries.append(f"site:gov.in current {office} India")

    if any(term in normalized for term in ("today", "current", "currently", "latest", "announced", "announces")):
        queries.append(f"{text[:160]} latest")

    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


def source_domain(url: str) -> str:
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        return hostname[4:] if hostname.startswith("www.") else hostname
    except Exception:
        return ""


def source_score(item: dict) -> int:
    """Rank evidence only; this function never decides the verdict."""
    domain = source_domain(item.get("url", ""))
    title = (item.get("title") or "").lower()
    description = (item.get("description") or "").lower()

    score = 0
    authoritative = {
        "pmindia.gov.in", "presidentofindia.nic.in", "india.gov.in",
        "nasa.gov", "who.int", "un.org", "rbi.org.in", "eci.gov.in"
    }

    if domain in authoritative or domain.endswith(".gov.in") or domain.endswith(".gov"):
        score += 100
    elif domain.endswith(".nic.in"):
        score += 90

    if any(term in title or term in description for term in (
        "current", "prime minister", "president", "chief minister",
        "appointed", "elected", "official", "government"
    )):
        score += 15

    return score


def normalize_evidence_item(item: dict) -> dict:
    title = html.unescape((item.get("title") or "").strip())
    description = html.unescape((item.get("description") or "").strip())
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "title": title,
        "description": description,
        "published": (item.get("published") or "").strip(),
        "url": (item.get("url") or "").strip(),
    }


def fetch_news_evidence(user_text: str, max_results: int = 10) -> list[dict]:
    """Dynamically retrieve and rank current public evidence from Google News RSS."""
    queries = extract_search_queries(user_text)
    if not queries:
        return []

    results = []
    seen_urls = set()

    try:
        for query in queries:
            params = {
                "q": query,
                "hl": "en-IN",
                "gl": "IN",
                "ceid": "IN:en",
            }

            response = requests.get(
                NEWS_RSS_URL,
                params=params,
                timeout=12,
                headers={"User-Agent": "QuntumMines-FakeNewsDetector/1.0"},
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                description = (item.findtext("description") or "").strip()

                if not title or not link or link in seen_urls:
                    continue

                seen_urls.add(link)
                results.append(normalize_evidence_item({
                    "title": title,
                    "description": description,
                    "published": pub_date,
                    "url": link,
                }))

        results.sort(key=source_score, reverse=True)
        return results[:max_results]

    except Exception:
        # Search/network failure must not automatically become a fake/real verdict.
        return []


def build_evidence_text(evidence: list[dict]) -> str:
    if not evidence:
        return (
            "NO_RETRIEVED_EVIDENCE\n"
            "The application could not retrieve usable public news results. "
            "Do not claim that the web was successfully searched."
        )

    chunks = []
    for index, item in enumerate(evidence, start=1):
        chunks.append(
            f"[Source {index}]\n"
            f"Domain: {source_domain(item.get('url', ''))}\n"
            f"Title: {item['title']}\n"
            f"Published: {item['published']}\n"
            f"Description: {item['description']}\n"
            f"URL: {item['url']}"
        )

    return "\n\n".join(chunks)


def call_hf_llm(user_text: str, evidence: list[dict]) -> dict:
    if not HF_TOKEN:
        return {
            "type": "news_analysis",
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "explanation": (
                "Server is missing HF_TOKEN. Set the Hugging Face access token "
                "in the environment variables to enable analysis."
            ),
            "corrected_version": user_text,
        }

    evidence_text = build_evidence_text(evidence)

    payload = {
        "model": HF_LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "USER CLAIM:\n"
                    f'"""\n{user_text}\n"""\n\n'
                    "RETRIEVED EVIDENCE:\n"
                    f"{evidence_text}\n\n"
                    "Analyze the user claim using the supplied evidence and "
                    "general reasoning. For current public-office claims, explicitly "
                    "compare the claimed person with the current office-holder shown "
                    "by the evidence. Return JSON only."
                ),
            },
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        HF_API_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content.strip(),
        flags=re.IGNORECASE,
    ).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                parsed = None
        else:
            parsed = None

        if not isinstance(parsed, dict):
            return {
                "type": "news_analysis",
                "verdict": "UNVERIFIABLE",
                "confidence": 0,
                "explanation": (
                    "The analysis model returned an invalid response format, "
                    "so the claim could not be classified safely."
                ),
                "corrected_version": user_text,
            }

    if parsed.get("type") == "general":
        return {
            "type": "general",
            "response": parsed.get("response", ""),
        }

    verdict = str(parsed.get("verdict", "UNVERIFIABLE")).upper()
    if verdict not in {"REAL", "LIKELY FAKE", "UNVERIFIABLE"}:
        verdict = "UNVERIFIABLE"

    try:
        confidence = int(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0

    confidence = max(0, min(100, confidence))

    return {
        "type": "news_analysis",
        "verdict": verdict,
        "confidence": confidence,
        "explanation": parsed.get("explanation", ""),
        "corrected_version": parsed.get(
            "corrected_version",
            user_text,
        ),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "model": HF_LLM_MODEL}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    text = (req.text or "").strip()

    if not text:
        return {
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "explanation": "Please provide some news text to analyze.",
            "corrected_version": "",
        }

    # Greetings never go through the news classifier.
    local_response = get_local_general_response(text)
    if local_response:
        return {
            "type": "general",
            "response": local_response,
            "verdict": "GENERAL",
            "confidence": 100,
            "explanation": local_response,
            "corrected_version": "",
        }

    try:
        evidence = fetch_news_evidence(text)
        result = call_hf_llm(text, evidence)

        if result.get("type") == "general":
            return {
                "type": "general",
                "response": result.get("response", ""),
                "verdict": "GENERAL",
                "confidence": 100,
                "explanation": result.get("response", ""),
                "corrected_version": "",
            }

        return result

    except requests.exceptions.HTTPError as e:
        return {
            "type": "news_analysis",
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "explanation": f"Hugging Face API error: {e}",
            "corrected_version": text,
        }

    except Exception as e:
        return {
            "type": "news_analysis",
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "explanation": f"Unexpected error: {e}",
            "corrected_version": text,
        }
