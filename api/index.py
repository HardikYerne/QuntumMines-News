import os
import json
import re
import requests
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---- Config ----
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
    "1. Evidence below comes from retrieved public news results.\n"
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
    "10. Never say 'I couldn't find reliable sources' unless the application "
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


def extract_search_query(user_text: str) -> str:
    """Create a short search query without changing the original claim."""
    text = re.sub(r"\s+", " ", user_text.strip())

    # Remove common request prefixes so the search focuses on the claim.
    text = re.sub(
        r"^(is it true that|is this true|fact check|fact-check|check this|verify this)\s*[:,-]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Keep the query reasonably short for Google News RSS.
    words = text.split()
    return " ".join(words[:45])


def fetch_news_evidence(user_text: str, max_results: int = 6) -> list[dict]:
    """
    Retrieve public news-search results through Google News RSS.
    Failure is non-fatal; the LLM can then return UNVERIFIABLE.
    """
    query = extract_search_query(user_text)
    if not query:
        return []

    params = {
        "q": query,
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    }

    try:
        response = requests.get(
            NEWS_RSS_URL,
            params=params,
            timeout=12,
            headers={"User-Agent": "QuntumMines-FakeNewsDetector/1.0"},
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        results = []

        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()

            if title:
                results.append(
                    {
                        "title": title,
                        "description": description,
                        "published": pub_date,
                        "url": link,
                    }
                )

        return results

    except Exception:
        # Do not turn a search/network problem into a fake/real verdict.
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
                    "Analyze the user claim using only the supplied evidence "
                    "and your general reasoning. Return JSON only."
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
        r"^```(?:json)?|```$",
        "",
        content.strip(),
        flags=re.MULTILINE,
    ).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
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
