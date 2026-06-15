"""Local dev server combining /api/predict and /api/recommend into one app.

In production each .py file in /api/ is a separate Vercel function and
URLs route by filename (predict.py serves /api/predict, recommend.py
serves /api/recommend). For local `next dev` we proxy all /api/* to one
backend, so this file mounts both route handlers onto a single FastAPI
instance.

Run:
    ./.venv/bin/uvicorn _local_dev:dev --reload --port 8000

The underscore prefix means Vercel does NOT treat this file as a
serverless function -- it's only used locally.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from predict import predict_route, health
from recommend import recommend_route

dev = FastAPI(title="TARGET dev combined")
dev.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

dev.add_api_route("/api/health", health, methods=["GET"])
dev.add_api_route("/api/predict", predict_route, methods=["POST"])
dev.add_api_route("/api/recommend", recommend_route, methods=["POST"])
