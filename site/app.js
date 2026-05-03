// LME Non-Ferrous Desk — vanilla JS (serverless GitHub Pages)
const DATA_BASE = '../data';

const METAL_NAMES_KO = { copper: '전기동', aluminum: '알루미늄', zinc: '아연', nickel: '니켈', lead: '납', tin: '주석' };
const METAL_NAMES_EN = { copper: 'Copper', aluminum: 'Aluminium', zinc: 'Zinc', nickel: 'Nickel', lead: 'Lead', tin: 'Tin' };
const METAL_SYMBOLS  = { copper: 'Cu', aluminum: 'Al', zinc: 'Zn', nickel: 'Ni', lead: 'Pb', tin: 'Sn' };
const METAL_ORDER    = ['copper', 'aluminum', 'zinc', 'nickel', 'lead', 'tin'];

const fmt = (n, d) => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: d ?? 2, maximumFractionDigits: d ?? 2 });
const fmtInt = (n) => (n == null || isNaN(n)) ? '—' : Math.round(n).toLocaleString('en-US');
const fmtSigned = (n, d) => {
  if (n == null || isNaN(n)) return '—';
  const s = fmt(Math.abs(n), d);
  if (n > 0) return '+' + s;
  if (n < 0) return '−' + s;
  return s;
};
const fmtSignedInt = (n) => {
  if (n == null || isNaN(n)) return '—';
  const s = fmtInt(Math.abs(n));
  if (n > 0) return '+' + s;
  if (n < 0) return '−' + s;
  return s;
};
const dirClass = (n) => (n == null || n === 0) ? 'flat' : (n > 0 ? 'up' : 'down');
const arrow = (n) => (n == null || n === 0) ? '·' : (n > 0 ? '▲' : '▼');
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function priceSeries(data, key = 'close') {
  return data.slice(0, 30).reverse().map(d => {
    const lme = d.lme || {};
    const ref = lme['3m'] || lme.cash || {};
    return { date: d.date, v: ref[key] != null ? ref[key] : null };
  }).filter(p => p.v != null);
}
function invSeries(data) {
  return data.slice(0, 30).reverse().map(d => ({
    date: d.date, v: (d.inventory && d.inventory.current != null) ? d.inventory.current : null
  })).filter(p => p.v != null);
}

function sparkline(series, opts = {}) {
  const h = opts.height || 28;
  const w = opts.width || 320;
  const sw = opts.strokeWidth || 1.25;
  if (!series || series.length < 2) return `<svg width="${w}" height="${h}" aria-hidden="true"></svg>`;
  const vals = series.map(p => p.v);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const pad = 2;
  const innerW = w - pad * 2, innerH = h - pad * 2;
  const step = innerW / (series.length - 1);
  const pts = series.map((p, i) => [pad + i * step, pad + innerH - ((p.v - min) / range) * innerH]);
  const dLine = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' ');
  const trending = vals[vals.length - 1] >= vals[0];
  const stroke = opts.accent || (trending ? 'var(--up)' : 'var(--down)');
  const id = 'spk-' + Math.random().toString(36).slice(2, 8);
  const dArea = dLine + ` L ${pts[pts.length-1][0].toFixed(2)} ${(h-pad).toFixed(2)} L ${pts[0][0].toFixed(2)} ${(h-pad).toFixed(2)} Z`;
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="display:block">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${stroke}" stop-opacity="0.18"/><stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${dArea}" fill="url(#${id})"/>
    <path d="${dLine}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${pts[pts.length-1][0]}" cy="${pts[pts.length-1][1]}" r="1.6" fill="${stroke}"/>
  </svg>`;
}

// --- Long-press copy ---
function bindLongPress(root) {
  root.querySelectorAll('[data-copy]').forEach(el => {
    let timer = null;
    const start = () => { timer = setTimeout(() => doCopy(el), 500); };
    const clear = () => { if (timer) { clearTimeout(timer); timer = null; } };
    el.addEventListener('mousedown', start);
    el.addEventListener('touchstart', start, { passive: true });
    el.addEventListener('mouseup', clear);
    el.addEventListener('mouseleave', clear);
    el.addEventListener('touchend', clear);
    el.addEventListener('touchcancel', clear);
  });
}
function doCopy(el) {
  const text = el.dataset.copy || el.textContent;
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(()=>{});
  el.classList.add('val-copied');
  const tag = document.createElement('span');
  tag.className = 'copied-tag';
  tag.textContent = '복사됨';
  el.appendChild(tag);
  setTimeout(() => { el.classList.remove('val-copied'); tag.remove(); }, 900);
}

// --- Hero (price-first) ---
function renderHero(metal, latest, series) {
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;
  const dir = dirClass(mainChange);
  const pctVal = (mainChange != null && tm.prev_close) ? (mainChange / tm.prev_close * 100) : null;
  const sym = METAL_SYMBOLS[metal];
  const ko = METAL_NAMES_KO[metal];
  const en = METAL_NAMES_EN[metal];

  return `<div class="hero hero--price">
    <div class="hero__top">
      <div class="hero__id">
        <div class="hero__sym mono">${sym}</div>
        <div>
          <div class="hero__ko">${ko}</div>
          <div class="hero__en">${en} · LME 3M · USD/t</div>
        </div>
      </div>
      <button class="hero__expand" data-expand="${metal}" aria-label="expand chart">
        <span class="mono">30D</span> <span style="opacity:.5">↗</span>
      </button>
    </div>
    <div class="hero__price-row">
      <span class="hero__price mono" data-copy="${mainPrice ?? ''}">${fmt(mainPrice)}</span>
    </div>
    <div class="hero__change mono ${dir}">
      <span>${arrow(mainChange)}</span>
      <span>${fmtSigned(mainChange)}</span>
      ${pctVal != null ? `<span class="hero__pct">${fmtSigned(pctVal, 2)}%</span>` : ''}
    </div>
    <div class="hero__spark" data-expand="${metal}">${sparkline(series, { height: 56, width: 320, strokeWidth: 1.5 })}</div>
    <div class="hero__ohlc mono">
      <div><span class="lbl">시가 O</span><span data-copy="${tm.open ?? cash.open ?? ''}">${fmt(tm.open ?? cash.open)}</span></div>
      <div><span class="lbl">고가 H</span><span data-copy="${tm.high ?? cash.high ?? ''}">${fmt(tm.high ?? cash.high)}</span></div>
      <div><span class="lbl">저가 L</span><span data-copy="${tm.low ?? cash.low ?? ''}">${fmt(tm.low ?? cash.low)}</span></div>
      <div><span class="lbl">종가 C</span><span data-copy="${tm.close ?? cash.close ?? ''}">${fmt(tm.close ?? cash.close)}</span></div>
    </div>
  </div>`;
}

function row(ko, en, value, opts = {}) {
  const display = opts.displayValue != null ? opts.displayValue : ((opts.prefix || '') + fmt(value) + (opts.suffix || ''));
  const cls = ['kv', opts.dim ? 'kv--dim' : '', opts.dir ? `kv--${opts.dir}` : ''].filter(Boolean).join(' ');
  const copy = opts.copyable === false ? '' : `data-copy="${esc(value ?? '')}"`;
  return `<div class="${cls}">
    <div class="kv__lbl">
      <span class="kv__ko">${esc(ko)}</span>
      ${en ? `<span class="kv__en">${esc(en)}</span>` : ''}
    </div>
    <span class="kv__val mono" ${copy}>${display}</span>
  </div>`;
}

function renderMetalSection(metal, ts) {
  const latest = ts && ts.data && ts.data[0];
  const ko = METAL_NAMES_KO[metal];
  const sym = METAL_SYMBOLS[metal];
  if (!latest) return `<section class="metal-section" data-metal="${metal}" data-screen-label="${sym} ${ko}"></section>`;

  const series = priceSeries(ts.data, 'close');
  const invSer = invSeries(ts.data);
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const inv = latest.inventory || {};
  const sett = latest.settlement || {};
  const shfe = latest.shfe || {};
  const krw = latest.krw || {};
  const hasCash = cash && cash.close != null;

  const monthlyDeltaCash = sett.monthly_avg && sett.prev_monthly_avg ? (sett.monthly_avg.cash - sett.prev_monthly_avg.cash) : null;
  const monthlyDelta3m = sett.monthly_avg && sett.prev_monthly_avg ? (sett.monthly_avg['3m'] - sett.prev_monthly_avg['3m']) : null;

  const lmeBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">LME 시세</span>
      <span class="block__h-en">LME quote · USD/t</span>
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('현금 Cash', '', cash.close, { dim: !hasCash })}
      ${row('3개월 3M', '', tm.close)}
      ${row('시가 Open', '', tm.open ?? cash.open, { dim: !hasCash && tm.open == null })}
      ${row('고가 High', '', tm.high ?? cash.high)}
      ${row('저가 Low', '', tm.low ?? cash.low)}
      ${row('전일종가', 'prev close', tm.prev_close ?? cash.prev_close)}
      ${row('매수호가', 'bid', lme.bid)}
      ${row('매도호가', 'ask', lme.ask)}
    </div>
    <div class="kv-grid kv-grid--1 kv-grid--accent">
      ${row('미결제약정', 'open interest · contracts', lme.open_interest, { displayValue: fmtInt(lme.open_interest) })}
    </div>
    ${!hasCash ? `<div class="block__note"><span class="dot dot--dim"></span> Cash 시세 미공개 — Zn/Pb/Ni/Sn은 LME에서 3M만 게시</div>` : ''}
  </div>`;

  const settBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">정산가</span>
      <span class="block__h-en">Settlement · USD/t</span>
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('Cash 정산', 'cash settle', sett.cash)}
      ${row('3M 정산', '3M settle', sett['3m'])}
      ${row('당월평균 Cash', 'MTD avg cash', sett.monthly_avg?.cash, { dir: dirClass(monthlyDeltaCash) })}
      ${row('당월평균 3M', 'MTD avg 3M', sett.monthly_avg?.['3m'], { dir: dirClass(monthlyDelta3m) })}
      ${row('전월평균 Cash', 'prev mo. cash', sett.prev_monthly_avg?.cash, { dim: true })}
      ${row('전월평균 3M', 'prev mo. 3M', sett.prev_monthly_avg?.['3m'], { dim: true })}
    </div>
    <div class="forwards">
      <div class="forwards__lbl">
        <span class="block__h-ko" style="font-size:10.5px">선물커브</span>
        <span class="block__h-en">forward curve</span>
      </div>
      <div class="forwards__row mono">
        <div><div class="lbl">M+1</div><div>${fmt(sett.forwards?.m1)}</div></div>
        <div><div class="lbl">M+2</div><div>${fmt(sett.forwards?.m2)}</div></div>
        <div><div class="lbl">M+3</div><div>${fmt(sett.forwards?.m3)}</div></div>
      </div>
    </div>
  </div>`;

  const invBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">LME 재고</span>
      <span class="block__h-en">Inventory · tonnes</span>
      <div class="block__h-spark">${sparkline(invSer, { height: 20, width: 70, strokeWidth: 1, accent: 'var(--text-mute)' })}</div>
    </div>
    <div class="inv-row">
      <div class="inv-row__main mono">
        <span data-copy="${inv.current ?? ''}">${fmtInt(inv.current)}</span>
        <span class="inv-row__delta mono ${dirClass(inv.change)}">${arrow(inv.change)} ${fmtSignedInt(inv.change)}</span>
      </div>
      <div class="inv-row__sub mono"><span class="lbl">전일</span> ${fmtInt(inv.prev)}</div>
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('반입 In', '', inv['in'], { displayValue: fmtInt(inv['in']) })}
      ${row('반출 Out', '', inv.out, { displayValue: fmtInt(inv.out) })}
      ${row('유효재고', 'on warrant', inv.on_warrant, { displayValue: fmtInt(inv.on_warrant) })}
      ${row('취소창고', 'cancelled warrant', inv.cancelled_warrant, { displayValue: fmtInt(inv.cancelled_warrant) })}
    </div>
    <div class="kv-grid kv-grid--1">
      ${row('취소창고 변동', 'CW change', inv.cw_change, { displayValue: fmtSignedInt(inv.cw_change), dir: dirClass(inv.cw_change) })}
    </div>
  </div>`;

  const shfeBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">SHFE 비교</span>
      <span class="block__h-en">SHFE arbitrage</span>
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('SHFE 정산가', 'SHFE settle · CNY', shfe.shfe_settle, { displayValue: fmtInt(shfe.shfe_settle) })}
      ${row('SHFE 3M', 'SHFE 3M · CNY', shfe.shfe_3m, { displayValue: fmtInt(shfe.shfe_3m) })}
      ${row('LME 3M (CNY)', 'excl. tax', shfe.lme_3m_cny, { displayValue: fmtInt(shfe.lme_3m_cny) })}
      ${row('LME 3M (CNY)', 'incl. tax', shfe.lme_3m_incl_tax, { displayValue: fmtInt(shfe.lme_3m_incl_tax) })}
      ${row('LME 현금 (CNY)', 'excl. tax', shfe.lme_near_cny, { displayValue: fmtInt(shfe.lme_near_cny), dim: !hasCash })}
      ${row('LME 현금 (CNY)', 'incl. tax', shfe.lme_near_incl_tax, { displayValue: fmtInt(shfe.lme_near_incl_tax), dim: !hasCash })}
    </div>
    <div class="kv-grid kv-grid--1 kv-grid--accent">
      ${row('프리미엄', 'premium · USD/t', shfe.premium_usd, { displayValue: fmtSigned(shfe.premium_usd, 2), dir: dirClass(shfe.premium_usd) })}
    </div>
  </div>`;

  const krwBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">원화 환산</span>
      <span class="block__h-en">KRW conversion · ₩/t</span>
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('Cash', '₩', krw.cash, { displayValue: fmtInt(krw.cash), prefix: '₩', dim: !hasCash })}
      ${row('3M', '₩', krw['3m'], { displayValue: fmtInt(krw['3m']), prefix: '₩' })}
    </div>
    <div class="kv-grid kv-grid--2">
      ${row('적용환율', 'applied FX', krw.rate)}
      ${row('환율 출처', 'source', krw.source, { displayValue: (krw.source || '—').toUpperCase(), copyable: false })}
    </div>
  </div>`;

  const metaBlock = `<div class="block block--meta">
    <span class="lbl">데이터 기준 · as of</span>
    <span class="mono">${esc(latest.date)}</span>
    <span class="block__sep">·</span>
    <span class="lbl">단위 · unit</span>
    <span class="mono">${esc(ts.unit || 'USD/t')}</span>
  </div>`;

  return `<section class="metal-section" data-metal="${metal}" data-screen-label="${sym} ${ko}">
    ${renderHero(metal, latest, series)}
    ${lmeBlock}
    ${settBlock}
    ${invBlock}
    ${shfeBlock}
    ${krwBlock}
    ${metaBlock}
  </section>`;
}

function renderNav(metals) {
  return METAL_ORDER.map(m => {
    const ts = metals[m];
    const latest = ts && ts.data && ts.data[0];
    const lme = (latest && latest.lme) || {};
    const tm = lme['3m'] || lme.cash || {};
    const close = tm.close;
    const change = tm.change;
    const pct = (change != null && tm.prev_close) ? (change / tm.prev_close * 100) : null;
    const dir = dirClass(change);
    return `<button class="nav-pill nav-pill--${dir}" data-metal="${m}">
      <span class="nav-pill__sym mono">${METAL_SYMBOLS[m]}</span>
      <div class="nav-pill__col">
        <span class="nav-pill__price mono">${fmt(close, close > 1000 ? 0 : 2)}</span>
        <span class="nav-pill__pct mono ${dir}">${arrow(change)} ${pct == null ? '—' : fmtSigned(pct, 2) + '%'}</span>
      </div>
    </button>`;
  }).join('');
}

function renderHeader(latestDate, krwRate, krwSrc, market) {
  const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
  const macros = market ? [
    { lbl: 'KRW/USD', v: fmt(market.krw_usd), c: market.krw_change },
    { lbl: 'WTI', v: fmt(market.wti), c: market.wti_change },
    { lbl: 'S&P 500', v: fmt(market.sp500, 0), c: market.sp500_change },
    { lbl: 'DOW', v: fmt(market.dow, 0), c: market.dow_change },
    { lbl: 'EUR/USD', v: fmt(market.eur_usd, 4), c: null },
    { lbl: 'JPY/USD', v: fmt(market.jpy_usd, 2), c: null },
  ] : [];
  return `<header class="app__header">
    <div class="app__head-l">
      <div class="brand">
        <span class="brand__mark mono">LME</span>
        <span class="brand__sub">비철금속 데스크 · Non-Ferrous Desk</span>
      </div>
    </div>
    <div class="app__head-r mono">
      <span class="dot dot--live"></span>
      <span class="head__ts">${esc(latestDate || '')} · ${ts}</span>
    </div>
  </header>
  <div class="app__rate">
    <div class="rate__main">
      <span class="lbl">USD/KRW</span>
      <span class="mono rate__v">${fmt(krwRate)}</span>
      <span class="rate__src">${esc((krwSrc || '—').toUpperCase())}</span>
    </div>
    <div class="macro">
      ${macros.map(it => `<div class="macro__item">
        <span class="macro__lbl">${esc(it.lbl)}</span>
        <span class="mono macro__v">${it.v}</span>
        ${it.c != null ? `<span class="mono macro__c ${dirClass(it.c)}">${arrow(it.c)} ${fmtSigned(it.c, 2)}</span>` : ''}
      </div>`).join('')}
    </div>
  </div>`;
}

// --- Expanded chart overlay ---
function openChart(label, series) {
  const W = 360, H = 200, padL = 44, padR = 12, padT = 16, padB = 28;
  if (!series || series.length < 2) return;
  const vals = series.map(p => p.v);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const step = innerW / (series.length - 1);
  const pts = series.map((p, i) => [padL + i * step, padT + innerH - ((p.v - min) / range) * innerH]);
  const dLine = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' ');
  const dArea = dLine + ` L ${pts[pts.length-1][0].toFixed(2)} ${(padT+innerH).toFixed(2)} L ${pts[0][0].toFixed(2)} ${(padT+innerH).toFixed(2)} Z`;
  const trending = vals[vals.length - 1] >= vals[0];
  const stroke = trending ? 'var(--up)' : 'var(--down)';
  const ticks = [max, (max + min) / 2, min];
  const dates = series.map(p => p.date);

  const cur = series[series.length - 1];
  const delta = cur.v - series[0].v;
  const deltaPct = delta / series[0].v * 100;

  const overlay = document.createElement('div');
  overlay.className = 'chart-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.innerHTML = `
    <div class="chart-overlay__backdrop"></div>
    <div class="chart-overlay__panel">
      <div class="chart-overlay__head">
        <div>
          <div class="chart-overlay__title">${esc(label)}</div>
          <div class="chart-overlay__sub">최근 30일 · 30-day · ${esc(dates[0])} → ${esc(dates[dates.length-1])}</div>
        </div>
        <button class="chart-overlay__close" aria-label="close">✕</button>
      </div>
      <div class="chart-overlay__readout">
        <div><div class="lbl"><span data-readout="date">${esc(cur.date)}</span></div><div class="val mono" data-readout="val">${fmt(cur.v)}</div></div>
        <div><div class="lbl">변동 vs 시작 · vs start</div><div class="val mono ${dirClass(delta)}">${fmtSigned(delta)} <span class="muted">(${fmtSigned(deltaPct, 2)}%)</span></div></div>
      </div>
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="200">
        <defs><linearGradient id="exp-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${stroke}" stop-opacity="0.22"/><stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
        </linearGradient></defs>
        ${ticks.map((t, i) => {
          const y = padT + (H - padT - padB) * (i / (ticks.length - 1));
          return `<g><line x1="${padL}" x2="${W-padR}" y1="${y}" y2="${y}" stroke="var(--border)" stroke-dasharray="2 3"/>
            <text x="${padL-6}" y="${y+3}" text-anchor="end" class="chart-tick">${fmt(t, t > 1000 ? 0 : 2)}</text></g>`;
        }).join('')}
        <path d="${dArea}" fill="url(#exp-fill)"/>
        <path d="${dLine}" fill="none" stroke="${stroke}" stroke-width="1.5"/>
        <text x="${padL}" y="${H-8}" class="chart-tick">${esc(dates[0])}</text>
        <text x="${W-padR}" y="${H-8}" text-anchor="end" class="chart-tick">${esc(dates[dates.length-1])}</text>
      </svg>
    </div>`;

  const close = () => overlay.remove();
  overlay.querySelector('.chart-overlay__backdrop').addEventListener('click', close);
  overlay.querySelector('.chart-overlay__close').addEventListener('click', close);

  const svg = overlay.querySelector('svg');
  const readoutDate = overlay.querySelector('[data-readout="date"]');
  const readoutVal = overlay.querySelector('[data-readout="val"]');
  function onMove(e) {
    const rect = svg.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const x = cx * (W / rect.width);
    let best = 0, bestD = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const d = Math.abs(pts[i][0] - x);
      if (d < bestD) { bestD = d; best = i; }
    }
    const p = series[best];
    readoutDate.textContent = p.date;
    readoutVal.textContent = fmt(p.v);
  }
  svg.addEventListener('mousemove', onMove);
  svg.addEventListener('touchmove', onMove);

  document.body.appendChild(overlay);
}

// --- Pull-to-refresh ---
function bindPTR(scroller, onRefresh) {
  let startY = null, pull = 0;
  let ptrEl = null;
  function setPull(p) {
    pull = p;
    if (p > 0) {
      if (!ptrEl) {
        ptrEl = document.createElement('div');
        ptrEl.className = 'ptr';
        ptrEl.innerHTML = `<span class="mono">↓ 당겨서 갱신 · pull</span>`;
        scroller.parentNode.insertBefore(ptrEl, scroller);
      }
      ptrEl.style.height = p + 'px';
      ptrEl.querySelector('span').textContent = p > 50 ? '↑ 놓아서 갱신 · release' : '↓ 당겨서 갱신 · pull';
    } else if (ptrEl) {
      ptrEl.style.height = '0';
      setTimeout(() => { ptrEl?.remove(); ptrEl = null; }, 200);
    }
  }
  scroller.addEventListener('touchstart', e => {
    if (scroller.scrollTop <= 0) startY = e.touches[0].clientY;
    else startY = null;
  }, { passive: true });
  scroller.addEventListener('touchmove', e => {
    if (startY == null) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 0 && scroller.scrollTop <= 0) {
      setPull(Math.min(80, dy * 0.5));
      e.preventDefault();
    }
  }, { passive: false });
  scroller.addEventListener('touchend', () => {
    if (pull > 50) {
      ptrEl.querySelector('span').textContent = '⟳ 갱신중 · refreshing';
      ptrEl.querySelector('span').classList.add('ptr--spin');
      onRefresh();
      setTimeout(() => setPull(0), 900);
    } else {
      setPull(0);
    }
    startY = null;
  });
}

// --- App init ---
async function loadAll() {
  const [index, ...metalsArr] = await Promise.all([
    fetch(`${DATA_BASE}/index.json`).then(r => r.json()).catch(() => null),
    ...METAL_ORDER.map(m => fetch(`${DATA_BASE}/metals/${m}.json`).then(r => r.json()).catch(() => null)),
  ]);
  const metals = {};
  METAL_ORDER.forEach((m, i) => metals[m] = metalsArr[i]);
  return { index, metals };
}

async function init() {
  const { index, metals } = await loadAll();
  const root = document.getElementById('root');
  const latest0 = metals.copper?.data?.[0];
  const latestDate = metals.copper?.last_updated || latest0?.date;
  const krw = latest0?.krw || {};
  const market = latest0?.market || {
    krw_usd: krw.rate, krw_change: null,
    wti: null, wti_change: null, sp500: null, sp500_change: null,
    dow: null, dow_change: null, eur_usd: null, jpy_usd: null,
  };

  root.outerHTML = `<div class="app" id="root" data-density="compact" data-lang="ko" data-accent="muted">
    ${renderHeader(latestDate, krw.rate, krw.source, market)}
    <nav class="app__nav nav--pricepct">${renderNav(metals)}</nav>
    <div class="app__scroller">
      ${METAL_ORDER.map(m => renderMetalSection(m, metals[m])).join('')}
      <footer class="app__footer">
        <div class="mono">END · 데이터 끝</div>
        <div class="lbl">Source: NH선물 · LME · SHFE · BOK · PDF · 마감 기준</div>
      </footer>
    </div>
  </div>`;

  const app = document.getElementById('root');
  const scroller = app.querySelector('.app__scroller');
  const nav = app.querySelector('.app__nav');

  // Long-press copy
  bindLongPress(app);

  // Nav click → scroll
  nav.querySelectorAll('.nav-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = btn.dataset.metal;
      const sec = scroller.querySelector(`.metal-section[data-metal="${m}"]`);
      sec?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // IntersectionObserver: active sync + entering animation
  const sections = scroller.querySelectorAll('.metal-section');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('is-entering');
        if (e.intersectionRatio > 0.5) {
          const m = e.target.dataset.metal;
          nav.querySelectorAll('.nav-pill').forEach(b => b.classList.toggle('is-active', b.dataset.metal === m));
        }
      }
    });
  }, { root: scroller, threshold: [0, 0.5, 1] });
  sections.forEach(s => obs.observe(s));

  // Hero expand → chart overlay
  app.querySelectorAll('[data-expand]').forEach(el => {
    el.addEventListener('click', () => {
      const m = el.dataset.expand;
      const ts = metals[m];
      if (!ts) return;
      const series = priceSeries(ts.data, 'close');
      openChart(`${METAL_NAMES_KO[m]} · ${METAL_SYMBOLS[m]} 3M`, series);
    });
  });

  // Pull-to-refresh
  bindPTR(scroller, () => location.reload());
}

init().catch(err => {
  document.getElementById('root').innerHTML = `<pre style="color:#c87a6a;padding:20px">${esc(err.message || err)}</pre>`;
});
