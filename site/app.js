// LME Non-Ferrous Desk — vanilla JS (serverless GitHub Pages)
// Data: Apache Parquet via hyparquet (ESM, ~25KB, no WASM)
// Pinned exact versions to remove auto-upgrade supply-chain risk.
import { parquetReadObjects } from 'https://cdn.jsdelivr.net/npm/hyparquet@1.25.6/+esm';
import { compressors } from 'https://cdn.jsdelivr.net/npm/hyparquet-compressors@1.1.1/+esm';
import {
  loadNews, loadEvents, loadTweaks, saveTweaks, lastSeenAt, markSeen,
  unseenCount, chartMarkersFor,
  renderBell, renderDrawer, renderTweaksGear, renderTweaksPanel,
  bindDrawer, bindTweaks, newsConstants,
} from './news.js';

const DATA_BASE = '../data';

// Metal metadata is sourced from data/manifest.json (single source of truth).
// These are populated in init() after manifest loads; modules use them via closures.
let METALS = {};       // LME 6종 { copper: { symbol, unit, name_ko, name_en, years }, ... }
let METAL_ORDER = [];  // canonical render order
let MINOR_METALS = {}; // 비철 LME 비상장 minor (Sb 등) — schema=minor_regional
let MINOR_ORDER = [];

// hyparquet returns BigInt for int64 columns — coerce to Number for JS math.
const num = (v) => v == null ? null : (typeof v === 'bigint' ? Number(v) : v);

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

// --- Parquet flat-row → nested entry adapter (UI consumes nested) ---
function unflatten(r) {
  return {
    date: r.date,
    lme: {
      cash: {
        open: num(r.lme_cash_open), high: num(r.lme_cash_high), low: num(r.lme_cash_low),
        close: num(r.lme_cash_close), change: num(r.lme_cash_change), prev_close: num(r.lme_cash_prev),
      },
      '3m': {
        open: num(r.lme_3m_open), high: num(r.lme_3m_high), low: num(r.lme_3m_low),
        close: num(r.lme_3m_close), change: num(r.lme_3m_change), prev_close: num(r.lme_3m_prev),
      },
      bid: num(r.lme_bid), ask: num(r.lme_ask), open_interest: num(r.lme_oi),
    },
    settlement: {
      cash: num(r.sett_cash), '3m': num(r.sett_3m),
      monthly_avg: { cash: num(r.sett_mavg_cash), '3m': num(r.sett_mavg_3m) },
      prev_monthly_avg: { cash: num(r.sett_prev_mavg_cash), '3m': num(r.sett_prev_mavg_3m) },
      forwards: { m1: num(r.sett_fwd_m1), m2: num(r.sett_fwd_m2), m3: num(r.sett_fwd_m3) },
    },
    inventory: {
      prev: num(r.inv_prev), in: num(r.inv_in), out: num(r.inv_out), current: num(r.inv_current),
      change: num(r.inv_change), on_warrant: num(r.inv_on_warrant),
      cancelled_warrant: num(r.inv_cancelled_warrant), cw_change: num(r.inv_cw_change),
    },
    shfe: {
      lme_3m_cny: num(r.shfe_lme_3m_cny), lme_near_cny: num(r.shfe_lme_near_cny),
      lme_3m_incl_tax: num(r.shfe_lme_3m_incl_tax), lme_near_incl_tax: num(r.shfe_lme_near_incl_tax),
      shfe_3m: num(r.shfe_3m), shfe_settle: num(r.shfe_settle), premium_usd: num(r.shfe_premium_usd),
    },
    krw: {
      cash: num(r.krw_cash), '3m': num(r.krw_3m), rate: num(r.krw_rate), source: r.krw_source,
    },
  };
}

async function loadParquet(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`fetch ${url}: ${resp.status}`);
  const buf = await resp.arrayBuffer();
  return await parquetReadObjects({ file: buf, compressors });
}

// --- Series helpers (work on nested entries) ---
function priceSeries(data, key = 'close', count = 30) {
  return data.slice(0, count).reverse().map(d => {
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
  const sym = METALS[metal].symbol;
  const ko = METALS[metal].name_ko;
  const en = METALS[metal].name_en;

  return `<div class="hero hero--price">
    <div class="hero__top">
      <div class="hero__id">
        <div class="hero__sym mono">${sym}</div>
        <div>
          <div class="hero__ko">${ko}</div>
          <div class="hero__en">${en} · LME 3M · USD/t</div>
        </div>
      </div>
    </div>
    <div class="hero__price-row">
      <span class="hero__price mono" data-copy="${mainPrice ?? ''}"><span class="hero__ccy">$</span>${fmt(mainPrice)}</span>
    </div>
    <div class="hero__change mono ${dir}">
      <span>${arrow(mainChange)}</span>
      <span>${mainChange != null ? (mainChange >= 0 ? '+$' : '−$') + fmt(Math.abs(mainChange)) : '—'}</span>
      ${pctVal != null ? `<span class="hero__pct">${fmtSigned(pctVal, 2)}%</span>` : ''}
    </div>
    <div class="hero__spark" data-expand="${metal}">${sparkline(series, { height: 56, width: 320, strokeWidth: 1.5 })}</div>
    <div class="hero__ohlc mono">
      <div><span class="lbl">시가 O</span><span data-copy="${tm.open ?? cash.open ?? ''}">$${fmt(tm.open ?? cash.open)}</span></div>
      <div><span class="lbl">고가 H</span><span data-copy="${tm.high ?? cash.high ?? ''}">$${fmt(tm.high ?? cash.high)}</span></div>
      <div><span class="lbl">저가 L</span><span data-copy="${tm.low ?? cash.low ?? ''}">$${fmt(tm.low ?? cash.low)}</span></div>
      <div><span class="lbl">종가 C</span><span data-copy="${tm.close ?? cash.close ?? ''}">$${fmt(tm.close ?? cash.close)}</span></div>
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
  const ko = METALS[metal].name_ko;
  const sym = METALS[metal].symbol;
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
      ${row('현금 Cash', '', cash.close, { dim: !hasCash, prefix: '$' })}
      ${row('3개월 3M', '', tm.close, { prefix: '$' })}
      ${row('시가 Open', '', tm.open ?? cash.open, { dim: !hasCash && tm.open == null, prefix: '$' })}
      ${row('고가 High', '', tm.high ?? cash.high, { prefix: '$' })}
      ${row('저가 Low', '', tm.low ?? cash.low, { prefix: '$' })}
      ${row('전일종가', 'prev close', tm.prev_close ?? cash.prev_close, { prefix: '$' })}
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
      ${row('Cash 정산', 'cash settle', sett.cash, { prefix: '$' })}
      ${row('3M 정산', '3M settle', sett['3m'], { prefix: '$' })}
      ${row('당월평균 Cash', 'MTD avg cash', sett.monthly_avg?.cash, { dir: dirClass(monthlyDeltaCash), prefix: '$' })}
      ${row('당월평균 3M', 'MTD avg 3M', sett.monthly_avg?.['3m'], { dir: dirClass(monthlyDelta3m), prefix: '$' })}
      ${row('전월평균 Cash', 'prev mo. cash', sett.prev_monthly_avg?.cash, { dim: true, prefix: '$' })}
      ${row('전월평균 3M', 'prev mo. 3M', sett.prev_monthly_avg?.['3m'], { dim: true, prefix: '$' })}
    </div>
    <div class="forwards">
      <div class="forwards__lbl">
        <span class="block__h-ko" style="font-size:10.5px">선물커브</span>
        <span class="block__h-en">forward curve</span>
      </div>
      <div class="forwards__row mono">
        <div><div class="lbl">M+1</div><div>$${fmt(sett.forwards?.m1)}</div></div>
        <div><div class="lbl">M+2</div><div>$${fmt(sett.forwards?.m2)}</div></div>
        <div><div class="lbl">M+3</div><div>$${fmt(sett.forwards?.m3)}</div></div>
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
      ${row('SHFE 정산가', 'SHFE settle · CNY', shfe.shfe_settle, { displayValue: '¥' + fmtInt(shfe.shfe_settle) })}
      ${row('SHFE 3M', 'SHFE 3M · CNY', shfe.shfe_3m, { displayValue: '¥' + fmtInt(shfe.shfe_3m) })}
      ${row('LME 3M (CNY)', 'excl. tax', shfe.lme_3m_cny, { displayValue: '¥' + fmtInt(shfe.lme_3m_cny) })}
      ${row('LME 3M (CNY)', 'incl. tax', shfe.lme_3m_incl_tax, { displayValue: '¥' + fmtInt(shfe.lme_3m_incl_tax) })}
      ${row('LME 현금 (CNY)', 'excl. tax', shfe.lme_near_cny, { displayValue: '¥' + fmtInt(shfe.lme_near_cny), dim: !hasCash })}
      ${row('LME 현금 (CNY)', 'incl. tax', shfe.lme_near_incl_tax, { displayValue: '¥' + fmtInt(shfe.lme_near_incl_tax), dim: !hasCash })}
    </div>
    <div class="kv-grid kv-grid--1 kv-grid--accent">
      ${row('프리미엄', 'premium · USD/t', shfe.premium_usd, { displayValue: (shfe.premium_usd != null ? (shfe.premium_usd >= 0 ? '+$' : '−$') + fmt(Math.abs(shfe.premium_usd), 2) : '—'), dir: dirClass(shfe.premium_usd) })}
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
      ${row('적용환율', 'applied FX', krw.rate, { prefix: '₩' })}
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

// --- Minor metal (Sb 등) — LME 비상장 regional schema ---
const REGION_LABEL = {
  exw_china:   { ko: '중국 EXW',    en: 'EXW China' },
  fob_china:   { ko: '중국 FOB',    en: 'FOB China' },
  port_india:  { ko: '인도 도착',   en: 'India CIF' },
  rotterdam:   { ko: '로테르담',    en: 'Rotterdam' },
  baltimore:   { ko: '볼티모어',    en: 'Baltimore' },
};

async function loadMinorLatest(metal) {
  const url = `${DATA_BASE}/series/${metal}/latest.parquet`;
  const rows = await loadParquet(url);
  return rows.map(r => ({
    date: r.date,
    exw_china:  num(r.exw_china),
    fob_china:  num(r.fob_china),
    port_india: num(r.port_india),
    rotterdam:  num(r.rotterdam),
    baltimore:  num(r.baltimore),
    _source:    r._source,
  })).sort((a, b) => a.date < b.date ? 1 : -1);
}

function minorPriceSeries(data, region = 'exw_china', count = 24) {
  return data.slice(0, count).reverse()
    .map(d => ({ date: d.date, v: d[region] != null ? d[region] : null }))
    .filter(p => p.v != null);
}

function renderMinorMetalSection(metal, ts, meta) {
  const latest = ts && ts.data && ts.data[0];
  const sym = meta.symbol;
  const ko = meta.name_ko;
  if (!latest) return `<section class="metal-section metal-section--minor" data-metal="${metal}" data-screen-label="${sym} ${ko}"></section>`;

  const series = minorPriceSeries(ts.data, 'exw_china', 24);
  // Hero: EXW China 기준 (가장 안정적 시계열)
  const mainPrice = latest.exw_china;
  const prev = ts.data[1]?.exw_china ?? null;
  const change = (mainPrice != null && prev != null) ? mainPrice - prev : null;
  const dir = dirClass(change);
  const pct = (change != null && prev) ? (change / prev * 100) : null;

  const regions = ['exw_china', 'fob_china', 'port_india', 'rotterdam', 'baltimore'];

  const hero = `<div class="hero hero--price">
    <div class="hero__top">
      <div class="hero__id">
        <div class="hero__sym mono">${sym}</div>
        <div>
          <div class="hero__ko">${esc(ko)}</div>
          <div class="hero__en">${esc(meta.name_en)} · ${esc(meta.grade || '')} · USD/t</div>
        </div>
      </div>
      <span class="badge-minor mono" title="LME 비상장">MINOR</span>
    </div>
    <div class="hero__price-row">
      <span class="hero__price mono" data-copy="${mainPrice ?? ''}"><span class="hero__ccy">$</span>${fmt(mainPrice)}</span>
      <span class="hero__price-tag lbl">EXW China · 기준</span>
    </div>
    <div class="hero__change mono ${dir}">
      <span>${arrow(change)}</span>
      <span>${change != null ? (change >= 0 ? '+$' : '−$') + fmt(Math.abs(change)) : '—'}</span>
      ${pct != null ? `<span class="hero__pct">${fmtSigned(pct, 2)}%</span>` : ''}
      <span class="lbl"> · vs prev pub.</span>
    </div>
    <div class="hero__spark" data-expand-minor="${metal}">${sparkline(series, { height: 56, width: 320, strokeWidth: 1.5 })}</div>
  </div>`;

  const regionsBlock = `<div class="block">
    <div class="block__h">
      <span class="block__h-ko">지역별 시세</span>
      <span class="block__h-en">Regional · USD/t</span>
    </div>
    <div class="kv-grid kv-grid--2">
      ${regions.map(r => {
        const lbl = REGION_LABEL[r];
        const v = latest[r];
        const prevV = ts.data[1]?.[r];
        const ch = (v != null && prevV != null) ? v - prevV : null;
        return row(lbl.ko, lbl.en, v, {
          dim: v == null,
          prefix: '$',
          dir: dirClass(ch),
        });
      }).join('')}
    </div>
    <div class="block__note">
      <span class="dot dot--dim"></span>
      LME 비상장 · 출처 ${esc(latest._source || meta.source || '—')} · ${esc(meta.update_freq || 'monthly')} 갱신
    </div>
  </div>`;

  const metaBlock = `<div class="block block--meta">
    <span class="lbl">데이터 기준 · as of</span>
    <span class="mono">${esc(latest.date)}</span>
    <span class="block__sep">·</span>
    <span class="lbl">grade</span>
    <span class="mono">${esc(meta.grade || '—')}</span>
  </div>`;

  return `<section class="metal-section metal-section--minor" data-metal="${metal}" data-screen-label="${sym} ${ko}">
    ${hero}
    ${regionsBlock}
    ${metaBlock}
  </section>`;
}

function renderNav(metals, minors) {
  const lmePills = METAL_ORDER.map(m => {
    const ts = metals[m];
    const latest = ts && ts.data && ts.data[0];
    const lme = (latest && latest.lme) || {};
    const tm = lme['3m'] || lme.cash || {};
    const close = tm.close;
    const change = tm.change;
    const pct = (change != null && tm.prev_close) ? (change / tm.prev_close * 100) : null;
    const dir = dirClass(change);
    return `<button class="nav-pill nav-pill--${dir}" data-metal="${m}">
      <span class="nav-pill__sym mono">${METALS[m].symbol}</span>
      <div class="nav-pill__col">
        <span class="nav-pill__price mono">$${fmt(close, close > 1000 ? 0 : 2)}</span>
        <span class="nav-pill__pct mono ${dir}">${arrow(change)} ${pct == null ? '—' : fmtSigned(pct, 2) + '%'}</span>
      </div>
    </button>`;
  }).join('');

  const minorPills = MINOR_ORDER.map(m => {
    const ts = minors[m];
    const latest = ts && ts.data && ts.data[0];
    const meta = MINOR_METALS[m];
    const close = latest?.exw_china;
    const prev = ts?.data?.[1]?.exw_china;
    const change = (close != null && prev != null) ? close - prev : null;
    const pct = (change != null && prev) ? (change / prev * 100) : null;
    const dir = dirClass(change);
    return `<button class="nav-pill nav-pill--${dir} nav-pill--minor" data-metal="${m}" title="${esc(meta.name_ko)} (LME 비상장)">
      <span class="nav-pill__sym mono">${esc(meta.symbol)}</span>
      <div class="nav-pill__col">
        <span class="nav-pill__price mono">$${fmt(close, close > 1000 ? 0 : 2)}</span>
        <span class="nav-pill__pct mono ${dir}">${arrow(change)} ${pct == null ? '—' : fmtSigned(pct, 2) + '%'}</span>
      </div>
    </button>`;
  }).join('');

  return lmePills + (minorPills ? `<div class="nav-pill__sep" aria-hidden="true"></div>` + minorPills : '');
}

function renderHeader(latestDate, krwRate, krwSrc, unseen) {
  const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
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
      ${renderBell(unseen)}
      ${renderTweaksGear()}
    </div>
  </header>
  <div class="app__rate">
    <div class="rate__main">
      <span class="lbl">USD/KRW</span>
      <span class="mono rate__v">₩${fmt(krwRate)}</span>
      <span class="rate__src">${esc((krwSrc || '—').toUpperCase())}</span>
    </div>
  </div>`;
}

// --- Expanded chart overlay ---
// opts.markers: [{date, kind:'news'|'event', sentiment, title, url, eventType, magnitude}]
function openChart(label, series, opts = {}) {
  const ccy = opts.ccy || '$';
  const fmtCcy = (n, d) => (n == null || isNaN(n)) ? '—' : ccy + fmt(n, d);
  const fmtCcySigned = (n, d) => {
    if (n == null || isNaN(n)) return '—';
    const s = ccy + fmt(Math.abs(n), d);
    if (n > 0) return '+' + s;
    if (n < 0) return '−' + s;
    return s;
  };

  const W = 360, H = 200, padL = 56, padR = 12, padT = 16, padB = 28;
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

  const latest = series[series.length - 1];
  // "vs 최신" semantics: how much has price moved from the hovered date to now.
  // Default (no hover): use the previous day → daily change.
  const defaultRef = series.length >= 2 ? series[series.length - 2] : latest;
  const initDelta = latest.v - defaultRef.v;
  const initDeltaPct = defaultRef.v ? (initDelta / defaultRef.v * 100) : 0;

  const overlay = document.createElement('div');
  overlay.className = 'chart-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.innerHTML = `
    <div class="chart-overlay__backdrop"></div>
    <div class="chart-overlay__panel">
      <div class="chart-overlay__head">
        <div>
          <div class="chart-overlay__title">${esc(label)}</div>
          <div class="chart-overlay__sub">${esc(dates[0])} → ${esc(dates[dates.length-1])} · ${dates.length}일</div>
        </div>
        <button class="chart-overlay__close" aria-label="close">✕</button>
      </div>
      <div class="chart-overlay__readout">
        <div><div class="lbl"><span data-readout="date">${esc(defaultRef.date)} → ${esc(latest.date)}</span></div><div class="val mono" data-readout="val">${fmtCcy(defaultRef.v)} → ${fmtCcy(latest.v)}</div></div>
        <div><div class="lbl"><span data-readout="dlbl">최신까지 변동 · vs latest</span></div><div class="val mono ${dirClass(initDelta)}" data-readout="delta">${fmtCcySigned(initDelta)} <span class="muted">(${fmtSigned(initDeltaPct, 2)}%)</span></div></div>
      </div>
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="200" style="touch-action:none">
        <defs><linearGradient id="exp-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${stroke}" stop-opacity="0.22"/><stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
        </linearGradient></defs>
        ${ticks.map((t, i) => {
          const y = padT + (H - padT - padB) * (i / (ticks.length - 1));
          return `<g><line x1="${padL}" x2="${W-padR}" y1="${y}" y2="${y}" stroke="var(--border)" stroke-dasharray="2 3"/>
            <text x="${padL-6}" y="${y+3}" text-anchor="end" class="chart-tick">${ccy}${fmt(t, t > 1000 ? 0 : 2)}</text></g>`;
        }).join('')}
        <path d="${dArea}" fill="url(#exp-fill)"/>
        <path d="${dLine}" fill="none" stroke="${stroke}" stroke-width="1.5"/>
        ${(() => {
          if (!opts.markers || !opts.markers.length) return '';
          const dateToIdx = new Map();
          for (let i = 0; i < series.length; i++) dateToIdx.set(series[i].date, i);
          return opts.markers.map((mk, idx) => {
            const i = dateToIdx.get(mk.date);
            if (i == null) return '';
            const x = pts[i][0];
            const color = mk.kind === 'news'
              ? (mk.sentiment > 0 ? 'var(--up)' : mk.sentiment < 0 ? 'var(--down)' : 'var(--accent)')
              : 'var(--accent)';
            return `<g class="chart-mk" data-mk-idx="${idx}" style="cursor:pointer">
              <line x1="${x}" x2="${x}" y1="${padT}" y2="${H-padB}" stroke="${color}" stroke-width="1.5" stroke-opacity="0.55" stroke-dasharray="3 2"/>
              <circle cx="${x}" cy="${padT+4}" r="3.5" fill="${color}"/>
            </g>`;
          }).join('');
        })()}
        <g data-hover style="display:none">
          <line data-hover-line x1="0" x2="0" y1="${padT}" y2="${H-padB}" stroke="${stroke}" stroke-opacity="0.5" stroke-dasharray="2 3"/>
          <circle data-hover-dot cx="0" cy="0" r="4" fill="${stroke}" stroke="var(--bg-1)" stroke-width="1.5"/>
        </g>
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
  const readoutDlbl = overlay.querySelector('[data-readout="dlbl"]');
  const readoutDelta = overlay.querySelector('[data-readout="delta"]');
  const hoverGroup = overlay.querySelector('[data-hover]');
  const hoverLine = overlay.querySelector('[data-hover-line]');
  const hoverDot = overlay.querySelector('[data-hover-dot]');
  function onMove(e) {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const x = cx * (W / rect.width);
    let best = 0, bestD = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const d = Math.abs(pts[i][0] - x);
      if (d < bestD) { bestD = d; best = i; }
    }
    const p = series[best];
    const [px, py] = pts[best];
    const d = latest.v - p.v;
    const dPct = p.v ? (d / p.v * 100) : 0;
    readoutDate.textContent = `${p.date} → ${latest.date}`;
    readoutVal.textContent = `${fmtCcy(p.v)} → ${fmtCcy(latest.v)}`;
    readoutDlbl.textContent = '이 날 → 최신';
    readoutDelta.classList.remove('up', 'down', 'flat');
    readoutDelta.classList.add(dirClass(d));
    readoutDelta.innerHTML = `${fmtCcySigned(d)} <span class="muted">(${fmtSigned(dPct, 2)}%)</span>`;
    hoverGroup.style.display = '';
    hoverLine.setAttribute('x1', px);
    hoverLine.setAttribute('x2', px);
    hoverDot.setAttribute('cx', px);
    hoverDot.setAttribute('cy', py);
  }
  function onLeave() {
    hoverGroup.style.display = 'none';
    readoutDate.textContent = `${defaultRef.date} → ${latest.date}`;
    readoutVal.textContent = `${fmtCcy(defaultRef.v)} → ${fmtCcy(latest.v)}`;
    readoutDlbl.textContent = '최신까지 변동 · vs latest';
    readoutDelta.classList.remove('up', 'down', 'flat');
    readoutDelta.classList.add(dirClass(initDelta));
    readoutDelta.innerHTML = `${fmtCcySigned(initDelta)} <span class="muted">(${fmtSigned(initDeltaPct, 2)}%)</span>`;
  }
  svg.addEventListener('mousemove', onMove);
  svg.addEventListener('mouseleave', onLeave);
  svg.addEventListener('touchstart', onMove, { passive: false });
  svg.addEventListener('touchmove', onMove, { passive: false });
  svg.addEventListener('touchend', onLeave);

  // Marker click → popover
  if (opts.markers && opts.markers.length) {
    overlay.querySelectorAll('.chart-mk').forEach(g => {
      g.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(g.dataset.mkIdx, 10);
        const mk = opts.markers[idx];
        if (!mk) return;
        const existing = overlay.querySelector('.chart-mk-pop');
        if (existing) existing.remove();
        const pop = document.createElement('div');
        pop.className = 'chart-mk-pop';
        const sentLbl = mk.kind === 'news'
          ? (mk.sentiment > 0 ? '↑ 상승' : mk.sentiment < 0 ? '↓ 하락' : '· 중립')
          : `${mk.type || 'event'} ${mk.magnitude != null ? '· ' + Math.round(mk.magnitude).toLocaleString() + 't' : ''}`;
        pop.innerHTML = `<div class="chart-mk-pop__head mono">${esc(mk.date)} · ${esc(sentLbl)}</div>
          <div class="chart-mk-pop__title">${esc(mk.title || '')}</div>
          ${mk.url ? `<a class="chart-mk-pop__link" href="${esc(mk.url)}" target="_blank" rel="noopener">원문 보기 →</a>` : ''}
          <button class="chart-mk-pop__close" aria-label="close">✕</button>`;
        overlay.querySelector('.chart-overlay__panel').appendChild(pop);
        pop.querySelector('.chart-mk-pop__close').addEventListener('click', () => pop.remove());
      });
    });
  }

  document.body.appendChild(overlay);
}

// --- Loaders ---
const yearCache = {}; // {metal}__{year} → entries[] (nested)

async function loadLatest(metal) {
  const url = `${DATA_BASE}/series/${metal}/latest.parquet`;
  const rows = await loadParquet(url);
  return rows.map(unflatten).sort((a, b) => (a.date < b.date ? 1 : -1));
}

async function loadYear(metal, year) {
  const key = `${metal}__${year}`;
  if (yearCache[key]) return yearCache[key];
  const url = `${DATA_BASE}/series/${metal}/${year}.parquet`;
  try {
    const rows = await loadParquet(url);
    const entries = rows.map(unflatten).sort((a, b) => (a.date < b.date ? 1 : -1));
    yearCache[key] = entries;
    return entries;
  } catch {
    return [];
  }
}

async function loadFullSeries(metal, manifest) {
  const years = (manifest?.metals?.[metal]?.years || []).slice().sort((a, b) => b - a);
  if (!years.length) return [];
  const chunks = await Promise.all(years.map(y => loadYear(metal, y)));
  const data = chunks.flat();
  data.sort((a, b) => (a.date < b.date ? 1 : -1));
  return data;
}

async function loadAll() {
  const manifest = await fetch(`${DATA_BASE}/manifest.json`).then(r => r.json());
  // Populate module-level metal metadata from manifest.
  METALS = manifest.metals;
  METAL_ORDER = Object.keys(METALS);
  MINOR_METALS = manifest.minor_metals || {};
  MINOR_ORDER = Object.keys(MINOR_METALS);

  const latestArr = await Promise.all(METAL_ORDER.map(m =>
    loadLatest(m).catch(err => { console.warn(`load ${m}:`, err); return []; })
  ));
  const metals = {};
  METAL_ORDER.forEach((m, i) => {
    metals[m] = {
      metal: m,
      symbol: METALS[m].symbol,
      unit: METALS[m].unit,
      data: latestArr[i],
    };
  });

  const minors = {};
  if (MINOR_ORDER.length) {
    const minorArr = await Promise.all(MINOR_ORDER.map(m =>
      loadMinorLatest(m).catch(err => { console.warn(`minor load ${m}:`, err); return []; })
    ));
    MINOR_ORDER.forEach((m, i) => {
      minors[m] = {
        metal: m,
        symbol: MINOR_METALS[m].symbol,
        unit: MINOR_METALS[m].unit,
        data: minorArr[i],
      };
    });
  }
  return { manifest, metals, minors };
}

// --- Init ---
async function init() {
  const tweaks = loadTweaks();
  const [{ manifest, metals, minors }, news, events] = await Promise.all([
    loadAll(),
    loadNews().catch(err => { console.warn('news load:', err); return []; }),
    loadEvents().catch(err => { console.warn('events load:', err); return []; }),
  ]);

  const root = document.getElementById('root');
  const latest0 = metals.copper?.data?.[0];
  const latestDate = manifest?.last_updated || latest0?.date;
  const krw = latest0?.krw || {};
  const seenAt = lastSeenAt();
  let unseen = unseenCount(news, seenAt);
  let currentMetal = METAL_ORDER[0] || null;

  root.outerHTML = `<div class="app" id="root" data-density="compact" data-lang="ko" data-accent="muted">
    ${renderHeader(latestDate, krw.rate, krw.source, unseen)}
    <nav class="app__nav nav--pricepct">${renderNav(metals, minors)}</nav>
    <div class="app__scroller">
      ${METAL_ORDER.map(m => renderMetalSection(m, metals[m])).join('')}
      ${MINOR_ORDER.map(m => renderMinorMetalSection(m, minors[m], MINOR_METALS[m])).join('')}
      <footer class="app__footer">
        <div class="mono">END · 데이터 끝</div>
        <div class="lbl">Source: NH선물 · LME · SHFE · BOK · scrapmonster (minor) · GDELT/RSS (news) · 마감 기준</div>
        <div class="lbl">Format: Apache Parquet · ${manifest?.total_days || '—'}일 · ${manifest?.years?.[0] || '—'}~${manifest?.years?.[manifest.years.length - 1] || '—'}</div>
      </footer>
    </div>
    ${tweaks.showNews ? renderDrawer(news, currentMetal, tweaks, seenAt) : ''}
    ${renderTweaksPanel(tweaks)}
  </div>`;

  const app = document.getElementById('root');
  const scroller = app.querySelector('.app__scroller');
  const nav = app.querySelector('.app__nav');

  bindLongPress(app);

  // Drawer rerender helper (for filter changes when active metal changes)
  const rerenderDrawer = () => {
    if (!tweaks.showNews) return;
    const oldDrawer = app.querySelector('#news-drawer');
    const oldBackdrop = app.querySelector('#news-drawer-backdrop');
    const wasOpen = oldDrawer?.classList.contains('is-open');
    oldDrawer?.remove();
    oldBackdrop?.remove();
    app.insertAdjacentHTML('beforeend', renderDrawer(news, currentMetal, tweaks, lastSeenAt()));
    bindDrawer(app, () => { markSeen(); refreshBell(); });
    if (wasOpen) {
      app.querySelector('#news-drawer')?.classList.add('is-open');
      app.querySelector('#news-drawer-backdrop')?.classList.add('is-open');
    }
  };

  const refreshBell = () => {
    const cnt = unseenCount(news, lastSeenAt());
    const head = app.querySelector('.app__head-r');
    const old = head.querySelector('#news-bell');
    old?.remove();
    head.insertAdjacentHTML('afterbegin', renderBell(cnt));
    head.querySelector('#news-bell').addEventListener('click', () => {
      const dr = app.querySelector('#news-drawer');
      if (!dr) return;
      const isOpen = dr.classList.contains('is-open');
      if (isOpen) {
        dr.classList.remove('is-open');
        app.querySelector('#news-drawer-backdrop')?.classList.remove('is-open');
      } else {
        dr.classList.add('is-open');
        app.querySelector('#news-drawer-backdrop')?.classList.add('is-open');
        markSeen();
        setTimeout(refreshBell, 300);
      }
    });
  };

  // Bind drawer + tweaks
  if (tweaks.showNews) bindDrawer(app, () => { markSeen(); refreshBell(); });
  bindTweaks(app, tweaks, (newTweaks) => {
    if (newTweaks.showNews && !app.querySelector('#news-drawer')) {
      app.insertAdjacentHTML('beforeend', renderDrawer(news, currentMetal, newTweaks, lastSeenAt()));
      bindDrawer(app, () => { markSeen(); refreshBell(); });
    } else if (!newTweaks.showNews && app.querySelector('#news-drawer')) {
      app.querySelector('#news-drawer')?.remove();
      app.querySelector('#news-drawer__backdrop')?.remove();
    } else {
      rerenderDrawer();
    }
  });

  nav.querySelectorAll('.nav-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = btn.dataset.metal;
      const sec = scroller.querySelector(`.metal-section[data-metal="${m}"]`);
      sec?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  const sections = scroller.querySelectorAll('.metal-section');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('is-entering');
        if (e.intersectionRatio > 0.6) {
          const m = e.target.dataset.metal;
          if (m && m !== currentMetal) {
            currentMetal = m;
            nav.querySelectorAll('.nav-pill').forEach(b => b.classList.toggle('is-active', b.dataset.metal === m));
            const activePill = nav.querySelector(`.nav-pill[data-metal="${m}"]`);
            activePill?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
            rerenderDrawer();  // 활성 metal 바뀌면 drawer 필터 업데이트
          }
        }
      }
    });
  }, { root: scroller, threshold: [0, 0.6, 1] });
  sections.forEach(s => obs.observe(s));

  // Hero expand → chart overlay with markers (LME 6종)
  app.querySelectorAll('[data-expand]').forEach(el => {
    el.addEventListener('click', async () => {
      const m = el.dataset.expand;
      const latestData = metals[m]?.data;
      if (!latestData?.length) return;
      const quickSeries = priceSeries(latestData, 'close');
      const title = `${METALS[m].name_ko} · ${METALS[m].symbol} 3M`;
      const dates = quickSeries.map(p => p.date);
      const markers = chartMarkersFor(m, dates, news, events, tweaks);
      openChart(title, quickSeries, { markers });
      const years = manifest?.metals?.[m]?.years || [];
      if (years.length > 1) {
        const full = await loadFullSeries(m, manifest);
        if (full.length > latestData.length) {
          const fullSeries = priceSeries(full, 'close', full.length);
          const fullDates = fullSeries.map(p => p.date);
          const fullMarkers = chartMarkersFor(m, fullDates, news, events, tweaks);
          document.querySelector('.chart-overlay')?.remove();
          openChart(title + ' · 전체', fullSeries, { markers: fullMarkers });
        }
      }
    });
  });

  // Minor metal expand (Sb)
  app.querySelectorAll('[data-expand-minor]').forEach(el => {
    el.addEventListener('click', () => {
      const m = el.dataset.expandMinor;
      const data = minors[m]?.data;
      if (!data?.length) return;
      const series = minorPriceSeries(data, 'exw_china', data.length);
      const meta = MINOR_METALS[m];
      const title = `${meta.name_ko} · ${meta.symbol} EXW China`;
      openChart(title, series);
    });
  });

  // 5분 주기 뉴스 polling — 새 뉴스 들어오면 bell 갱신
  setInterval(async () => {
    try {
      const fresh = await loadNews();
      if (fresh.length !== news.length) {
        news.length = 0;
        news.push(...fresh);
        refreshBell();
        rerenderDrawer();
      }
    } catch (e) { /* skip silently */ }
  }, newsConstants.POLL_MS);
}

init().catch(err => {
  console.error(err);
  document.getElementById('root').innerHTML = `<pre style="color:#c87a6a;padding:20px">${esc(err.message || err)}</pre>`;
});
