const DATA_BASE = '../data';
const METAL_NAMES = {
  copper: '전기동', aluminum: '알루미늄', zinc: '아연',
  nickel: '니켈', lead: '납', tin: '주석',
};
const METAL_SYMBOLS = {
  copper: 'Cu', aluminum: 'Al', zinc: 'Zn',
  nickel: 'Ni', lead: 'Pb', tin: 'Sn',
};

const cache = {};

function fmt(n) {
  if (n == null) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

function fmtInt(n) {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('en-US');
}

function changeClass(n) {
  if (n == null || n === 0) return '';
  return n > 0 ? 'up' : 'down';
}

function changePrefix(n) {
  if (n == null) return '';
  return n > 0 ? '+' : '';
}

function miniChart(data, key) {
  const values = data.slice(0, 30).reverse().map(d => {
    const lme = d.lme || {};
    const tm = lme['3m'] || lme['cash'] || {};
    return tm[key] ?? tm['close'];
  }).filter(v => v != null);

  if (values.length < 2) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 100;
  const h = 100;
  const step = w / (values.length - 1);

  const points = values.map((v, i) =>
    `${(i * step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`
  ).join(' ');

  const trending = values[values.length - 1] >= values[0];
  const color = trending ? 'var(--up)' : 'var(--down)';

  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
  </svg>`;
}

function renderSection(metal, ts) {
  const section = document.querySelector(`.metal-section[data-metal="${metal}"]`);
  if (!ts || !ts.data || ts.data.length === 0) {
    section.innerHTML = `<div class="card"><div class="card-title">데이터 없음</div></div>`;
    return;
  }

  const latest = ts.data[0];
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const inv = latest.inventory || {};
  const sett = latest.settlement || {};
  const shfe = latest.shfe || {};
  const krw = latest.krw || {};

  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;

  section.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:baseline;justify-content:space-between">
        <div>
          <span class="metal-name">${METAL_NAMES[metal]}</span>
          <span class="metal-symbol">${METAL_SYMBOLS[metal]}</span>
        </div>
        <div style="text-align:right">
          <div class="price-main">$${fmt(mainPrice)}</div>
          <div class="change ${changeClass(mainChange)}">${changePrefix(mainChange)}${fmt(mainChange)}</div>
        </div>
      </div>
      <div class="chart-container">${miniChart(ts.data, 'close')}</div>
    </div>

    <div class="card">
      <div class="card-title">LME 시세</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash</span>
          <span class="data-value">${fmt(cash.close)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M</span>
          <span class="data-value">${fmt(tm.close)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">시가</span>
          <span class="data-value">${fmt(tm.open ?? cash.open)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">고가</span>
          <span class="data-value">${fmt(tm.high ?? cash.high)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">저가</span>
          <span class="data-value">${fmt(tm.low ?? cash.low)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">미결제약정</span>
          <span class="data-value">${fmtInt(lme.open_interest)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Bid</span>
          <span class="data-value">${fmt(lme.bid)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Ask</span>
          <span class="data-value">${fmt(lme.ask)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">정산가</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash</span>
          <span class="data-value">${fmt(sett.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M</span>
          <span class="data-value">${fmt(sett['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">당월평균 Cash</span>
          <span class="data-value">${fmt(sett.monthly_avg?.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">당월평균 3M</span>
          <span class="data-value">${fmt(sett.monthly_avg?.['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">전월평균 Cash</span>
          <span class="data-value">${fmt(sett.prev_monthly_avg?.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">전월평균 3M</span>
          <span class="data-value">${fmt(sett.prev_monthly_avg?.['3m'])}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">LME 재고</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">현재고</span>
          <span class="data-value">${fmtInt(inv.current)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">변동</span>
          <span class="data-value change ${changeClass(inv.change)}">${changePrefix(inv.change)}${fmtInt(inv.change)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">반입</span>
          <span class="data-value">${fmtInt(inv['in'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">반출</span>
          <span class="data-value">${fmtInt(inv.out)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">On Warrant</span>
          <span class="data-value">${fmtInt(inv.on_warrant)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Cancelled Warrant</span>
          <span class="data-value">${fmtInt(inv.cancelled_warrant)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">SHFE 비교</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">SHFE 정산가</span>
          <span class="data-value">${fmtInt(shfe.shfe_settle)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">프리미엄 (USD)</span>
          <span class="data-value change ${changeClass(shfe.premium_usd)}">${fmt(shfe.premium_usd)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">LME 3M (CNY)</span>
          <span class="data-value">${fmtInt(shfe.lme_3m_cny)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">LME 3M (세금포함)</span>
          <span class="data-value">${fmtInt(shfe.lme_3m_incl_tax)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">원화 환산</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash (KRW)</span>
          <span class="data-value">${fmtInt(krw.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M (KRW)</span>
          <span class="data-value">${fmtInt(krw['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">적용환율</span>
          <span class="data-value">${fmt(krw.rate)}</span>
        </div>
      </div>
    </div>
  `;
}

async function loadMetal(metal) {
  if (cache[metal]) return cache[metal];
  const resp = await fetch(`${DATA_BASE}/metals/${metal}.json`);
  if (!resp.ok) return null;
  const data = await resp.json();
  cache[metal] = data;
  return data;
}

async function loadIndex() {
  const resp = await fetch(`${DATA_BASE}/index.json`);
  if (!resp.ok) return null;
  return resp.json();
}

function updateNav(activeMetal) {
  document.querySelectorAll('#metal-nav button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.metal === activeMetal);
  });
}

async function init() {
  const index = await loadIndex();
  if (index) {
    document.getElementById('last-updated').textContent = `업데이트: ${index.last_updated}`;
  }

  const metals = ['copper', 'aluminum', 'zinc', 'nickel', 'lead', 'tin'];
  for (const metal of metals) {
    const ts = await loadMetal(metal);
    if (ts) renderSection(metal, ts);
  }

  const firstData = cache['copper'];
  if (firstData?.data?.[0]?.krw?.rate) {
    document.getElementById('krw-rate').textContent = `USD/KRW: ${fmt(firstData.data[0].krw.rate)}`;
  }

  const container = document.getElementById('scroll-container');
  const sections = document.querySelectorAll('.metal-section');

  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        updateNav(entry.target.dataset.metal);
      }
    }
  }, { root: container, threshold: 0.5 });

  sections.forEach(s => observer.observe(s));

  document.querySelectorAll('#metal-nav button').forEach(btn => {
    btn.addEventListener('click', () => {
      const section = document.querySelector(`.metal-section[data-metal="${btn.dataset.metal}"]`);
      section.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

init();
