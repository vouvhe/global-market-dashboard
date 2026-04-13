# Global Market Dashboard — 프로젝트 문서

> 작성일: 2026-04-13  
> 목적: 인베스팅닷컴 스타일의 환율·원자재·주요 지수 차트 웹사이트  
> 상태: MVP 완성 (Phase 1 기능 구현 완료)

---

## 1. 사용자 요청 요약

investing.com / 네이버 금융처럼 **환율·원자재·주요 지수**를 한 화면에서 카드 형태로 보여주고,  
카드를 클릭하면 **하단 차트(Chart.js)**가 나타나며 **기간 선택(1일~1년)**이 가능한 대시보드.  
백엔드는 Python FastAPI + yfinance, DB는 Supabase(PostgreSQL), 프론트는 Vanilla JS.

---

## 2. 기술 스택

| 레이어 | 기술 | 버전 | 선택 이유 |
|--------|------|------|-----------|
| Backend | FastAPI | 0.115.0 | 코드 간결, async 지원, 자동 문서화 |
| ASGI 서버 | uvicorn[standard] | 0.30.6 | FastAPI 공식 권장 |
| 금융 데이터 | yfinance | 0.2.43 | API Key 불필요, 환율·원자재·지수 모두 커버 |
| 데이터 처리 | pandas | 2.2.3 | yfinance DataFrame 핸들링 |
| DB 클라이언트 | supabase-py | 2.9.1 | Supabase REST API 래퍼 |
| 환경변수 | python-dotenv | 1.0.1 | .env 파일 로드 |
| HTTP 클라이언트 | httpx | 0.27.2 | supabase-py 의존성 |
| Frontend | Vanilla JS + HTML + CSS | - | 빌드 도구 불필요, Claude Code 결과물 검토 쉬움 |
| 차트 | Chart.js | 4.4.3 | CDN 1줄, Line Chart 바로 사용 가능 |
| DB | Supabase (PostgreSQL) | - | 무료 플랜, MCP 연결 가능 |

---

## 3. 디렉토리 구조

```
인베스팅/
├── PROJECT.md          ← 이 파일 (프로젝트 전체 문서)
├── main.py             ← FastAPI 앱 진입점 + 라우터
├── data_fetcher.py     ← yfinance 데이터 조회 (fetch_summary / fetch_chart)
├── cache.py            ← Supabase 캐시 read/write (get_cached_* / upsert_*)
├── db.py               ← Supabase 클라이언트 싱글턴 (graceful fallback)
├── requirements.txt    ← Python 의존성
├── .env                ← 실제 키 (Git 제외 필수)
├── .env.example        ← 키 템플릿
└── static/
    ├── index.html      ← 메인 UI (헤더 + 카드 섹션 + 차트 패널)
    ├── style.css       ← 다크 테마 스타일
    └── app.js          ← 카드 렌더링 + Chart.js 제어
```

---

## 4. 데이터 항목

### 환율 (FX)
| 표시명 | 심볼 |
|--------|------|
| 달러/원 | USDKRW=X |
| 유로/원 | EURKRW=X |
| 엔/원 | JPYKRW=X |
| 위안/원 | CNYKRW=X |

### 원자재 (Commodity)
| 표시명 | 심볼 |
|--------|------|
| WTI 유가 | CL=F |
| 브렌트 유가 | BZ=F |
| 금 (Gold) | GC=F |
| 은 (Silver) | SI=F |

### 주요 지수 (Index)
| 표시명 | 심볼 |
|--------|------|
| 코스피 | ^KS11 |
| 코스닥 | ^KQ11 |
| 나스닥 | ^IXIC |
| S&P 500 | ^GSPC |
| 다우존스 | ^DJI |
| 니케이 225 | ^N225 |
| 상하이 종합 | 000001.SS |

---

## 5. API 엔드포인트

```
GET /                           → index.html 반환
GET /api/summary                → 전체 종목 현재가 + 등락 (카드용)
GET /api/chart/{symbol}         → 특정 종목 히스토리 (차트용)
  ?period = 1d | 5d | 1mo | 3mo | 1y  (기본값: 1mo)
```

### /api/summary 응답 예시
```json
[
  {
    "symbol": "USDKRW=X",
    "name": "달러/원",
    "category": "fx",
    "price": 1374.50,
    "prev_close": 1370.00,
    "change_amt": 4.50,
    "change_pct": 0.3285,
    "fetched_at": "2026-04-13T06:00:00+00:00"
  }
]
```

### /api/chart/{symbol} 응답 예시
```json
[
  {
    "datetime": "2026-03-14T00:00:00",
    "open": 1365.0,
    "high": 1372.0,
    "low": 1360.0,
    "close": 1368.5,
    "volume": null
  }
]
```

---

## 6. Supabase 테이블 설계

### market_prices — 시세 캐시 (TTL 60초)
```sql
CREATE TABLE market_prices (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL UNIQUE,
    name        VARCHAR(50),
    category    VARCHAR(20)    NOT NULL,
    price       NUMERIC(18,4)  NOT NULL,
    prev_close  NUMERIC(18,4),
    change_amt  NUMERIC(18,4),
    change_pct  NUMERIC(8,4),
    fetched_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
```

### market_history — 히스토리 (일봉 적재)
```sql
CREATE TABLE market_history (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL,
    trade_date  DATE           NOT NULL,
    open_price  NUMERIC(18,4),
    high_price  NUMERIC(18,4),
    low_price   NUMERIC(18,4),
    close_price NUMERIC(18,4)  NOT NULL,
    volume      BIGINT,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, trade_date)
);
```

### user_favorites — 즐겨찾기 (Phase 2)
```sql
CREATE TABLE user_favorites (
    id         BIGSERIAL PRIMARY KEY,
    symbol     VARCHAR(20) NOT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. 캐싱 흐름

```
[GET /api/summary 요청]
        ↓
cache.get_cached_summary()
        ↓
fetched_at이 60초 이내? ──YES──→ DB 데이터 반환
        ↓ NO
data_fetcher.fetch_summary()  ← yfinance 호출
        ↓
cache.upsert_summary()        ← DB에 저장
        ↓
클라이언트에 반환

[GET /api/chart/{symbol}?period=1mo]
        ↓
cache.get_cached_chart()
        ↓
DB에 기간 내 데이터 있음? ──YES──→ DB 데이터 반환
        ↓ NO
data_fetcher.fetch_chart()    ← yfinance 호출
        ↓
period가 1mo/3mo/1y이면 cache.upsert_chart()  (분봉 1d/5d는 저장 생략)
        ↓
클라이언트에 반환
```

---

## 8. 환경 설정

### .env 파일 (`.env.example` 복사 후 작성)
```env
SUPABASE_URL=https://<project_ref>.supabase.co
SUPABASE_KEY=<service_role_key>
```

> Supabase 미설정(또는 플레이스홀더 유지) 시 `db.get_client()`가 `None` 반환 →  
> 캐시 없이 yfinance 직접 호출로 자동 폴백. **서버는 정상 동작함.**

### Supabase MCP 연결 (Claude Code 사용 시)
`claude_desktop_config.json` 에 추가:
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--supabase-url", "https://<project_ref>.supabase.co",
        "--supabase-key", "<service_role_key>"
      ]
    }
  }
}
```

---

## 9. 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일 열어서 Supabase 정보 입력 (선택 사항)

# 3. 서버 실행
uvicorn main:app --reload --port 8000

# 4. 브라우저 접속
# http://localhost:8000
```

---

## 10. UI 동작 방식

1. 페이지 진입 → `loadSummary()` 호출 → 전체 카드 렌더링
2. 카드 클릭 → `loadChart(symbol, "1mo")` → 하단 차트 표시
3. 기간 탭 클릭 → 같은 종목으로 `loadChart(symbol, period)` 재호출
4. 새로고침 버튼 → `loadSummary()` 재호출
5. 색상 기준: **상승 = 빨강(#ef5350), 하락 = 파랑(#1976d2)** (국내 기준)

---

## 11. 구현 현황 (Phase 별)

### Phase 1 — MVP ✅ 완료
- [x] 전체 종목 카드 표시 (환율/원자재/지수)
- [x] 카드 클릭 → 하단 차트 표시
- [x] 차트 기간 선택 (1일 / 1주 / 1개월 / 3개월 / 1년)
- [x] 등락 색상 구분 (상승=빨강, 하락=파랑)
- [x] 수동 새로고침 버튼
- [x] 기준 시각 표시
- [x] Supabase 캐싱 (TTL 60초, graceful fallback)

### Phase 2 — 추가 기능 (미구현)
- [ ] 자동 새로고침 (5분 간격)
- [ ] 즐겨찾기 종목 고정 (`user_favorites` 테이블 연동)
- [ ] 다크모드 / 라이트모드 전환
- [ ] 종목 추가/삭제 기능

---

## 12. 데이터 제약 사항

| 항목 | 내용 |
|------|------|
| yfinance 딜레이 | 주식/지수 15~20분 지연, 선물/FX는 비교적 빠름 |
| 요청 제한 | 과도한 호출 시 Yahoo 차단 가능 → 캐싱으로 완화 (TTL 60초) |
| 장외 시간 | 미국 장 마감 후 데이터 미갱신 → 마지막 종가 표시 |
| 1d 차트 | 분봉(5m) 데이터, DB 저장 생략 (매번 yfinance 직접 호출) |

---

## 13. 이 파일을 Claude Code에 전달하는 방법

이 파일(`PROJECT.md`)을 Claude Code 대화창에 붙여넣거나 첨부하면  
**현재 프로젝트 구조, 기술 스택, 구현 현황, 다음 할 일**을 즉시 파악하고 이어서 개발 가능합니다.

예시 프롬프트:
```
아래 PROJECT.md 내용을 기반으로 Phase 2 자동 새로고침 기능을 추가해줘.
[PROJECT.md 내용 붙여넣기]
```
