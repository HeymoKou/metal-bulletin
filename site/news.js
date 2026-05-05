// News integration — drawer + chart markers + tweaks
// Reads data/news/{year}.parquet, data/events/{year}.parquet via hyparquet.
import { parquetReadObjects } from 'https://cdn.jsdelivr.net/npm/hyparquet@1.25.6/+esm';
import { compressors } from 'https://cdn.jsdelivr.net/npm/hyparquet-compressors@1.1.1/+esm';
import { DATA_BASE } from './config.js';

const TWEAKS_KEY = 'desk.tweaks';
const SEEN_KEY = 'desk.lastSeenAt';
const POLL_MS = 5 * 60 * 1000; // 5분 — news.yml 12h 주기 대비 충분

const DEFAULT_TWEAKS = {
  showNews: true,
  confThreshold: 0.5,   // 0..1, 낮은 confidence 흐림
  bigMoveTons: 5000,    // 재고 |Δ| ≥ 임계값 → 차트 marker
};

export function loadTweaks() {
  try {
    const raw = JSON.parse(localStorage.getItem(TWEAKS_KEY) || '{}');
    return { ...DEFAULT_TWEAKS, ...raw };
  } catch { return { ...DEFAULT_TWEAKS }; }
}
export function saveTweaks(t) {
  try { localStorage.setItem(TWEAKS_KEY, JSON.stringify(t)); } catch {}
}
export function lastSeenAt() {
  return localStorage.getItem(SEEN_KEY) || '';
}
export function markSeen() {
  try { localStorage.setItem(SEEN_KEY, new Date().toISOString()); } catch {}
}

// hyparquet date32 → ISO string (epoch days since 1970-01-01)
function dateToISO(v) {
  if (v == null) return null;
  if (typeof v === 'string') return v;
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (typeof v === 'number') {
    const ms = v * 86400000;
    return new Date(ms).toISOString().slice(0, 10);
  }
  if (typeof v === 'bigint') {
    const ms = Number(v) * 86400000;
    return new Date(ms).toISOString().slice(0, 10);
  }
  return String(v);
}

async function loadParquet(url) {
  const resp = await fetch(url, { cache: 'no-cache' });
  if (!resp.ok) throw new Error(`fetch ${url}: ${resp.status}`);
  const buf = await resp.arrayBuffer();
  return await parquetReadObjects({ file: buf, compressors });
}

function thisYear() { return new Date().getFullYear(); }

export async function loadNews() {
  const years = [thisYear(), thisYear() - 1];
  const out = [];
  for (const y of years) {
    try {
      const rows = await loadParquet(`${DATA_BASE}/news/${y}.parquet`);
      for (const r of rows) {
        out.push({
          date: dateToISO(r.date),
          source: r.source,
          url: r.url,
          urlHash: r.url_hash,
          title: r.title_ko || r.title,
          titleEn: r.title,
          summary: r.summary_ko,
          metals: Array.isArray(r.metals) ? r.metals : [],
          sentiment: r.sentiment ?? 0,
          eventType: r.event_type || 'other',
          confidence: r.confidence ?? 0,
          lang: r.lang,
        });
      }
    } catch (e) {
      // year file missing — skip silently
    }
  }
  out.sort((a, b) => a.date < b.date ? 1 : -1);
  return out;
}

export async function loadEvents() {
  const years = [thisYear(), thisYear() - 1];
  const out = [];
  for (const y of years) {
    try {
      const rows = await loadParquet(`${DATA_BASE}/events/${y}.parquet`);
      for (const r of rows) {
        out.push({
          date: dateToISO(r.date),
          type: r.type,
          metal: r.metal,
          magnitude: r.magnitude,
          title: r.title,
          url: r.url,
          source: r.source,
        });
      }
    } catch {}
  }
  return out;
}

// Filter: 현재 metal + macro 함께 (macro = 메탈 미지정 or 다중 메탈)
export function filterForMetal(news, metal, tweaks) {
  return news.filter(n => {
    if (n.confidence < (tweaks?.confThreshold ?? 0)) return false;
    if (!metal) return true;
    if (!n.metals || n.metals.length === 0) return true;          // macro
    if (n.metals.length >= 4) return true;                         // 거시
    return n.metals.includes(metal);
  });
}

export function unseenCount(news, lastSeen) {
  if (!lastSeen) return news.length;
  return news.filter(n => n.date > lastSeen.slice(0, 10)).length;
}

// Vertical line markers: combine inventory big-moves (from price series adjacent inventory)
// with news events for the metal in the visible date range.
export function chartMarkersFor(metal, dates, news, events, tweaks) {
  const dateSet = new Set(dates);
  const inRange = (d) => dateSet.has(d);
  const out = [];

  // News markers
  for (const n of news) {
    if (!inRange(n.date)) continue;
    if (n.confidence < (tweaks?.confThreshold ?? 0)) continue;
    const isMacro = !n.metals || n.metals.length === 0 || n.metals.length >= 4;
    if (!isMacro && !n.metals.includes(metal)) continue;
    out.push({
      date: n.date,
      kind: 'news',
      sentiment: n.sentiment,
      title: n.title,
      url: n.url,
      eventType: n.eventType,
      confidence: n.confidence,
    });
  }

  // Event markers (LME stock big moves filtered by tonnage)
  for (const ev of events) {
    if (ev.metal !== metal) continue;
    if (!inRange(ev.date)) continue;
    if (ev.type === 'inventory_change' && Math.abs(ev.magnitude || 0) < (tweaks?.bigMoveTons ?? 0)) continue;
    out.push({
      date: ev.date,
      kind: 'event',
      type: ev.type,
      magnitude: ev.magnitude,
      title: ev.title,
      url: ev.url,
    });
  }

  return out;
}

// --- Renderers ---
const SENT_COLOR = { '-1': 'down', '0': 'mute', '1': 'up' };
const SENT_LABEL = { '-1': '하락', '0': '중립', '1': '상승' };
const EVENT_ICON = {
  supply: '⛏', demand: '◧', policy: '⚖', strike: '✊',
  outage: '✕', inventory: '▦', macro: '◐', other: '·',
};

function escAttr(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function timeAgoKo(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00Z');
  const diff = (Date.now() - d.getTime()) / 86400000;
  if (diff < 1) return '오늘';
  if (diff < 2) return '어제';
  if (diff < 7) return `${Math.floor(diff)}일 전`;
  return iso;
}

export function renderBell(unseen) {
  const has = unseen > 0;
  return `<button class="news-bell ${has ? 'is-new' : ''}" id="news-bell" aria-label="뉴스" title="뉴스">
    <span class="news-bell__icon" aria-hidden="true">📰</span>
    ${unseen > 0 ? `<span class="news-bell__badge mono">${unseen > 99 ? '99+' : unseen}</span>` : ''}
    ${has ? '<span class="news-bell__dot"></span>' : ''}
  </button>`;
}

export function renderTweaksGear() {
  return `<button class="tweaks-gear" id="tweaks-gear" aria-label="설정" title="설정">⚙</button>`;
}

export function renderDrawer(news, currentMetal, tweaks, lastSeen) {
  const filtered = filterForMetal(news, currentMetal, tweaks);
  const items = filtered.map(n => renderNewsRow(n, lastSeen)).join('');
  const metalLabel = currentMetal ? currentMetal.toUpperCase() : '전체';
  return `<aside class="news-drawer" id="news-drawer" aria-hidden="true">
    <div class="news-drawer__handle" aria-hidden="true"></div>
    <header class="news-drawer__head">
      <div>
        <div class="news-drawer__title">뉴스 · News</div>
        <div class="news-drawer__sub mono">${metalLabel} + 거시 · ${filtered.length}건</div>
      </div>
      <button class="news-drawer__close" id="news-drawer-close" aria-label="닫기">✕</button>
    </header>
    <div class="news-drawer__list">
      ${items || '<div class="news-drawer__empty">필터 결과 없음</div>'}
    </div>
  </aside>
  <div class="news-drawer__backdrop" id="news-drawer-backdrop"></div>`;
}

function renderNewsRow(n, lastSeen) {
  const isNew = lastSeen ? n.date > lastSeen.slice(0, 10) : true;
  const sentClass = SENT_COLOR[String(n.sentiment)] || 'mute';
  const evIcon = EVENT_ICON[n.eventType] || '·';
  const dim = n.confidence < 0.6 ? 'is-dim' : '';
  const metals = (n.metals || []).slice(0, 3).map(m =>
    `<span class="news-row__metal">${escAttr(m)}</span>`
  ).join('');
  return `<a class="news-row ${isNew ? 'is-new' : ''} ${dim}" href="${escAttr(n.url)}" target="_blank" rel="noopener">
    <div class="news-row__head">
      <span class="news-row__icon" title="${escAttr(n.eventType)}">${evIcon}</span>
      <span class="news-row__sent news-row__sent--${sentClass}">${SENT_LABEL[String(n.sentiment)] || ''}</span>
      ${metals}
      <span class="news-row__time mono">${timeAgoKo(n.date)}</span>
    </div>
    <div class="news-row__title">${escAttr(n.title)}</div>
    ${n.summary ? `<div class="news-row__summary">${escAttr(n.summary)}</div>` : ''}
    <div class="news-row__meta mono">
      <span>${escAttr(n.source)}</span>
      <span class="news-row__conf">conf ${(n.confidence * 100).toFixed(0)}%</span>
    </div>
  </a>`;
}

export function renderTweaksPanel(tweaks) {
  return `<div class="tweaks-panel" id="tweaks-panel" aria-hidden="true">
    <header class="tweaks-panel__head">
      <span>설정 · Tweaks</span>
      <button class="tweaks-panel__close" id="tweaks-close" aria-label="닫기">✕</button>
    </header>
    <div class="tweaks-panel__body">
      <label class="tweaks-row">
        <span>뉴스 패널 표시</span>
        <input type="checkbox" id="tw-show-news" ${tweaks.showNews ? 'checked' : ''}>
      </label>
      <label class="tweaks-row tweaks-row--col">
        <div class="tweaks-row__lbl"><span>신뢰도 임계값</span><span class="mono" id="tw-conf-v">${(tweaks.confThreshold*100).toFixed(0)}%</span></div>
        <input type="range" id="tw-conf" min="0" max="1" step="0.05" value="${tweaks.confThreshold}">
      </label>
      <label class="tweaks-row tweaks-row--col">
        <div class="tweaks-row__lbl"><span>큰 변동 임계값(t)</span><span class="mono" id="tw-bm-v">${tweaks.bigMoveTons.toLocaleString()}t</span></div>
        <input type="range" id="tw-bm" min="500" max="20000" step="500" value="${tweaks.bigMoveTons}">
      </label>
    </div>
  </div>`;
}

// Open drawer (mobile bottom sheet swipe-down close support)
export function bindDrawer(root, onMarkSeen) {
  const drawer = root.querySelector('#news-drawer');
  const backdrop = root.querySelector('#news-drawer-backdrop');
  const closeBtn = root.querySelector('#news-drawer-close');
  const bell = root.querySelector('#news-bell');

  const open = () => {
    drawer.classList.add('is-open');
    backdrop.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    onMarkSeen?.();
  };
  const close = () => {
    drawer.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
  };

  bell?.addEventListener('click', () => drawer.classList.contains('is-open') ? close() : open());
  closeBtn?.addEventListener('click', close);
  backdrop?.addEventListener('click', close);

  // Mobile swipe-down on handle to close
  let startY = null;
  const handle = drawer.querySelector('.news-drawer__handle');
  const onStart = (e) => { startY = (e.touches ? e.touches[0].clientY : e.clientY); };
  const onMove = (e) => {
    if (startY == null) return;
    const y = (e.touches ? e.touches[0].clientY : e.clientY);
    const dy = y - startY;
    if (dy > 80) { close(); startY = null; }
  };
  const onEnd = () => { startY = null; };
  handle?.addEventListener('touchstart', onStart, { passive: true });
  handle?.addEventListener('touchmove', onMove, { passive: true });
  handle?.addEventListener('touchend', onEnd);

  return { open, close };
}

export function bindTweaks(root, tweaks, onChange) {
  const panel = root.querySelector('#tweaks-panel');
  const gear = root.querySelector('#tweaks-gear');
  const closeBtn = root.querySelector('#tweaks-close');

  const open = () => { panel.classList.add('is-open'); panel.setAttribute('aria-hidden', 'false'); };
  const close = () => { panel.classList.remove('is-open'); panel.setAttribute('aria-hidden', 'true'); };
  gear?.addEventListener('click', () => panel.classList.contains('is-open') ? close() : open());
  closeBtn?.addEventListener('click', close);

  const showNews = root.querySelector('#tw-show-news');
  const conf = root.querySelector('#tw-conf');
  const confV = root.querySelector('#tw-conf-v');
  const bm = root.querySelector('#tw-bm');
  const bmV = root.querySelector('#tw-bm-v');

  showNews?.addEventListener('change', () => { tweaks.showNews = showNews.checked; saveTweaks(tweaks); onChange?.(tweaks); });
  conf?.addEventListener('input', () => {
    tweaks.confThreshold = parseFloat(conf.value);
    confV.textContent = (tweaks.confThreshold * 100).toFixed(0) + '%';
    saveTweaks(tweaks); onChange?.(tweaks);
  });
  bm?.addEventListener('input', () => {
    tweaks.bigMoveTons = parseInt(bm.value, 10);
    bmV.textContent = tweaks.bigMoveTons.toLocaleString() + 't';
    saveTweaks(tweaks); onChange?.(tweaks);
  });
}

export const newsConstants = { POLL_MS };
