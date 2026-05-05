// News + LME stock event data + helpers for filtering, marking charts, etc.
// Schema mirrors data/news/2026.parquet (date, fetched_at, source, url, title,
// summary_ko, metals[], sentiment, event_type, confidence, lang).
(function(){

const NEWS = [
  // ---------- 2026-05-05 (latest) ----------
  { id:'n01', date:'2026-05-05', fetched_at:'2026-05-05T09:12:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'China tightens grip on rare earths with strict enforcement',
    summary_ko:'중국, 희토류 생산 할당량 위반에 강력 단속 — 공급 위축 우려',
    metals:['copper'], sentiment:+1, event_type:'policy', confidence:0.88 },

  { id:'n02', date:'2026-05-05', fetched_at:'2026-05-05T08:40:00Z',
    source:'snmnews', lang:'ko',
    url:'#', title:'고려아연-록히드마틴, 게르마늄 공급망 협력 MOU 체결',
    summary_ko:'고려아연-록히드마틴, 게르마늄 공급망 협력 — 아연 부산물 가치↑',
    metals:['zinc'], sentiment:+1, event_type:'supply', confidence:0.92 },

  { id:'n03', date:'2026-05-05', fetched_at:'2026-05-05T07:55:00Z',
    source:'gdelt', lang:'zh→en',
    url:'#', title:'Indonesia nickel export halt extended to Q3',
    summary_ko:'인도네시아, 니켈 정광 수출 중단 3분기까지 연장',
    metals:['nickel'], sentiment:+1, event_type:'supply', confidence:0.91 },

  { id:'n04', date:'2026-05-05', fetched_at:'2026-05-05T07:21:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Alphamin posts record profit, boosts dividend on tin rally',
    summary_ko:'Alphamin, 주석 가격 호조로 사상 최대 이익·배당 확대',
    metals:['tin'], sentiment:-1, event_type:'supply', confidence:0.85 },

  { id:'n05', date:'2026-05-05', fetched_at:'2026-05-05T06:48:00Z',
    source:'mt.co.kr', lang:'ko',
    url:'#', title:'Fed 5월 FOMC 금리 동결 시사 — 달러지수 반락',
    summary_ko:'Fed 금리 동결 시사, 달러 약세 — 비철 전반 우호적',
    metals:['copper','aluminum','zinc','nickel','lead','tin'],
    sentiment:+1, event_type:'macro', confidence:0.74 },

  { id:'n06', date:'2026-05-05', fetched_at:'2026-05-05T06:03:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'Glencore aluminum smelter restart eyed in Q3',
    summary_ko:'Glencore, 3분기 알루미늄 제련소 재가동 검토 중',
    metals:['aluminum'], sentiment:-1, event_type:'supply', confidence:0.58 },

  // ---------- 2026-05-04 ----------
  { id:'n07', date:'2026-05-04', fetched_at:'2026-05-04T22:14:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'BHP cuts copper guidance citing Escondida grade decline',
    summary_ko:'BHP, Escondida 광석품위 하락으로 전기동 가이던스 하향',
    metals:['copper'], sentiment:+1, event_type:'supply', confidence:0.94 },

  { id:'n08', date:'2026-05-04', fetched_at:'2026-05-04T19:55:00Z',
    source:'snmnews', lang:'ko',
    url:'#', title:'국내 자동차 OEM, 알루미늄 단조부품 수요 8% 감소',
    summary_ko:'국내 OEM 알루미늄 단조부품 수요 8%↓ — EV 판매 둔화',
    metals:['aluminum'], sentiment:-1, event_type:'demand', confidence:0.81 },

  { id:'n09', date:'2026-05-04', fetched_at:'2026-05-04T17:32:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'EU CBAM phase II kicks in for refined zinc imports',
    summary_ko:'EU CBAM 2단계, 정제아연 수입 적용 개시',
    metals:['zinc','lead'], sentiment:0, event_type:'policy', confidence:0.69 },

  { id:'n10', date:'2026-05-04', fetched_at:'2026-05-04T15:08:00Z',
    source:'mt.co.kr', lang:'ko',
    url:'#', title:'중국 4월 PMI 49.2, 두 달 연속 위축 국면',
    summary_ko:'중국 4월 PMI 49.2 — 비철 수요 둔화 시그널',
    metals:['copper','aluminum','zinc'],
    sentiment:-1, event_type:'macro', confidence:0.83 },

  { id:'n11', date:'2026-05-04', fetched_at:'2026-05-04T13:45:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Vedanta restarts Tuticorin smelter pending court ruling',
    summary_ko:'Vedanta, 인도 Tuticorin 제련소 재가동 — 법원 판결 대기',
    metals:['copper'], sentiment:-1, event_type:'supply', confidence:0.55 },

  { id:'n12', date:'2026-05-04', fetched_at:'2026-05-04T11:20:00Z',
    source:'gdelt', lang:'es→en',
    url:'#', title:'Peru community blockades resume at Las Bambas access road',
    summary_ko:'페루 Las Bambas 진입로 봉쇄 재개 — 출하 차질 우려',
    metals:['copper'], sentiment:+1, event_type:'supply', confidence:0.78 },

  // ---------- 2026-05-03 ----------
  { id:'n13', date:'2026-05-03', fetched_at:'2026-05-03T20:11:00Z',
    source:'snmnews', lang:'ko',
    url:'#', title:'한국 4월 비철금속 수출 전년比 12.4% 증가',
    summary_ko:'한국 4월 비철금속 수출 +12.4%y/y — 동·아연 견인',
    metals:['copper','zinc'], sentiment:0, event_type:'demand', confidence:0.72 },

  { id:'n14', date:'2026-05-03', fetched_at:'2026-05-03T16:38:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Tin supply tightens as Myanmar Wa State extends mining freeze',
    summary_ko:'미얀마 와주, 채광 동결 연장 — 주석 공급 추가 위축',
    metals:['tin'], sentiment:+1, event_type:'supply', confidence:0.89 },

  { id:'n15', date:'2026-05-03', fetched_at:'2026-05-03T14:08:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'Trafigura warns of physical lead tightness into Q3',
    summary_ko:'Trafigura, 3분기까지 납 현물 타이트 — 배터리 수요 견조',
    metals:['lead'], sentiment:+1, event_type:'demand', confidence:0.76 },

  { id:'n16', date:'2026-05-03', fetched_at:'2026-05-03T10:42:00Z',
    source:'mt.co.kr', lang:'ko',
    url:'#', title:'美 4월 ISM 제조업 PMI 48.7 — 4개월 연속 위축',
    summary_ko:'美 4월 ISM 제조업 48.7 — 산업금속 수요 둔화 시그널',
    metals:['copper','aluminum','zinc','nickel'],
    sentiment:-1, event_type:'macro', confidence:0.79 },

  // ---------- 2026-05-02 ----------
  { id:'n17', date:'2026-05-02', fetched_at:'2026-05-02T22:50:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Norilsk Nickel signals 2026 production at lower end of guidance',
    summary_ko:'Norilsk Nickel, 2026년 생산 가이던스 하단 시사',
    metals:['nickel','copper'], sentiment:+1, event_type:'supply', confidence:0.86 },

  { id:'n18', date:'2026-05-02', fetched_at:'2026-05-02T18:22:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'Korea Zinc lifts Q2 LME premium offers by $15/t',
    summary_ko:'고려아연, 2분기 아시아 프리미엄 +$15/t 인상',
    metals:['zinc'], sentiment:+1, event_type:'demand', confidence:0.71 },

  { id:'n19', date:'2026-05-02', fetched_at:'2026-05-02T13:15:00Z',
    source:'snmnews', lang:'ko',
    url:'#', title:'주석 4만 9천달러 돌파…미얀마發 공급 우려 지속',
    summary_ko:'주석 $49,000 돌파 — 미얀마 공급 우려 + 반도체 수요',
    metals:['tin'], sentiment:+1, event_type:'demand', confidence:0.84 },

  // ---------- 2026-04-30 (older) ----------
  { id:'n20', date:'2026-04-30', fetched_at:'2026-04-30T20:00:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Codelco Q1 production -7%, weakest in 20 years',
    summary_ko:'Codelco 1분기 생산 -7%y/y — 20년래 최저',
    metals:['copper'], sentiment:+1, event_type:'supply', confidence:0.93 },

  { id:'n21', date:'2026-04-29', fetched_at:'2026-04-29T17:30:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'Yunnan power restrictions ease, aluminum smelters resume',
    summary_ko:'운남성 전력제한 완화 — 알루미늄 제련 재개',
    metals:['aluminum'], sentiment:-1, event_type:'supply', confidence:0.77 },

  { id:'n22', date:'2026-04-25', fetched_at:'2026-04-25T11:00:00Z',
    source:'mt.co.kr', lang:'ko',
    url:'#', title:'美 1분기 GDP 1.6% 예상 하회, 달러 약세',
    summary_ko:'美 1Q GDP +1.6%, 예상 하회 — 달러 약세',
    metals:['copper','aluminum','zinc','nickel','lead','tin'],
    sentiment:+1, event_type:'macro', confidence:0.81 },

  { id:'n23', date:'2026-04-22', fetched_at:'2026-04-22T09:15:00Z',
    source:'mining.com', lang:'en',
    url:'#', title:'Chile copper royalty hike clears senate committee',
    summary_ko:'칠레 구리 로열티 인상안, 상원 위원회 통과',
    metals:['copper'], sentiment:+1, event_type:'policy', confidence:0.82 },

  { id:'n24', date:'2026-04-18', fetched_at:'2026-04-18T14:45:00Z',
    source:'gdelt', lang:'en',
    url:'#', title:'Glencore Mt Isa zinc shutdown confirmed for July',
    summary_ko:'Glencore Mt Isa 아연제련 7월 영구폐쇄 확정',
    metals:['zinc','lead'], sentiment:+1, event_type:'supply', confidence:0.95 },
];

// LME warehouse stock events: one per metal per day. Big = abs(magnitude)
// over the user-tunable threshold.
const STOCK_EVENTS = [
  { date:'2026-05-05', type:'lme_stock', metal:'copper',   magnitude:-1050, title:'LME copper stock 398,675 t (Δ-1,050)',  source:'lme' },
  { date:'2026-05-05', type:'lme_stock', metal:'aluminum', magnitude:-3275, title:'LME aluminum stock 364,725 t (Δ-3,275)', source:'lme' },
  { date:'2026-05-05', type:'lme_stock', metal:'zinc',     magnitude:+150,  title:'LME zinc stock 96,250 t (Δ+150)',        source:'lme' },
  { date:'2026-05-05', type:'lme_stock', metal:'nickel',   magnitude:+500,  title:'LME nickel stock 276,896 t (Δ+500)',     source:'lme' },
  { date:'2026-05-05', type:'lme_stock', metal:'lead',     magnitude:-225,  title:'LME lead stock 268,500 t (Δ-225)',       source:'lme' },
  { date:'2026-05-05', type:'lme_stock', metal:'tin',      magnitude:-65,   title:'LME tin stock 8,475 t (Δ-65)',           source:'lme' },

  { date:'2026-05-04', type:'lme_stock', metal:'copper',   magnitude:+5800, title:'LME copper stock 399,725 t (Δ+5,800)',  source:'lme' },
  { date:'2026-05-04', type:'lme_stock', metal:'aluminum', magnitude:-1200, title:'LME aluminum stock 368,000 t (Δ-1,200)', source:'lme' },
  { date:'2026-05-04', type:'lme_stock', metal:'zinc',     magnitude:-7250, title:'LME zinc stock 96,100 t (Δ-7,250)',      source:'lme' },
  { date:'2026-05-04', type:'lme_stock', metal:'nickel',   magnitude:-380,  title:'LME nickel stock 276,396 t (Δ-380)',     source:'lme' },
  { date:'2026-05-04', type:'lme_stock', metal:'lead',     magnitude:+820,  title:'LME lead stock 268,725 t (Δ+820)',       source:'lme' },
  { date:'2026-05-04', type:'lme_stock', metal:'tin',      magnitude:+15,   title:'LME tin stock 8,540 t (Δ+15)',           source:'lme' },

  { date:'2026-05-03', type:'lme_stock', metal:'copper',   magnitude:+12400, title:'LME copper stock 393,925 t (Δ+12,400)', source:'lme' },
  { date:'2026-05-03', type:'lme_stock', metal:'aluminum', magnitude:-9050,  title:'LME aluminum stock 369,200 t (Δ-9,050)', source:'lme' },
  { date:'2026-05-03', type:'lme_stock', metal:'zinc',     magnitude:+6200,  title:'LME zinc stock 103,350 t (Δ+6,200)',     source:'lme' },
  { date:'2026-05-03', type:'lme_stock', metal:'nickel',   magnitude:-180,   title:'LME nickel stock 276,776 t (Δ-180)',     source:'lme' },
  { date:'2026-05-03', type:'lme_stock', metal:'lead',     magnitude:-340,   title:'LME lead stock 267,905 t (Δ-340)',       source:'lme' },
  { date:'2026-05-03', type:'lme_stock', metal:'tin',      magnitude:-20,    title:'LME tin stock 8,525 t (Δ-20)',           source:'lme' },

  { date:'2026-05-02', type:'lme_stock', metal:'copper',   magnitude:-2100, title:'LME copper stock 381,525 t (Δ-2,100)', source:'lme' },
  { date:'2026-05-02', type:'lme_stock', metal:'aluminum', magnitude:+8400, title:'LME aluminum stock 378,250 t (Δ+8,400)', source:'lme' },
  { date:'2026-05-02', type:'lme_stock', metal:'zinc',     magnitude:-1100, title:'LME zinc stock 97,150 t (Δ-1,100)', source:'lme' },
];

const SOURCE_LABEL = {
  'mining.com':'MINING.COM',
  'snmnews':'철강금속신문',
  'mt.co.kr':'머니투데이',
  'gdelt':'GDELT',
  'lme':'LME',
};

const EVENT_TYPE = {
  supply:  { ko:'공급',  en:'SUPPLY', glyph:'⛏' },
  demand:  { ko:'수요',  en:'DEMAND', glyph:'◆' },
  policy:  { ko:'정책',  en:'POLICY', glyph:'§' },
  macro:   { ko:'거시',  en:'MACRO',  glyph:'∿' },
  stock:   { ko:'재고',  en:'STOCK',  glyph:'▢' },
  other:   { ko:'기타',  en:'OTHER',  glyph:'·' },
};

const METAL_SYM = {
  copper:'Cu', aluminum:'Al', zinc:'Zn', nickel:'Ni', lead:'Pb', tin:'Sn',
};
const METAL_KO = {
  copper:'전기동', aluminum:'알루미늄', zinc:'아연',
  nickel:'니켈', lead:'납', tin:'주석',
};

// "Now" anchor — used by relative-time formatting and "is new" checks.
const DATA_NOW = new Date();

function timeAgo(iso, now){
  const t = new Date(iso).getTime();
  const ref = (now ? now.getTime() : DATA_NOW.getTime());
  const m = Math.round((ref - t)/60000);
  if (m < 1) return '방금';
  if (m < 60) return m + '분 전';
  const h = Math.round(m/60);
  if (h < 24) return h + '시간 전';
  const d = Math.round(h/24);
  return d + '일 전';
}

function sentimentDir(s){
  if (s > 0) return 'up';
  if (s < 0) return 'down';
  return 'flat';
}

// Filter helpers used by the drawer + chart markers.

// Returns news relevant to a given metal: items that name the metal directly,
// PLUS macro items (unless excludeMacro). Sorted newest-first.
function newsForMetal(metal, opts){
  opts = opts || {};
  const excludeMacro = !!opts.excludeMacro;
  const minConf = opts.minConf == null ? 0 : opts.minConf;
  return NEWS
    .filter(n => n.confidence >= minConf)
    .filter(n => {
      const isMacro = n.event_type === 'macro';
      if (isMacro) return !excludeMacro;
      return n.metals.includes(metal);
    })
    .sort((a,b) => (b.fetched_at||b.date).localeCompare(a.fetched_at||a.date));
}

// Markers to overlay on the 30-day chart of a single metal: news with
// confidence >= minConf AND stock events with |Δ| >= bigMoveTons. Returns
// {date, kind, items} grouped by date.
function chartMarkersFor(metal, dateRange, opts){
  opts = opts || {};
  const minConf = opts.minConf == null ? 0.6 : opts.minConf;
  const bigMoveTons = opts.bigMoveTons == null ? 5000 : opts.bigMoveTons;
  const dateSet = new Set(dateRange); // valid chart dates

  const newsItems = NEWS.filter(n =>
    dateSet.has(n.date) &&
    n.confidence >= minConf &&
    (n.metals.includes(metal) || (opts.includeMacro !== false && n.event_type === 'macro'))
  );

  const stockItems = STOCK_EVENTS.filter(e =>
    e.metal === metal &&
    dateSet.has(e.date) &&
    Math.abs(e.magnitude) >= bigMoveTons
  );

  // Group by date so multiple items collapse to one tick
  const byDate = {};
  for (const n of newsItems) {
    if (!byDate[n.date]) byDate[n.date] = { date:n.date, news:[], stock:[] };
    byDate[n.date].news.push(n);
  }
  for (const e of stockItems) {
    if (!byDate[e.date]) byDate[e.date] = { date:e.date, news:[], stock:[] };
    byDate[e.date].stock.push(e);
  }
  return Object.values(byDate).sort((a,b) => a.date.localeCompare(b.date));
}

// Total badge count for the toolbar bell.
function unreadCount(opts){
  opts = opts || {};
  const minConf = opts.minConf == null ? 0.6 : opts.minConf;
  const bigMoveTons = opts.bigMoveTons == null ? 5000 : opts.bigMoveTons;
  const newsN = NEWS.filter(n => n.confidence >= minConf && n.date >= '2026-05-04').length;
  const stockN = STOCK_EVENTS.filter(e => Math.abs(e.magnitude) >= bigMoveTons && e.date >= '2026-05-04').length;
  return newsN + stockN;
}

// Read of localStorage of the last "seen" timestamp for the news bell —
// items newer than that count as "new" (the dot appears).
const SEEN_KEY = 'lme.newsSeenAt';
function getLastSeen(){ try { return localStorage.getItem(SEEN_KEY); } catch(e){ return null; } }
function markSeen(){ try { localStorage.setItem(SEEN_KEY, new Date().toISOString()); } catch(e){} }
function newCount(opts){
  const lastSeen = getLastSeen();
  if (!lastSeen) return unreadCount(opts);
  return NEWS.filter(n => n.fetched_at > lastSeen && n.confidence >= (opts?.minConf ?? 0.6)).length
    + STOCK_EVENTS.filter(e => e.date > lastSeen.slice(0,10) && Math.abs(e.magnitude) >= (opts?.bigMoveTons ?? 5000)).length;
}

window.LME_NEWS = {
  NEWS, STOCK_EVENTS, SOURCE_LABEL, EVENT_TYPE, METAL_SYM, METAL_KO, DATA_NOW,
  timeAgo, sentimentDir, newsForMetal, chartMarkersFor, unreadCount, newCount,
  getLastSeen, markSeen,
};

})();
