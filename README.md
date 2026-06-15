# TARGET_BCN_APP

Clinical prediction web app for the TARGET Master's thesis (UPC Barcelona).
A clinician enters patient data at admission; the app shows live Bayesian
predictions of five stroke-rehab discharge outcomes (Barthel, FIM Total,
FIM Motor, walking probability, mRS ≤ 2 probability) with 50% / 95%
credible intervals.

## Folder structure

```
TARGET_BCN_APP/
├── src/                 # Next.js + TypeScript UI (App Router, 3 tabs)
├── api/                 # Python serverless functions (Vercel)
│   ├── predict.py       # POST /api/predict — Bayesian discharge + SHAP
│   ├── recommend.py     # POST /api/recommend — fuzzy treatment ranker
│   ├── _local_dev.py    # combined uvicorn entry for `next dev`
│   ├── _tests.py        # self-consistency tests for predict.py
│   ├── data/*.pkl       # posterior draws (5 endpoints)
│   ├── data/*.csv       # SCOAR arm summary + synthetic trials
│   └── requirements.txt # numpy / scipy / pandas / fastapi / uvicorn
├── public/              # Next.js static assets
├── next.config.ts       # Next.js config (dev proxy for /api/*)
├── vercel.json          # Vercel build config (maxDuration per function)
└── README.md
```

Everything sits at the repo root so Vercel auto-detects the standard
Next.js + Python serverless layout with no Root Directory tweaks needed.

## Local development

Two processes: a Next.js dev server and a uvicorn process. The Next.js
rewrite (`next.config.ts`) proxies `/api/*` to uvicorn when the
`BACKEND_URL` env var is set; on Vercel `BACKEND_URL` is unset, so the
rewrite is a no-op and `/api/predict` goes straight to the Python
serverless function.

```bash
# Terminal 1 -- Python backend (combined dev entry, all /api/* routes)
cd api
python3.13 -m venv .venv                # first time only
./.venv/bin/pip install -r requirements.txt   # first time only
./.venv/bin/uvicorn _local_dev:dev --reload --port 8000

# Terminal 2 -- Next.js frontend (from repo root)
cp .env.local.example .env.local        # first time only
npm install                              # first time only
npm run dev
```

Open <http://localhost:3000>. Predictions update 300 ms after the last
keystroke.

## Running the prediction self-tests

```bash
cd api
./.venv/bin/python _tests.py
```

The tests reconstruct raw features from 15 training rows across the five
endpoints, push them through `predict()`, and confirm the deterministic
linear predictor matches what's stored in the pickles to 1e-10.

## Deploying to Vercel

Import the repo (`kasaandras/Stroke_APP`) in Vercel and click Deploy.
Default settings work out of the box:

- **Framework Preset:** Next.js (auto-detected from `package.json`)
- **Root Directory:** `./` (the default — keep it)
- **Environment Variables:** leave empty (do **not** set `BACKEND_URL`)

Vercel auto-detects `api/predict.py` as a Python serverless function,
installs the deps from `api/requirements.txt`, and bundles `api/data/*.pkl`
into the function bundle (via `vercel.json`). First cold start can take
a few seconds (numpy + scipy import); subsequent requests are fast.
