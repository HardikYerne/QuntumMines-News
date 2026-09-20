import os
import json
import re
import html
import requests
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from html.parser import HTMLParser


class _ArticleHTMLParser(HTMLParser):
    """Small stdlib-only HTML extractor for publisher pages."""

    SKIP_TAGS = {
        "script", "style", "noscript", "svg", "nav", "footer",
        "header", "form", "aside", "iframe"
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.in_title = False
        self.in_meta = False
        self.meta_attrs = {}
        self.paragraphs = []
        self.title_parts = []
        self.current_parts = []
        self.current_tag = None
        self.description = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = True

        if tag == "meta":
            name = (attrs.get("name") or "").lower()
            prop = (attrs.get("property") or "").lower()
            content = (attrs.get("content") or "").strip()
            if content and (
                name in {"description", "twitter:description"}
                or prop == "og:description"
            ) and not self.description:
                self.description = content

        if tag in {"p", "h2", "h3"}:
            self.current_parts = []
            self.current_tag = tag

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = False

        if tag in {"p", "h2", "h3"} and self.current_tag == tag:
            value = re.sub(r"\s+", " ", " ".join(self.current_parts)).strip()
            if len(value) >= 35:
                self.paragraphs.append(value)
            self.current_parts = []
            self.current_tag = None

    def handle_data(self, data):
        if self.skip_depth:
            return

        if self.in_title:
            self.title_parts.append(data)

        if self.current_tag:
            self.current_parts.append(data)


def parse_html_evidence(html_text: str) -> tuple[str, str, str]:
    parser = _ArticleHTMLParser()
    parser.feed(html_text)
    parser.close()

    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    description = re.sub(r"\s+", " ", parser.description).strip()

    seen = set()
    paragraphs = []
    for paragraph in parser.paragraphs:
        key = paragraph.lower()
        if key not in seen:
            seen.add(key)
            paragraphs.append(paragraph)

    return title[:500], description[:1500], "\n".join(paragraphs)[:12000]


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
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

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
    "3. Do not invent sources, facts, dates, numbers, or evidence.\n"
    "4. If the supplied evidence does not establish the claim, use UNVERIFIABLE.\n"
    "5. Do not call a claim fake merely because no search result was found.\n"
    "6. Confidence must represent confidence in the verdict, not confidence that an article exists.\n"
    "7. For REAL, require meaningful supporting evidence from the retrieved results.\n"
    "8. For LIKELY FAKE, require meaningful contradictory evidence or a clear internal factual contradiction.\n"
    "9. Otherwise return UNVERIFIABLE.\n"
    "10. Use retrieved evidence, not memorized facts, as the primary basis for the verdict.\n"
    "11. Multiple independent sources agreeing on the same material facts strengthen the evidence, but source count alone is not proof.\n"
    "12. Compare the actual facts, dates, numbers, units, subjects, and context. Do not require identical wording.\n"
    "13. If sources conflict, explain the conflict and prefer the most direct and authoritative evidence available.\n"
    "14. For numerical claims, compare exact numbers, dates, units, and subjects.\n"
    "15. A related article discussing the same topic but different numbers is not sufficient to prove or disprove the claim.\n"
    "16. For claims containing multiple facts, evaluate each material fact separately.\n"
    "17. When a claim says a person currently holds a public office, compare the claimed person with evidence identifying the current office-holder. If reliable retrieved evidence identifies a different current office-holder, that is meaningful contradictory evidence.\n"
    "18. Do not treat absence of a person's name in search results as proof that the person does not hold an office.\n"
    "19. Prefer current evidence for current events and other time-sensitive facts.\n"
    "20. If the application supplied usable evidence, do not say that no public results were found. Explain what the retrieved evidence does or does not establish.\n\n"
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
    """Generate dynamic searches without storing individual news."""
    text = clean_search_text(user_text)
    if not text:
        return []

    queries = [" ".join(text.split()[:45])]

    tokens = meaningful_tokens(text)
    if tokens:
        queries.append(" ".join(tokens[:24]))

    numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", text)
    if numbers and tokens:
        queries.append(" ".join(tokens[:18]) + " " + " ".join(numbers[:6]))

    normalized = text.lower()

    office_terms = [
        "prime minister", "pm", "president", "vice president",
        "chief minister", "cm", "governor", "minister", "mayor",
        "chief justice", "chairman", "director", "ceo",
    ]
    office = next(
        (x for x in office_terms if re.search(rf"\b{re.escape(x)}\b", normalized)),
        None,
    )

    countries = [
        "india", "united states", "usa", "united kingdom",
        "uk", "canada", "australia",
    ]
    country = next((x for x in countries if x in normalized), None)

    if office:
        queries.append(
            f"current {office} of {country}" if country
            else f"current {office}"
        )
        if country:
            queries.append(f"{office} {country} current office holder")
        if country == "india":
            if office in {"prime minister", "pm"}:
                queries.append("site:pmindia.gov.in current Prime Minister of India")
            elif office == "president":
                queries.append(
                    "site:presidentofindia.nic.in current President of India"
                )
            else:
                queries.append(f"site:gov.in current {office} India")

    if any(
        x in normalized
        for x in ("today", "current", "currently", "latest", "announced", "announces")
    ):
        queries.append(f"{text[:160]} latest")

    # Dynamic source-oriented searches. These do not contain any claim-specific
    # facts; they improve recall when one news index misses the story.
    source_domains = [
        "reuters.com",
        "thehindu.com",
        "indianexpress.com",
        "hindustantimes.com",
        "timesofindia.indiatimes.com",
        "economictimes.indiatimes.com",
    ]
    for domain in source_domains[:4]:
        queries.append(f"{text[:180]} site:{domain}")

    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))



def normalize_evidence_item(item: dict) -> dict:
    """Normalize dynamically retrieved evidence without storing news facts."""
    return {
        "title": str(item.get("title") or "").strip(),
        "description": str(item.get("description") or "").strip(),
        "published": str(item.get("published") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "content": str(item.get("content") or "").strip(),
    }


def source_domain(url: str) -> str:
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        return hostname[4:] if hostname.startswith("www.") else hostname
    except Exception:
        return ""


def meaningful_tokens(text: str) -> list[str]:
    """Extract useful words while preserving numbers and years."""
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "on", "at", "for", "from", "by", "with", "and", "or",
        "as", "that", "this", "it", "its", "has", "have", "had", "will", "would",
        "can", "could", "may", "might", "should", "do", "does", "did", "than",
        "then", "over", "after", "before", "into", "about", "according", "said",
        "says", "claim", "claims", "news", "report", "reported",
    }
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]*|\d+(?:\.\d+)?%?", text.lower())
    return [t for t in tokens if t not in stopwords and len(t) > 1]


def source_quality_score(item: dict) -> int:
    """Rank source quality only; this never decides the verdict."""
    domain = source_domain(item.get("url", ""))
    if domain in {"news.google.com", "google.com"}:
        domain = source_domain(item.get("publisher", ""))
    authoritative = {
        "pmindia.gov.in", "presidentofindia.nic.in", "india.gov.in",
        "rbi.org.in", "eci.gov.in", "nasa.gov", "who.int", "un.org",
    }
    if domain in authoritative:
        return 100
    if domain.endswith(".gov.in") or domain.endswith(".gov"):
        return 95
    if domain.endswith(".nic.in"):
        return 90
    if domain.endswith(".org"):
        return 50
    return 10


def evidence_relevance_score(item: dict, claim: str) -> float:
    """Score evidence using title, description, and fetched article text."""
    claim_tokens = set(meaningful_tokens(claim))
    if not claim_tokens:
        return 0.0

    title = (item.get("title") or "").lower()
    description = (item.get("description") or "").lower()
    content = (item.get("content") or "").lower()
    combined = f"{title} {description} {content}"

    body_matches = sum(1 for token in claim_tokens if token in combined)
    title_matches = sum(1 for token in claim_tokens if token in title)
    coverage = body_matches / len(claim_tokens)
    title_coverage = title_matches / len(claim_tokens)

    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim.lower()))
    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", combined))
    number_match = (
        len(claim_numbers & evidence_numbers) / len(claim_numbers)
        if claim_numbers else 0.0
    )

    score = (
        coverage * 0.45
        + title_coverage * 0.15
        + number_match * 0.30
        + (0.10 if source_quality_score(item) >= 90 else 0.0)
    )
    return min(score, 1.0)




def resolve_publisher_url(url: str) -> str:
    """Compatibility helper for callers that need a resolved URL."""
    if not url:
        return url
    try:
        response = requests.get(
            url,
            timeout=4,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 QuntumMines-FakeNewsDetector/1.0"},
            stream=True,
        )
        return response.url or url
    except Exception:
        return url


def extract_article_text(html_text: str) -> tuple[str, str, str]:
    """Extract generic publisher-page title, description, and article text."""
    return parse_html_evidence(html_text)


def fetch_article_evidence(item: dict) -> dict:
    """
    Fetch one dynamically discovered article.
    The original RSS/GDELT metadata is retained even when the publisher page
    cannot be fetched.
    """
    result = dict(item)
    original_url = item.get("url", "")
    if not original_url:
        return result

    try:
        response = requests.get(
            original_url,
            timeout=6,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/153 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()

        final_url = response.url or original_url
        content_type = response.headers.get("content-type", "").lower()

        if "html" not in content_type:
            result["publisher"] = source_domain(final_url)
            result["article_fetched"] = False
            return result

        page_title, page_description, article_content = extract_article_text(
            response.text
        )

        # Do NOT replace a useful news headline with a generic publisher
        # <title>. Keep the original discovery title as evidence.
        if page_description and len(page_description) > len(result.get("description", "")):
            result["description"] = page_description

        if article_content:
            result["content"] = article_content

        result["url"] = final_url
        result["publisher"] = source_domain(final_url)
        result["article_fetched"] = bool(article_content)
        result["original_url"] = original_url
        return result

    except Exception as exc:
        print(f"[retrieval] article fetch failed url={original_url!r}: {exc}")
        result["publisher"] = source_domain(original_url)
        result["article_fetched"] = False
        return result


def fetch_gdelt_evidence(
    query: str,
    max_records: int = 20,
) -> list[dict]:
    """Retrieve current articles dynamically from GDELT."""
    try:
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max_records,
            "timespan": "3months",
            "sort": "datedesc",
        }

        response = requests.get(
            GDELT_DOC_URL,
            params=params,
            timeout=15,
            headers={"User-Agent": "QuntumMines-FakeNewsDetector/1.0"},
        )
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])
        if not isinstance(articles, list):
            return []

        evidence = []
        for article in articles:
            url = (article.get("url") or "").strip()
            title = (article.get("title") or "").strip()
            if not url or not title:
                continue

            evidence.append(
                normalize_evidence_item(
                    {
                        "title": title,
                        "description": "",
                        "published": article.get("seendate") or "",
                        "url": url,
                        "content": "",
                    }
                )
            )

        return evidence

    except (requests.RequestException, ValueError, TypeError):
        return []
    except Exception:
        return []



def fetch_google_news_evidence(query: str, max_records: int = 12) -> list[dict]:
    """Retrieve current news metadata from Google News RSS."""
    try:
        params = {
            "q": query,
            "hl": "en-IN",
            "gl": "IN",
            "ceid": "IN:en",
        }
        response = requests.get(
            NEWS_RSS_URL,
            params=params,
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0 QuntumMines-FakeNewsDetector/1.0"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)

        evidence = []
        for item in root.findall(".//item")[:max_records]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = html.unescape(item.findtext("description") or "")
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

            source_node = item.find("source")
            source_name = (
                (source_node.text or "").strip()
                if source_node is not None else ""
            )

            if not title or not link:
                continue

            evidence.append(normalize_evidence_item({
                "title": title,
                "description": description,
                "published": pub_date,
                "url": link,
                "content": "",
                "publisher": source_name,
            }))
        return evidence
    except Exception as exc:
        print(f"[retrieval] Google News failed for query={query!r}: {exc}")
        return []


def collect_dynamic_evidence(user_text: str) -> list[dict]:
    """
    Dynamically collect evidence from multiple independent discovery channels.
    Retrieval is parallelized so a slow source does not make the serverless
    request return an empty evidence set.
    """
    queries = extract_search_queries(user_text)
    if not queries:
        return []

    results = []
    seen_urls = set()

    # Keep the dynamic query set broad, but bounded for serverless execution.
    discovery_queries = queries[:8]

    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for query in discovery_queries:
            jobs.append(executor.submit(fetch_google_news_evidence, query, 12))
            jobs.append(executor.submit(fetch_gdelt_evidence, query, 12))

        for future in as_completed(jobs):
            try:
                items = future.result()
            except Exception as exc:
                print(f"[retrieval] discovery worker failed: {exc}")
                continue

            for item in items:
                url = (item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append(item)

    print(f"[retrieval] discovered {len(results)} unique results for claim")

    return results


def fetch_news_evidence(
    user_text: str,
    max_results: int = 12,
) -> list[dict]:
    """
    Discover current evidence dynamically, rank it, and fetch a bounded number
    of publisher pages in parallel. RSS/GDELT metadata remains usable even if
    a publisher page cannot be fetched.
    """
    results = collect_dynamic_evidence(user_text)
    if not results:
        return []

    # Rank discovery metadata first. This is important because publisher-page
    # fetching can fail on Vercel and must not erase useful RSS/GDELT evidence.
    for item in results:
        item["_relevance"] = evidence_relevance_score(item, user_text)

    results.sort(
        key=lambda item: (
            item.get("_relevance", 0.0),
            source_quality_score(item),
        ),
        reverse=True,
    )

    # Keep enough candidates to obtain multiple independent publishers without
    # making dozens of serial outbound requests.
    candidates = results[:24]

    from concurrent.futures import ThreadPoolExecutor, as_completed

    fetched = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(fetch_article_evidence, item): item
            for item in candidates
        }

        for future in as_completed(future_map):
            original = future_map[future]
            try:
                item = future.result()
            except Exception as exc:
                print(f"[retrieval] publisher fetch failed: {exc}")
                item = dict(original)

            # Never lose the original discovery metadata.
            if not item.get("title"):
                item["title"] = original.get("title", "")
            if not item.get("description"):
                item["description"] = original.get("description", "")
            if not item.get("published"):
                item["published"] = original.get("published", "")
            if not item.get("url"):
                item["url"] = original.get("url", "")
            if "content" not in item:
                item["content"] = ""

            item["_relevance"] = evidence_relevance_score(item, user_text)
            fetched.append(item)

    fetched.sort(
        key=lambda item: (
            item.get("_relevance", 0.0),
            source_quality_score(item),
        ),
        reverse=True,
    )

    selected = []
    domain_counts = {}

    for item in fetched:
        domain = source_domain(item.get("url", "")) or "unknown"
        if domain_counts.get(domain, 0) >= 2:
            continue
        selected.append(item)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if len(selected) >= max_results:
            break

    # Fill remaining slots if diversity alone was too restrictive.
    if len(selected) < max_results:
        selected_urls = {item.get("url") for item in selected}
        for item in fetched:
            if item.get("url") in selected_urls:
                continue
            selected.append(item)
            if len(selected) >= max_results:
                break

    print(
        f"[retrieval] selected {len(selected)} evidence items; "
        f"top relevance={[round(x.get('_relevance', 0), 3) for x in selected[:5]]}"
    )
    return selected


def has_usable_evidence(evidence: list[dict], claim: str) -> bool:
    """Check whether dynamic retrieval produced substantively relevant evidence."""
    if not evidence:
        return False

    for item in evidence:
        relevance = evidence_relevance_score(item, claim)
        content = (
            f"{item.get('title', '')} "
            f"{item.get('description', '')} "
            f"{item.get('content', '')}"
        ).strip()
        if content and relevance >= 0.15:
            return True

    return False


def build_evidence_text(evidence: list[dict]) -> str:
    if not evidence:
        return (
            "NO_RETRIEVED_EVIDENCE\n"
            "No usable dynamically retrieved evidence was available. "
            "Do not invent facts or claim that a source was checked."
        )

    chunks = []
    for index, item in enumerate(evidence, start=1):
        chunks.append(
            f"[Source {index}]\n"
            f"Domain: {source_domain(item.get('url', ''))}\n"
            f"Publisher: {item.get('publisher', '')}\n"
            f"Relevance: {item.get('_relevance', 0):.2f}\n"
            f"Title: {item['title']}\n"
            f"Published: {item['published']}\n"
            f"Description: {item['description']}\n"
            f"Article Content: {item.get('content', '')[:12000]}\n"
            f"Publisher Page Retrieved: {item.get('article_fetched', False)}\n"
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

    ranked_evidence = []
    for item in evidence:
        copied = dict(item)
        copied["_relevance"] = evidence_relevance_score(item, user_text)
        ranked_evidence.append(copied)

    evidence_text = build_evidence_text(ranked_evidence)

    retrieval_status = (
        "USABLE_DYNAMIC_EVIDENCE"
        if has_usable_evidence(ranked_evidence, user_text)
        else "NO_USABLE_DYNAMIC_EVIDENCE"
    )

    evidence_text = (
        f"RETRIEVAL STATUS: {retrieval_status}\n\n"
        + evidence_text
    )

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
        "max_tokens": 700,
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
