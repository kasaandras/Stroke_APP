# TARGET_BCN_APP

Clinical prediction web app for the TARGET Master's thesis (UPC Barcelona).
A clinician enters patient data at admission; the app shows live Bayesian
predictions of five stroke-rehab discharge outcomes (Barthel, FIM Total,
FIM Motor, walking probability, mRS ≤ 2 probability) with 50% / 95%
credible intervals.

## Folder structure

```
TARGET_BCN_APP/
├── frontend/
│   ├── src/                  # Next.js + TypeScript UI
│   └── api/                  # Python serverless functions (Vercel)
│       ├── predict.py        # POST /api/predict (FastAPI app)
│       ├── _core.py          # predict() implementation + constants
│       ├── _tests.py         # self-consistency tests vs stored draws
│       ├── data/*.pkl        # posterior draws from the thesis fit
│       └── requirements.txt  # numpy / scipy / fastapi / uvicorn
└── README.md
```

The Python code lives inside `frontend/api/` because Vercel's Python
runtime auto-detects serverless functions in a project's top-level
`api/` directory. With Vercel's Root Directory set to `frontend`,
`frontend/api/predict.py` is served at `/api/predict` automatically.

## Local development

Two processes: a Next.js dev server and a uvicorn process. The Next.js
rewrite (`next.config.ts`) proxies `/api/*` to uvicorn when the
`BACKEND_URL` env var is set; on Vercel `BACKEND_URL` is unset, so the
rewrite is a no-op and `/api/predict` goes straight to the Python
serverless function.

```bash
# Terminal 1 -- backend
cd frontend/api
python3.13 -m venv .venv                 # first time only
./.venv/bin/pip install -r requirements.txt   # first time only
./.venv/bin/uvicorn predict:app --reload --port 8000

# Terminal 2 -- frontend
cd frontend
cp .env.local.example .env.local          # first time only
npm install                                # first time only
npm run dev
```

Open <http://localhost:3000>. Predictions update 300 ms after the last
keystroke.

## Running the prediction self-tests

```bash
cd frontend/api
./.venv/bin/python _tests.py
```

The tests reconstruct raw features from 15 training rows across the five
endpoints, push them through `predict()`, and confirm the deterministic
linear predictor matches what's stored in the pickles to 1e-10.

## Deploying to Vercel

1. **Import** the repo (`kasaandras/Stroke_APP`) in Vercel.
2. **Framework Preset:** Next.js.
3. **Root Directory:** `frontend` (Vercel will scan `frontend/api/`
   for Python functions automatically).
4. Do **not** set `BACKEND_URL` -- leaving it unset disables the dev proxy
   so requests reach the deployed Python function directly.
5. Click **Deploy**. The first cold start may take a few seconds
   (numpy + scipy import); subsequent requests are fast.
