/* ── 전역 상태 ─────────────────────────────────────── */
let chartInstance = null;
let currentSymbol = null;
let currentPeriod = '1mo';
let summaryData   = [];

/* ── 포맷 헬퍼 ─────────────────────────────────────── */
function formatPrice(price, category) {
  if (price === null || price === undefined) return '-';
  const num = parseFloat(price);
  if (isNaN(num)) return '-';

  if (category === 'fx') {
    // 원화 환율: 소수점 2자리
    return num.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  // 원자재·지수: 2자리
  return num.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function changeClass(val) {
  if (val === null || val === undefined) return 'flat';
  const n = parseFloat(val);
  if (n > 0) return 'rise';
  if (n < 0) return 'fall';
  return 'flat';
}

function changeArrow(val) {
  if (val === null || val === undefined) return '';
  const n = parseFloat(val);
  if (n > 0) return '▲';
  if (n < 0) return '▼';
  return '';
}

function fmtChange(amt, pct) {
  if (amt === null || pct === null) return '-';
  const a = parseFloat(amt);
  const p = parseFloat(pct);
  const sign = a >= 0 ? '+' : '';
  return `${sign}${a.toFixed(2)} (${sign}${p.toFixed(2)}%)`;
}

/* ── 카드 렌더링 ───────────────────────────────────── */
function renderCards(data) {
  summaryData = data;

  const containers = {
    fx:        document.getElementById('cards-fx'),
    commodity: document.getElementById('cards-commodity'),
    index:     document.getElementById('cards-index'),
  };

  // 컨테이너 초기화
  Object.values(containers).forEach(el => { el.innerHTML = ''; });

  data.forEach(item => {
    const cls   = changeClass(item.change_amt);
    const arrow = changeArrow(item.change_amt);
    const priceStr  = formatPrice(item.price, item.category);
    const changeStr = fmtChange(item.change_amt, item.change_pct);

    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.symbol   = item.symbol;
    card.dataset.category = item.category;

    card.innerHTML = `
      <div class="card-name">${item.name}</div>
      <div class="card-price ${cls}">${priceStr}</div>
      <div class="card-change ${cls}">
        <span>${arrow}</span>
        <span>${changeStr}</span>
      </div>
      ${item.error ? `<div class="card-error">⚠ 데이터 오류</div>` : ''}
    `;

    card.addEventListener('click', () => onCardClick(item.symbol, item.name));

    const container = containers[item.category];
    if (container) container.appendChild(card);
  });

  // 이전에 선택된 카드 복원
  if (currentSymbol) {
    setSelectedCard(currentSymbol);
  }
}

function setSelectedCard(symbol) {
  document.querySelectorAll('.card').forEach(c => {
    c.classList.toggle('selected', c.dataset.symbol === symbol);
  });
}

/* ── 카드 클릭 핸들러 ──────────────────────────────── */
function onCardClick(symbol, name) {
  currentSymbol = symbol;
  setSelectedCard(symbol);

  // 차트 패널 제목 업데이트
  document.getElementById('chart-title').textContent = name;

  // 기간 탭 활성화 상태 유지
  loadChart(symbol, currentPeriod);
}

/* ── 데이터 로드: summary ──────────────────────────── */
async function loadSummary() {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.remove('hidden');

  try {
    const resp = await fetch('/api/summary');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderCards(data);

    // 기준 시각 업데이트
    const now = new Date();
    document.getElementById('updated-time').textContent =
      now.toLocaleString('ko-KR', { hour12: false });
  } catch (err) {
    console.error('summary 로드 실패:', err);
    alert('데이터를 불러오지 못했습니다. 서버를 확인해 주세요.');
  } finally {
    overlay.classList.add('hidden');
  }
}

/* ── 데이터 로드: chart ────────────────────────────── */
async function loadChart(symbol, period) {
  const panel   = document.getElementById('chart-panel');
  const loading = document.getElementById('chart-loading');
  const errEl   = document.getElementById('chart-error');

  panel.classList.remove('hidden');
  loading.classList.remove('hidden');
  errEl.classList.add('hidden');

  try {
    const resp = await fetch(`/api/chart/${encodeURIComponent(symbol)}?period=${period}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const records = await resp.json();

    if (!records || records.length === 0) {
      throw new Error('데이터가 없습니다.');
    }

    // 종목 메타 찾기 (카테고리)
    const meta = summaryData.find(d => d.symbol === symbol) || {};
    renderChart(records, meta);
  } catch (err) {
    console.error('chart 로드 실패:', err);
    errEl.textContent = `차트 데이터를 불러오지 못했습니다: ${err.message}`;
    errEl.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
  }
}

/* ── Chart.js 렌더링 ───────────────────────────────── */
function renderChart(records, meta) {
  const labels = records.map(r => {
    const dt = new Date(r.datetime);
    if (currentPeriod === '1d' || currentPeriod === '5d') {
      // 분봉/시봉: HH:MM 표시
      return dt.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
    }
    // 일봉: MM/DD
    return `${dt.getMonth() + 1}/${dt.getDate()}`;
  });

  const closes = records.map(r => r.close ?? r.datetime);

  // 등락 방향으로 차트 색상 결정
  const first = closes.find(v => v !== null);
  const last  = closes.filter(v => v !== null).at(-1);
  const isRise = (last ?? 0) >= (first ?? 0);
  const lineColor = isRise ? '#ef5350' : '#1976d2';

  // 기존 차트 제거
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const ctx = document.getElementById('market-chart').getContext('2d');

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: closes,
        borderColor: lineColor,
        borderWidth: 2,
        pointRadius: records.length > 60 ? 0 : 2,
        pointHoverRadius: 4,
        fill: true,
        backgroundColor: hexToRgba(lineColor, 0.08),
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2230',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#8b949e',
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.y;
              if (v === null) return '-';
              return ' ' + formatPrice(v, meta.category);
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: '#8b949e',
            maxTicksLimit: 8,
            maxRotation: 0,
          },
          grid: { color: '#21262d' },
        },
        y: {
          ticks: {
            color: '#8b949e',
            callback: v => formatPrice(v, meta.category),
          },
          grid: { color: '#21262d' },
          position: 'right',
        },
      },
    },
  });
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/* ── 기간 탭 이벤트 ────────────────────────────────── */
document.querySelectorAll('.period-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!currentSymbol) return;
    currentPeriod = btn.dataset.period;

    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    loadChart(currentSymbol, currentPeriod);
  });
});

/* ── 새로고침 버튼 ─────────────────────────────────── */
document.getElementById('refresh-btn').addEventListener('click', () => {
  loadSummary();
});

/* ── 초기 로드 ─────────────────────────────────────── */
loadSummary();
handlePaymentRedirect();

/* ═══════════════════════════════════════════════════
   토스페이먼츠 결제 위젯
   ═══════════════════════════════════════════════════ */
const TOSS_CLIENT_KEY = 'test_gck_docs_Ovk5rk1EwkEbP0W43n07W0zPoqfR';
const PREMIUM_AMOUNT  = 9900;

let tossWidgets = null; // 결제위젯 인스턴스 (모달 열릴 때 생성)

/* ── 주문 ID 생성 ──────────────────────────────────── */
function generateOrderId() {
  const ts   = Date.now().toString(36).toUpperCase();
  const rand = Math.random().toString(36).slice(2, 8).toUpperCase();
  return `ORD-${ts}-${rand}`;
}

/* ── 결제 모달 열기 ────────────────────────────────── */
async function openPaymentModal() {
  const modal     = document.getElementById('payment-modal');
  const submitBtn = document.getElementById('pay-submit-btn');

  modal.classList.remove('hidden');
  submitBtn.disabled = true;
  submitBtn.textContent = '결제 UI 로딩 중...';

  try {
    // 비회원 결제: '__ANONYMOUS_' 는 토스 ANONYMOUS 상수 실제값
    const customerKey = '__ANONYMOUS_';
    const tossPayments = TossPayments(TOSS_CLIENT_KEY);
    tossWidgets = tossPayments.widgets({ customerKey });

    await tossWidgets.setAmount({ currency: 'KRW', value: PREMIUM_AMOUNT });

    // 결제수단 UI 렌더링
    await tossWidgets.renderPaymentMethods({
      selector: '#payment-method',
      variantKey: 'DEFAULT',
    });

    // 약관 UI (실패해도 결제수단 UI는 유지)
    try {
      await tossWidgets.renderAgreement({
        selector: '#agreement',
        variantKey: 'AGREEMENT',
      });
    } catch (_) { /* 어드민 미설정 시 무시 */ }

    submitBtn.disabled = false;
    submitBtn.textContent = '결제하기';
  } catch (err) {
    console.error('결제 위젯 로드 실패:', err);
    submitBtn.textContent = '로드 실패 — 다시 시도해 주세요';
  }
}

/* ── 결제 모달 닫기 ────────────────────────────────── */
function closePaymentModal() {
  document.getElementById('payment-modal').classList.add('hidden');
  // 위젯 영역 초기화 (재오픈 시 중복 렌더 방지)
  document.getElementById('payment-method').innerHTML = '';
  document.getElementById('agreement').innerHTML      = '';
  tossWidgets = null;
}

/* ── 결제 요청 ─────────────────────────────────────── */
async function requestTossPayment() {
  if (!tossWidgets) return;

  const submitBtn = document.getElementById('pay-submit-btn');
  submitBtn.disabled = true;
  submitBtn.textContent = '처리 중...';

  const baseUrl = window.location.origin + '/';

  try {
    await tossWidgets.requestPayment({
      orderId:       generateOrderId(),
      orderName:     'Global Market Dashboard 프리미엄',
      customerName:  '구독자',
      successUrl:    baseUrl + '?payment=success',
      failUrl:       baseUrl + '?payment=fail',
    });
  } catch (err) {
    // 사용자가 결제창을 닫거나 에러 발생 시
    submitBtn.disabled = false;
    submitBtn.textContent = '결제하기';
    if (err?.code !== 'USER_CANCEL') {
      console.error('결제 요청 오류:', err);
    }
  }
}

/* ── 결제 결과 처리 (리다이렉트 복귀 시) ─────────── */
async function handlePaymentRedirect() {
  const params = new URLSearchParams(window.location.search);
  const status = params.get('payment');
  if (!status) return;

  // URL 정리 (뒤로가기 시 중복 처리 방지)
  history.replaceState(null, '', window.location.pathname);

  if (status === 'success') {
    const paymentKey = params.get('paymentKey');
    const orderId    = params.get('orderId');
    const amount     = parseInt(params.get('amount'), 10);

    try {
      await fetch('/api/payment/confirm', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ paymentKey, orderId, amount }),
      }).then(r => {
        if (!r.ok) throw new Error('승인 실패');
        return r.json();
      });

      showResultModal(
        '🎉',
        '결제 완료!',
        `프리미엄 구독이 시작되었습니다.\n월 ${PREMIUM_AMOUNT.toLocaleString()}원 · 언제든지 해지 가능`
      );
    } catch (err) {
      showResultModal('❌', '결제 승인 실패', '결제는 완료됐지만 승인 처리 중 오류가 발생했습니다.\n고객센터에 문의해 주세요.');
    }
  } else if (status === 'fail') {
    const message = params.get('message') || '결제가 취소되었습니다.';
    showResultModal('😢', '결제 실패', message);
  }
}

/* ── 결과 모달 표시 ────────────────────────────────── */
function showResultModal(icon, title, desc) {
  document.getElementById('result-icon').textContent  = icon;
  document.getElementById('result-title').textContent = title;
  document.getElementById('result-desc').textContent  = desc;
  document.getElementById('result-modal').classList.remove('hidden');
}

/* ── 모달 이벤트 바인딩 ────────────────────────────── */
document.getElementById('premium-btn')
  .addEventListener('click', openPaymentModal);

document.getElementById('payment-modal-close')
  .addEventListener('click', closePaymentModal);

document.getElementById('payment-modal')
  .addEventListener('click', e => {
    if (e.target === e.currentTarget) closePaymentModal();
  });

document.getElementById('pay-submit-btn')
  .addEventListener('click', requestTossPayment);

document.getElementById('result-close-btn')
  .addEventListener('click', () => {
    document.getElementById('result-modal').classList.add('hidden');
  });
