from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import cache
import data_fetcher

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Global Market Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/summary")
def get_summary():
    """전체 종목 현재가 + 등락 반환 (카드용)."""
    cached = cache.get_cached_summary()
    if cached:
        return cached

    data = data_fetcher.fetch_summary()
    cache.upsert_summary(data)
    return data


@app.get("/api/chart/{symbol}")
def get_chart(
    symbol: str,
    period: str = Query(default="1mo", regex="^(1d|5d|1mo|3mo|1y)$"),
):
    """특정 종목 히스토리 반환 (차트용)."""
    if symbol not in data_fetcher.SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    cached = cache.get_cached_chart(symbol, period)
    if cached:
        return cached

    records = data_fetcher.fetch_chart(symbol, period)
    cache.upsert_chart(symbol, records, period)
    return records
