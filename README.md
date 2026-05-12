# TARGET_BCN_APP

Clinical prediction web app for the TARGET thesis. The frontend is a Next.js + TypeScript UI; the backend is a Python serverless API (FastAPI, Vercel-style) that loads posterior draws and serves predictions.

## Folder structure

```
TARGET_BCN_APP/
├── frontend/   # Next.js + TypeScript + Tailwind
├── backend/    # Python serverless (FastAPI)
├── data/       # Posterior draws .pkl files (added later)
└── README.md
```

## Frontend — run the dev server

```bash
cd frontend
npm install        # first time only
npm run dev
```

Open http://localhost:3000.

## Backend — run locally

```bash
cd backend
source .venv/bin/activate          # activate the virtualenv
pip install -r requirements.txt    # first time only
uvicorn main:app --reload --port 8000
```

The API will be at http://localhost:8000.

## Data

Drop posterior draw `.pkl` files into `data/`. They're git-ignored placeholders for now — the backend will load them at request time.
