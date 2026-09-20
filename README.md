# Fake News Detector Chatbot

Simple chatbot that analyzes a news snippet, judges REAL / LIKELY FAKE / UNVERIFIABLE
with a confidence score, explains why, and returns a corrected, neutral rewrite.

- **Backend:** FastAPI (`api/index.py`), deployed as a Vercel Python serverless function.
- **Frontend:** React + Vite (`frontend/`), deployed as a Vercel static build.
- **Model:** Hugging Face Inference API, `meta-llama/Llama-3.1-8B-Instruct` (via the
  OpenAI-compatible chat completions route), configurable with `HF_LLM_MODEL`.

## 1. Get a Hugging Face token

1. Create an account at https://huggingface.co
2. Go to https://huggingface.co/settings/tokens and create a **read** access token.
3. Accept the model's license at https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
   (Meta gated model — approval is usually instant).

## 2. Local development

**Backend**
```bash
cd fake-news-chatbot
python -m venv venv && source venv/bin/activate   # optional
pip install -r requirements.txt
export HF_TOKEN=hf_xxx
export HF_LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
uvicorn api.index:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd fake-news-chatbot/frontend
npm install
npm run dev
```
Open http://localhost:5173 — the Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`.

## 3. Deploy to Vercel

```bash
npm install -g vercel   # if you don't have it
cd fake-news-chatbot
vercel
```

During setup (or afterwards in the Vercel dashboard → Project → Settings → Environment
Variables), add:

| Name          | Value                                   |
|---------------|------------------------------------------|
| `HF_TOKEN`      | your Hugging Face access token          |
| `HF_LLM_MODEL`  | `meta-llama/Llama-3.1-8B-Instruct`      |

Then deploy to production:
```bash
vercel --prod
```

`vercel.json` already wires:
- `/api/*` → the FastAPI app in `api/index.py`
- everything else → the built React app in `frontend/dist`

## 4. How it works

1. User types/pastes a news snippet in the chat UI.
2. Frontend POSTs `{ text }` to `/api/analyze`.
3. Backend sends a structured prompt to the HF chat-completions endpoint for
   `HF_LLM_MODEL`, asking for a JSON verdict, confidence, explanation, and a
   corrected neutral rewrite.
4. Backend parses/validates the JSON and returns it; the UI renders it as a
   colored result card in the chat.

## Notes / limits

- This is intentionally minimal (no database, no auth, no chat history persistence)
  to keep it easy to read and cheap to run.
- Hugging Face's free Inference API can be slow/rate-limited on first request
  (model "cold start"); a retry or loading state is already handled in the UI.
- If `HF_TOKEN` is missing, the backend returns a friendly UNVERIFIABLE response
  explaining what to configure, instead of crashing.
