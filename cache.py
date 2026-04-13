from __future__ import annotations

from datetime import datetime, timezone, timedelta

from db import get_client

# 1d/5d 기간은 분봉 데이터라 DB 저장 생략
_CHART_CACHE_PERIODS = {"1mo", "3mo", "1y"}

# summary 캐시 TTL (초)
_SUMMARY_TTL = 60


def get_cached_summary() -> list[dict] | None:
    """market_prices 테이블에서 TTL 이내 레코드를 반환. 없으면 None."""
    client = get_client()
    if client is None:
        return None

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=_SUMMARY_TTL)).isoformat()
        resp = (
            client.table("market_prices")
            .select("symbol, name, category, price, prev_close, change_amt, change_pct, fetched_at")
            .gte("fetched_at", cutoff)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data
    except Exception:
        pass
    return None


def upsert_summary(data: list[dict]) -> None:
    """market_prices 테이블에 데이터를 upsert."""
    client = get_client()
    if client is None:
        return

    try:
        rows = [
            {
                "symbol":     item["symbol"],
                "name":       item.get("name"),
                "category":   item.get("category"),
                "price":      item.get("price"),
                "prev_close": item.get("prev_close"),
                "change_amt": item.get("change_amt"),
                "change_pct": item.get("change_pct"),
                "fetched_at": item.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
            }
            for item in data
            if item.get("price") is not None
        ]
        if rows:
            client.table("market_prices").upsert(rows, on_conflict="symbol").execute()
    except Exception:
        pass


def get_cached_chart(symbol: str, period: str) -> list[dict] | None:
    """market_history 테이블에서 symbol + period 범위의 레코드를 반환. 없으면 None."""
    if period not in _CHART_CACHE_PERIODS:
        return None

    client = get_client()
    if client is None:
        return None

    try:
        cutoff_date = _period_to_cutoff(period)
        resp = (
            client.table("market_history")
            .select("datetime:trade_date, open:open_price, high:high_price, low:low_price, close:close_price, volume")
            .eq("symbol", symbol)
            .gte("trade_date", cutoff_date)
            .order("trade_date", desc=False)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data
    except Exception:
        pass
    return None


def upsert_chart(symbol: str, records: list[dict], period: str) -> None:
    """market_history 테이블에 히스토리 데이터를 upsert."""
    if period not in _CHART_CACHE_PERIODS:
        return

    client = get_client()
    if client is None:
        return

    try:
        rows = []
        for r in records:
            dt_str = r.get("datetime", "")
            trade_date = dt_str[:10] if dt_str else None
            if not trade_date or r.get("close") is None:
                continue
            rows.append({
                "symbol":      symbol,
                "trade_date":  trade_date,
                "open_price":  r.get("open"),
                "high_price":  r.get("high"),
                "low_price":   r.get("low"),
                "close_price": r.get("close"),
                "volume":      r.get("volume"),
            })
        if rows:
            client.table("market_history").upsert(rows, on_conflict="symbol,trade_date").execute()
    except Exception:
        pass


def _period_to_cutoff(period: str) -> str:
    """기간 문자열을 기준 날짜(ISO date)로 변환."""
    today = datetime.now(timezone.utc).date()
    if period == "1mo":
        delta = timedelta(days=31)
    elif period == "3mo":
        delta = timedelta(days=92)
    else:  # 1y
        delta = timedelta(days=366)
    return (today - delta).isoformat()
