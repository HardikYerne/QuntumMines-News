# QuntumMines – Fake News Detector (frontend)

React + Vite. Pixel-matched to the reference design. Your backend is not touched.

## Run
    npm install
    cp .env.example .env     # set VITE_API_URL to your existing chat endpoint
    npm run dev              # http://localhost:5173

## Connect your backend
Everything backend-related lives in **src/api.js**:
- `VITE_API_URL` – your endpoint (leave empty to use the built-in demo replies)
- request body – edit the `body: JSON.stringify({ message: text })` line if your API expects other field names
- `normalize()` – map your API's JSON to the UI shape (plain text reply or claim analysis)

No other file needs to change.
