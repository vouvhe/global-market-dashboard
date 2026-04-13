"""
Yahoo Finance v8 Chart API를 직접 호출하여 시세 데이터를 조회합니다.
- yfinance 라이브러리 대신 requests + ThreadPoolExecutor 사용
- 이유: yfinance fast_info가 Yahoo 정책 변경으로 빈 응답 반환
- 효과: 15개 심볼 병렬 처리 → 로딩 시간 ~2초 (기존 순차 ~75초)
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

# ── 심볼 목록 ────────────────────────────────────────────
SYMBOLS: dict[str, dict] = {
    # 환율
    "USDKRW=X": {"name": "달러/원",     "category": "fx"},
    "EURKRW=X": {"name": "유로/원",     "category": "fx"},
    "JPYKRW=X": {"name": "엔/원",       "category": "fx"},
    "CNYKRW=X": {"name": "위안/원",     "category": "fx"},
    # 원자재
    "CL=F":     {"name": "WTI 유가",    "category": "commodity"},
    "BZ=F":     {"name": "브렌트 유가", "category": "commodity"},
    "GC=F":     {"name": "금 (Gold)",   "category": "commodity"},
    "SI=F":     {"name": "은 (Silver)", "category": "commodity"},
    # 지수
    "^KS11":    {"name": "코스피",      "category": "index"},
    "^KQ11":    {"name": "코스닥",      "category": "index"},
    "^IXIC":    {"name": "나스닥",      "category": "index"},
    "^GSPC":    {"name": "S&P 500",    "category": "index"},
    "^DJI":     {"name": "다우존스",    "category": "index"},
    "^N225":    {"name": "니케이 225",  "category": "index"},
    "000001.SS":{"name": "상하이 종합", "category": "index"},
}

# period → (range, interval) 매핑
PERIOD_MAP = {
    "1d":  {"range": "1d",  "interval": "5m"},
    "5d":  {"range": "5d",  "interval": "30m"},
    "1mo": {"range": "1mo", "interval": "1d"},
    "3mo": {"range": "3mo", "interval": "1d"},
    "1y":  {"range": "1y",  "interval": "1wk"},
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_TIMEOUT  = 10  # seconds


def _get_chart(symbol: str, range_: str, interval: str) -> dict:
    """Yahoo Finance v8 Chart API 단일 호출."""
    url = _BASE_URL.format(symbol=symbol)
    r = requests.get(
        url,
        headers=_HEADERS,
        params={"range": range_, "interval": interval},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return None


# ── 공개 API ─────────────────────────────────────────────

def fetch_summary() -> list[dict]:
    """모든 심볼의 현재가·등락 정보를 병렬로 반환합니다."""

    def _fetch_one(symbol: str, meta: dict) -> dict:
        base = {
            "symbol":     symbol,
            "name":       meta["name"],
            "category":   meta["category"],
            "price":      None,
            "prev_close": None,
            "change_amt": None,
            "change_pct": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            data   = _get_chart(symbol, range_="2d", interval="1d")
            result = data["chart"]["result"][0]
            m      = result["meta"]

            price      = _safe_float(m.get("regularMarketPrice"))
            prev_close = _safe_float(m.get("chartPreviousClose"))

            if price is None:
                # indicators 마지막 close 값으로 폴백
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                price  = _safe_float(next((v for v in reversed(closes) if v is not None), None))

            change_amt = round(price - prev_close, 4) if (price and prev_close) else None
            change_pct = round(change_amt / prev_close * 100, 4) if (change_amt and prev_close) else None

            return {**base, "price": price, "prev_close": prev_close,
                    "change_amt": change_amt, "change_pct": change_pct}
        except Exception as e:
            return {**base, "error": str(e)}

    results: list[dict] = [None] * len(SYMBOLS)  # type: ignore
    symbol_list = list(SYMBOLS.items())

    with ThreadPoolExecutor(max_workers=15) as pool:
        future_to_idx = {
            pool.submit(_fetch_one, sym, meta): idx
            for idx, (sym, meta) in enumerate(symbol_list)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    return results


def fetch_chart(symbol: str, period: str = "1mo") -> list[dict]:
    """특정 심볼의 히스토리 데이터를 반환합니다."""
    cfg = PERIOD_MAP.get(period, PERIOD_MAP["1mo"])
    try:
        data   = _get_chart(symbol, range_=cfg["range"], interval=cfg["interval"])
        result = data["chart"]["result"][0]

        timestamps = result.get("timestamp", [])
        quote      = result.get("indicators", {}).get("quote", [{}])[0]

        opens   = quote.get("open",   [None] * len(timestamps))
        highs   = quote.get("high",   [None] * len(timestamps))
        lows    = quote.get("low",    [None] * len(timestamps))
        closes  = quote.get("close",  [None] * len(timestamps))
        volumes = quote.get("volume", [None] * len(timestamps))

        records = []
        for i, ts in enumerate(timestamps):
            close = _safe_float(closes[i]) if i < len(closes) else None
            if close is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            records.append({
                "datetime": dt,
                "open":     _safe_float(opens[i])   if i < len(opens)   else None,
                "high":     _safe_float(highs[i])   if i < len(highs)   else None,
                "low":      _safe_float(lows[i])    if i < len(lows)    else None,
                "close":    close,
                "volume":   int(volumes[i]) if (i < len(volumes) and volumes[i] is not None) else None,
            })
        return records
    except Exception:
        return []
