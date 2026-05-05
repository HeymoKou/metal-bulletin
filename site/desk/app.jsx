// Main app: nav + header + tweaks + sections + expanded chart overlay
const { useState: useStateApp, useEffect: useEffectApp, useMemo: useMemoApp, useRef: useRefApp, useCallback: useCallbackApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "heroVariant": "price",
  "density": "compact",
  "lang": "ko",
  "showSHFE": true,
  "showForwards": true,
  "showInventoryGrid": true,
  "showKRW": true,
  "navStyle": "pricepct",
  "accent": "muted",
  "showNews": true,
  "showChartMarkers": true,
  "confThreshold": 0.6,
  "bigMoveTons": 5000
}/*EDITMODE-END*/;

function NavPill({ metal, ts, active, onClick }) {
  const latest = ts && ts.data && ts.data[0];
  const lme = (latest && latest.lme) || {};
  const tm = lme['3m'] || lme.cash || {};
  const close = tm.close;
  const change = tm.change;
  const pct = (change != null && tm.prev_close) ? (change / tm.prev_close * 100) : null;
  const dir = LME.dirClass(change);
  return (
    <button className={"nav-pill " + (active ? 'is-active ' : '') + 'nav-pill--' + dir} onClick={onClick}>
      <span className="nav-pill__sym mono">{LME.METAL_SYMBOLS[metal]}</span>
      <div className="nav-pill__col">
        <span className="nav-pill__price mono">{LME.fmt(close, close > 1000 ? 0 : 2)}</span>
        <span className={"nav-pill__pct mono " + dir}>
          {LME.arrow(change)} {pct == null ? '—' : LME.fmtSigned(pct, 2) + '%'}
        </span>
      </div>
    </button>
  );
}

function PullToRefresh({ onRefresh, scrollerRef }) {
  const [pull, setPull] = useStateApp(0);
  const [refreshing, setRefreshing] = useStateApp(false);
  const startY = useRefApp(null);

  useEffectApp(() => {
    const el = scrollerRef.current;
    if (!el) return;
    function ts(e){
      if (el.scrollTop <= 0) startY.current = e.touches[0].clientY;
      else startY.current = null;
    }
    function tm(e){
      if (startY.current == null) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy > 0 && el.scrollTop <= 0) {
        setPull(Math.min(80, dy * 0.5));
        if (dy > 0) e.preventDefault?.();
      }
    }
    function te(){
      if (pull > 50) {
        setRefreshing(true);
        setPull(40);
        onRefresh();
        setTimeout(() => { setRefreshing(false); setPull(0); }, 900);
      } else {
        setPull(0);
      }
      startY.current = null;
    }
    el.addEventListener('touchstart', ts, {passive:true});
    el.addEventListener('touchmove', tm, {passive:false});
    el.addEventListener('touchend', te);
    return () => {
      el.removeEventListener('touchstart', ts);
      el.removeEventListener('touchmove', tm);
      el.removeEventListener('touchend', te);
    };
  }, [scrollerRef, pull, onRefresh]);

  if (pull <= 0 && !refreshing) return null;
  return (
    <div className="ptr" style={{ height: pull + 'px' }}>
      <span className={"mono " + (refreshing ? 'ptr--spin' : '')}>
        {refreshing ? '⟳ 갱신중 · refreshing' : (pull > 50 ? '↑ 놓아서 갱신 · release' : '↓ 당겨서 갱신 · pull')}
      </span>
    </div>
  );
}

function MarqueeMacro({ daily }) {
  if (!daily || !daily.market) return null;
  const m = daily.market;
  const items = [
    { ko: 'KRW/USD', v: LME.fmt(m.krw_usd), c: m.krw_change },
    { ko: 'WTI', v: LME.fmt(m.wti), c: m.wti_change },
    { ko: 'S&P 500', v: LME.fmt(m.sp500, 0), c: m.sp500_change },
    { ko: 'DOW', v: LME.fmt(m.dow, 0), c: m.dow_change },
    { ko: 'EUR/USD', v: LME.fmt(m.eur_usd, 4), c: null },
    { ko: 'JPY/USD', v: LME.fmt(m.jpy_usd, 2), c: null },
  ];
  return (
    <div className="macro">
      {items.map((it,i) => (
        <div key={i} className="macro__item">
          <span className="macro__lbl">{it.ko}</span>
          <span className="mono macro__v">{it.v}</span>
          {it.c != null && <span className={"mono macro__c " + LME.dirClass(it.c)}>{LME.arrow(it.c)} {LME.fmtSigned(it.c, 2)}</span>}
        </div>
      ))}
    </div>
  );
}

function TweaksUI({ tweaks, setTweak }) {
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection title="Hero variant">
        <TweakRadio
          value={tweaks.heroVariant}
          onChange={v => setTweak('heroVariant', v)}
          options={[
            {value:'price', label:'A · Price'},
            {value:'krw', label:'B · KRW'},
            {value:'arb', label:'C · SHFE arb'},
          ]}
        />
      </TweakSection>
      <TweakSection title="Density">
        <TweakRadio
          value={tweaks.density}
          onChange={v => setTweak('density', v)}
          options={[
            {value:'compact', label:'Compact'},
            {value:'cozy', label:'Cozy'},
            {value:'comfy', label:'Comfy'},
          ]}
        />
      </TweakSection>
      <TweakSection title="Language">
        <TweakRadio
          value={tweaks.lang}
          onChange={v => setTweak('lang', v)}
          options={[
            {value:'ko', label:'KR primary'},
            {value:'both', label:'KR + EN'},
            {value:'en', label:'EN primary'},
          ]}
        />
      </TweakSection>
      <TweakSection title="Nav style">
        <TweakRadio
          value={tweaks.navStyle}
          onChange={v => setTweak('navStyle', v)}
          options={[
            {value:'pricepct', label:'Price + Δ%'},
            {value:'symbolonly', label:'Symbol'},
          ]}
        />
      </TweakSection>
      <TweakSection title="Accent">
        <TweakRadio
          value={tweaks.accent}
          onChange={v => setTweak('accent', v)}
          options={[
            {value:'muted', label:'Muted'},
            {value:'classic', label:'Terminal'},
          ]}
        />
      </TweakSection>
      <TweakSection title="Show / hide">
        <TweakToggle label="SHFE block" value={tweaks.showSHFE} onChange={v => setTweak('showSHFE', v)} />
        <TweakToggle label="Forward curve" value={tweaks.showForwards} onChange={v => setTweak('showForwards', v)} />
        <TweakToggle label="Inventory grid" value={tweaks.showInventoryGrid} onChange={v => setTweak('showInventoryGrid', v)} />
        <TweakToggle label="KRW block" value={tweaks.showKRW} onChange={v => setTweak('showKRW', v)} />
      </TweakSection>
      <TweakSection title="News &amp; events">
        <TweakToggle label="Show news drawer" value={tweaks.showNews} onChange={v => setTweak('showNews', v)} />
        <TweakToggle label="Chart markers" value={tweaks.showChartMarkers} onChange={v => setTweak('showChartMarkers', v)} />
        <TweakSlider label="Min confidence" value={Math.round(tweaks.confThreshold*100)} min={0} max={100} step={5} unit="%" onChange={v => setTweak('confThreshold', v/100)} />
        <TweakSlider label="Big stock move" value={tweaks.bigMoveTons} min={1000} max={20000} step={500} unit="t" onChange={v => setTweak('bigMoveTons', v)} />
      </TweakSection>
      <TweakSection title="Reference">
        <a href="Critique.html" className="tweaks-critique-link" target="_blank" rel="noopener">
          → 현행 구현 비평 · Read critique
        </a>
      </TweakSection>
    </TweaksPanel>
  );
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [active, setActive] = useStateApp('copper');
  const [expanded, setExpanded] = useStateApp(null);
  const [now, setNow] = useStateApp(new Date());
  const [drawerOpen, setDrawerOpen] = useStateApp(false);
  const [bellTick, setBellTick] = useStateApp(0);
  const scrollerRef = useRefApp(null);
  const data = window.METALS_DATA;

  useEffectApp(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  const onActivate = useCallbackApp((m) => setActive(m), []);
  const onExpand = useCallbackApp((payload) => setExpanded(payload), []);
  const refresh = () => setNow(new Date());

  function scrollTo(metal){
    const el = scrollerRef.current?.querySelector(`.metal-section[data-metal="${metal}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const latestDate = data.copper?.last_updated || data.copper?.data?.[0]?.date;
  const krwRate = data.copper?.data?.[0]?.krw?.rate;
  const krwSrc = data.copper?.data?.[0]?.krw?.source;
  const fakeDaily = useMemoApp(() => ({
    market: {
      krw_usd: krwRate || 1471.94,
      krw_change: -5.63, wti: 101.46, wti_change: -3.61,
      sp500: 7240.58, sp500_change: 31.57,
      dow: 49626.53, dow_change: -25.61,
      eur_usd: 1.1741, jpy_usd: 156.92,
    }
  }), [krwRate]);

  const root = useRefApp(null);
  useEffectApp(() => {
    if (!root.current) return;
    root.current.dataset.density = tweaks.density;
    root.current.dataset.lang = tweaks.lang;
    root.current.dataset.accent = tweaks.accent;
  }, [tweaks.density, tweaks.lang, tweaks.accent]);

  const ts = (now).toLocaleTimeString('en-GB', { hour12: false });

  return (
    <div className="app" ref={root} data-density={tweaks.density} data-lang={tweaks.lang} data-accent={tweaks.accent}>
      <header className="app__header">
        <div className="app__head-l">
          <div className="brand">
            <span className="brand__mark mono">LME</span>
            <span className="brand__sub">비철금속 데스크 · Non-Ferrous Desk</span>
          </div>
        </div>
        <div className="app__head-r mono">
          {tweaks.showNews && (() => {
            const N = window.LME_NEWS;
            const newCount = N.newCount({ minConf: tweaks.confThreshold, bigMoveTons: tweaks.bigMoveTons });
            const totalCount = N.unreadCount({ minConf: tweaks.confThreshold, bigMoveTons: tweaks.bigMoveTons });
            return (
              <button className={"news-bell " + (newCount > 0 ? 'news-bell--has-new' : '')}
                onClick={() => { setDrawerOpen(true); setBellTick(t => t + 1); }}
                aria-label="open news drawer">
                <span className="news-bell__icon">◉</span>
                <span className="news-bell__lbl">뉴스</span>
                <span className="news-bell__cnt mono">{totalCount}</span>
                {newCount > 0 && <span className="news-bell__dot" aria-hidden="true"></span>}
              </button>
            );
          })()}
          <span className="dot dot--live" />
          <span className="head__ts">{latestDate} · {ts}</span>
        </div>
      </header>

      <div className="app__rate">
        <div className="rate__main">
          <span className="lbl">USD/KRW</span>
          <span className="mono rate__v">{LME.fmt(krwRate)}</span>
          <span className="rate__src">{(krwSrc||'—').toUpperCase()}</span>
        </div>
        <MarqueeMacro daily={fakeDaily} />
      </div>

      <nav className={"app__nav nav--" + tweaks.navStyle}>
        {LME.METAL_ORDER.map(m => (
          <NavPill key={m} metal={m} ts={data[m]} active={active===m} onClick={() => scrollTo(m)} />
        ))}
      </nav>

      <div className="app__scroller" ref={scrollerRef}>
        <PullToRefresh onRefresh={refresh} scrollerRef={scrollerRef} />
        {LME.METAL_ORDER.map(m => (
          <MetalSection
            key={m}
            metal={m}
            ts={data[m]}
            heroVariant={tweaks.heroVariant}
            onActivate={onActivate}
            onExpand={onExpand}
            showSHFE={tweaks.showSHFE}
            showForwards={tweaks.showForwards}
            showInventoryGrid={tweaks.showInventoryGrid}
            showKRW={tweaks.showKRW}
          />
        ))}
        <footer className="app__footer">
          <div className="mono">END · 데이터 끝</div>
          <div className="lbl">Source: LME · SHFE · BOK · PDF · 마감 기준</div>
        </footer>
      </div>

      {expanded && (
        <ExpandedChart
          series={expanded.series}
          label={expanded.label}
          markers={tweaks.showChartMarkers ? window.LME_NEWS.chartMarkersFor(expanded.metal, expanded.series.map(p => p.date), { minConf: tweaks.confThreshold, bigMoveTons: tweaks.bigMoveTons }) : null}
          bigMoveTons={tweaks.bigMoveTons}
          onClose={() => setExpanded(null)}
        />
      )}

      <NewsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        confThreshold={tweaks.confThreshold}
        bigMoveTons={tweaks.bigMoveTons}
      />

      <TweaksUI tweaks={tweaks} setTweak={setTweak} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
