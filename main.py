from __future__ import annotations

import base64
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import cache
import data_fetcher

# 토스페이먼츠 테스트 시크릿 키 (실서비스 시 환경변수로 교체)
TOSS_SECRET_KEY = "test_gsk_docs_OaPz8L5KdmQXkzRz3y47BMw6"

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


class PaymentConfirmRequest(BaseModel):
    paymentKey: str
    orderId: str
    amount: int


@app.post("/api/payment/confirm")
async def confirm_payment(body: PaymentConfirmRequest):
    """토스페이먼츠 결제 승인 API 호출."""
    credentials = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.tosspayments.com/v1/payments/confirm",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": body.paymentKey,
                "orderId": body.orderId,
                "amount": body.amount,
            },
            timeout=15.0,
        )

    if resp.status_code == 200:
        return resp.json()

    error = resp.json()
    raise HTTPException(
        status_code=resp.status_code,
        detail=error.get("message", "결제 승인에 실패했습니다."),
    )


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
