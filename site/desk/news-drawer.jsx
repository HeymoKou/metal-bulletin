// News drawer — right-side on desktop (480px), bottom-sheet on mobile (62vh).
// Used by app.jsx. Bell button + drawer are owned by App.
const { useState: useStateND, useEffect: useEffectND, useMemo: useMemoND, useRef: useRefND, useCallback: useCallbackND } = React;

const N = window.LME_NEWS;

function NewsRow({ item, onClickMetal }){
  const dir = N.sentimentDir(item.sentiment);
  const lc = item.confidence < 0.6;
  const ev = N.EVENT_TYPE[item.event_type] || N.EVENT_TYPE.other;
  return (
    <div className={"nrow" + (lc ? ' is-lowconf' : '')}>
      <div className={"sbar sbar--" + dir}></div>
      <div className="nrow__time mono">{N.timeAgo(item.fetched_at)}</div>
      <div className="nrow__body">
        <div className="nrow__head">{item.summary_ko}</div>
        <div className="nrow__meta">
          {item.metals.length > 1
            ? <span className="mpill mpill--multi">{item.metals.length}M</span>
            : <span className="mpill" onClick={onClickMetal ? () => onClickMetal(item.metals[0]) : undefined} style={onClickMetal?{cursor:'pointer'}:{}}>{N.METAL_SYM[item.metals[0]]}</span>}
          <span className="etag"><span className="etag__g">{ev.glyph}</span>{ev.ko}</span>
          <span className="src">{(N.SOURCE_LABEL[item.source] || item.source).toUpperCase()}</span>
          {lc && <span className="conf"><span className="conf__bar" style={{ '--w': ((item.confidence*100)|0) + '%' }}></span>{(item.confidence*100)|0}</span>}
        </div>
      </div>
      <div className="nrow__r">
        <span className={"sntm sntm--" + dir}>{item.sentiment > 0 ? '+' : item.sentiment < 0 ? '−' : '·'}</span>
      </div>
    </div>
  );
}

function StockEventRow({ item, bigMoveTons }){
  const big = Math.abs(item.magnitude) >= bigMoveTons;
  const dir = item.magnitude > 0 ? 'up' : 'down';
  return (
    <div className="nrow">
      <div className={"sbar sbar--" + dir}></div>
      <div className="nrow__time mono">{item.date.slice(5)}</div>
      <div className="nrow__body">
        <div className={"nrow__head" + (big ? '' : ' nrow__head--muted')}>{item.title}</div>
        <div className="nrow__meta">
          <span className="mpill">{N.METAL_SYM[item.metal]}</span>
          <span className="etag"><span className="etag__g">▢</span>재고</span>
          <span className="src">LME</span>
          {big && <span className="etag" style={{ color:'var(--accent)', borderColor:'var(--accent)' }}>⚑ 큰변동</span>}
        </div>
      </div>
      <div className="nrow__r">
        <span className={"mono " + dir} style={{fontSize:'10.5px'}}>{item.magnitude > 0 ? '+' : ''}{item.magnitude}t</span>
      </div>
    </div>
  );
}

function groupByDate(items, getDate){
  const groups = {};
  items.forEach(it => {
    const d = getDate(it);
    if (!groups[d]) groups[d] = [];
    groups[d].push(it);
  });
  return Object.entries(groups).sort((a,b) => b[0].localeCompare(a[0]));
}

function dateLabel(d){
  if (d === '2026-05-05') return '오늘 · ' + d;
  if (d === '2026-05-04') return '어제 · ' + d;
  return d;
}

// Hook: track viewport for desktop / mobile
function useIsMobileND(){
  const [isMobile, setIsMobile] = useStateND(() => window.matchMedia('(max-width: 760px)').matches);
  useEffectND(() => {
    const mq = window.matchMedia('(max-width: 760px)');
    const fn = e => setIsMobile(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);
  return isMobile;
}

function NewsDrawer({ open, onClose, confThreshold, bigMoveTons }){
  const isMobile = useIsMobileND();
  const [tab, setTab] = useStateND('all');           // all | news | stock
  const [metalFilter, setMetalFilter] = useStateND('all'); // all | <metal>
  const [showNeg, setShowNeg] = useStateND(true);
  const [showPos, setShowPos] = useStateND(true);
  const [showFlat, setShowFlat] = useStateND(true);
  const [hideLowConf, setHideLowConf] = useStateND(true);

  // Mobile drag-to-close
  const sheetRef = useRefND(null);
  const dragRef = useRefND({ startY: null, dy: 0 });
  const [dragOffset, setDragOffset] = useStateND(0);

  useEffectND(() => {
    if (open) N.markSeen();
  }, [open]);

  // Esc to close
  useEffectND(() => {
    if (!open) return;
    function onKey(e){ if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const items = useMemoND(() => {
    const minConf = hideLowConf ? confThreshold : 0;
    let news = N.NEWS.filter(n => n.confidence >= minConf);
    if (metalFilter !== 'all') {
      news = news.filter(n => n.metals.includes(metalFilter) || n.event_type === 'macro');
    }
    news = news.filter(n => {
      const d = N.sentimentDir(n.sentiment);
      if (d === 'up' && !showPos) return false;
      if (d === 'down' && !showNeg) return false;
      if (d === 'flat' && !showFlat) return false;
      return true;
    });
    let stock = N.STOCK_EVENTS.filter(e => Math.abs(e.magnitude) >= bigMoveTons);
    if (metalFilter !== 'all') stock = stock.filter(e => e.metal === metalFilter);

    if (tab === 'news') return { news, stock: [] };
    if (tab === 'stock') return { news: [], stock };
    return { news, stock };
  }, [tab, metalFilter, showPos, showNeg, showFlat, hideLowConf, confThreshold, bigMoveTons]);

  const newsByDate = useMemoND(() => groupByDate(items.news, n => n.date), [items.news]);
  const stockByDate = useMemoND(() => groupByDate(items.stock, e => e.date), [items.stock]);

  // Merge by date for "all" view
  const merged = useMemoND(() => {
    if (tab !== 'all') return tab === 'news' ? newsByDate : stockByDate;
    const map = {};
    items.news.forEach(n => {
      if (!map[n.date]) map[n.date] = { news: [], stock: [] };
      map[n.date].news.push(n);
    });
    items.stock.forEach(e => {
      if (!map[e.date]) map[e.date] = { news: [], stock: [] };
      map[e.date].stock.push(e);
    });
    return Object.entries(map).sort((a,b) => b[0].localeCompare(a[0]));
  }, [tab, items, newsByDate, stockByDate]);

  const totalCount = items.news.length + items.stock.length;
  const newsCount = N.NEWS.filter(n => n.confidence >= confThreshold).length;
  const stockCount = N.STOCK_EVENTS.filter(e => Math.abs(e.magnitude) >= bigMoveTons).length;

  // Mobile drag handlers
  function onTouchStart(e){
    if (!isMobile) return;
    dragRef.current.startY = e.touches[0].clientY;
    dragRef.current.dy = 0;
  }
  function onTouchMove(e){
    if (!isMobile || dragRef.current.startY == null) return;
    const dy = e.touches[0].clientY - dragRef.current.startY;
    if (dy > 0) {
      dragRef.current.dy = dy;
      setDragOffset(dy);
    }
  }
  function onTouchEnd(){
    if (!isMobile) return;
    if (dragRef.current.dy > 80) onClose();
    dragRef.current.startY = null;
    dragRef.current.dy = 0;
    setDragOffset(0);
  }

  if (!open) return null;

  const metalsAll = ['copper','aluminum','zinc','nickel','lead','tin'];

  return (
    <div className={"news-drawer " + (isMobile ? 'news-drawer--mobile' : 'news-drawer--side')}
         role="dialog" aria-modal="true" aria-label="뉴스·이벤트">
      <div className="news-drawer__backdrop" onClick={onClose} />
      <aside
        ref={sheetRef}
        className="news-drawer__panel"
        style={dragOffset ? { transform: `translateY(${dragOffset}px)` } : undefined}
      >
        {isMobile && (
          <div className="news-drawer__handle" onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
            <span></span>
          </div>
        )}

        <div className="vb__drawer-h">
          <span className="ttl">뉴스 · 이벤트</span>
          <span className="cnt mono">{totalCount}건</span>
          <button className="x" onClick={onClose} aria-label="close">×</button>
        </div>

        <div className="vb__drawer-tabs">
          <button className={"vb__drawer-tab" + (tab==='all'?' is-on':'')} onClick={() => setTab('all')}>전체 · {newsCount + stockCount}</button>
          <button className={"vb__drawer-tab" + (tab==='news'?' is-on':'')} onClick={() => setTab('news')}>뉴스 · {newsCount}</button>
          <button className={"vb__drawer-tab" + (tab==='stock'?' is-on':'')} onClick={() => setTab('stock')}>재고 · {stockCount}</button>
        </div>

        <div className="vb__drawer-filters">
          <button className={"fpill" + (metalFilter==='all'?' is-on':'')} onClick={() => setMetalFilter('all')}>all</button>
          {metalsAll.map(m => (
            <button key={m} className={"fpill" + (metalFilter===m?' is-on':'')} onClick={() => setMetalFilter(m)}>{N.METAL_SYM[m]}</button>
          ))}
          <span style={{width:'1px', background:'var(--border-strong)', margin:'0 2px'}}></span>
          <button className={"fpill" + (showPos?' is-on':'')} onClick={() => setShowPos(!showPos)}>+상승</button>
          <button className={"fpill" + (showNeg?' is-on':'')} onClick={() => setShowNeg(!showNeg)}>−하락</button>
          <button className={"fpill" + (showFlat?' is-on':'')} onClick={() => setShowFlat(!showFlat)}>·중립</button>
          <span style={{width:'1px', background:'var(--border-strong)', margin:'0 2px'}}></span>
          <button className={"fpill" + (hideLowConf?' is-on':'')}
                  onClick={() => setHideLowConf(!hideLowConf)}
                  title={`신뢰도 ${(confThreshold*100)|0}% 미만 숨김`}>
            conf≥{(confThreshold*100)|0}%
          </button>
        </div>

        <div className="vb__drawer-list nlist">
          {merged.length === 0 && (
            <div style={{ padding:'40px 20px', textAlign:'center', color:'var(--text-mute)', fontSize:'12px' }}>
              조건에 해당하는 항목이 없습니다.
            </div>
          )}
          {merged.map(([date, group]) => {
            // group is either an array of news or {news, stock}
            const isAllTab = tab === 'all';
            const newsArr = isAllTab ? (group.news || []) : (Array.isArray(group) ? group : []);
            const stockArr = isAllTab ? (group.stock || []) : (Array.isArray(group) && tab === 'stock' ? group : []);
            const count = newsArr.length + stockArr.length;
            return (
              <React.Fragment key={date}>
                <div className="ngrp">
                  {dateLabel(date)}
                  <span className="ngrp__line"></span>
                  <span className="mono">{count}건</span>
                </div>
                {(isAllTab || tab === 'news' ? newsArr : []).map(n => <NewsRow key={n.id} item={n} />)}
                {(isAllTab || tab === 'stock' ? stockArr : []).map((e,i) => <StockEventRow key={date+'-'+e.metal+'-'+i} item={e} bigMoveTons={bigMoveTons} />)}
              </React.Fragment>
            );
          })}
        </div>

        <div className="vb__drawer-foot">
          <span>↻ 30s 자동갱신</span>
          <span className="mono">{N.DATA_NOW.toISOString().slice(0,16).replace('T',' ')}</span>
        </div>
      </aside>
    </div>
  );
}

window.NewsDrawer = NewsDrawer;
window.NewsRow = NewsRow;
