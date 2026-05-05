// MetalSection: hero (3 variants) + dense data tables
const { useMemo: useMemoMS, useState: useStateMS, useRef: useRefMS, useEffect: useEffectMS } = React;

function useLongPress(callback, ms = 500) {
  const timer = useRefMS(null);
  const start = (e) => {
    timer.current = setTimeout(() => callback(e), ms);
  };
  const clear = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  };
  return {
    onMouseDown: start, onTouchStart: start,
    onMouseUp: clear, onMouseLeave: clear, onTouchEnd: clear, onTouchCancel: clear,
  };
}

function CopyVal({ value, displayValue, className, copyHint, ...rest }) {
  const [flash, setFlash] = useStateMS(false);
  const lp = useLongPress(() => {
    const text = value == null ? '' : String(value);
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(()=>{});
    setFlash(true);
    setTimeout(() => setFlash(false), 900);
  });
  return (
    <span className={(className||'') + (flash ? ' val-copied' : '')} {...lp} {...rest}>
      {displayValue != null ? displayValue : value}
      {flash && <span className="copied-tag">복사됨</span>}
    </span>
  );
}

function HeroPriceFirst({ metal, latest, series, onExpand }) {
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;
  const dirCls = LME.dirClass(mainChange);
  const pctVal = mainChange != null && tm.prev_close ? (mainChange / tm.prev_close * 100) : null;
  const sym = LME.METAL_SYMBOLS[metal];
  const ko = LME.METAL_NAMES_KO[metal];
  const en = LME.METAL_NAMES_EN[metal];

  return (
    <div className="hero hero--price">
      <div className="hero__top">
        <div className="hero__id">
          <div className="hero__sym mono">{sym}</div>
          <div>
            <div className="hero__ko">{ko}</div>
            <div className="hero__en">{en} · LME 3M · USD/t</div>
          </div>
        </div>
        <button className="hero__expand" onClick={onExpand} aria-label="expand chart">
          <span className="mono">30D</span> <span style={{opacity:.5}}>↗</span>
        </button>
      </div>
      <div className="hero__price-row">
        <CopyVal className="hero__price mono" value={mainPrice} displayValue={LME.fmt(mainPrice)} />
      </div>
      <div className={"hero__change mono " + dirCls}>
        <span>{LME.arrow(mainChange)}</span>
        <span>{LME.fmtSigned(mainChange)}</span>
        {pctVal != null && <span className="hero__pct">{LME.fmtSigned(pctVal, 2)}%</span>}
      </div>
      <div className="hero__spark" onClick={onExpand}>
        <Sparkline series={series} height={56} width={320} strokeWidth={1.5} />
      </div>
      <div className="hero__ohlc mono">
        <div><span className="lbl">시가 O</span><CopyVal value={tm.open ?? cash.open} displayValue={LME.fmt(tm.open ?? cash.open)} /></div>
        <div><span className="lbl">고가 H</span><CopyVal value={tm.high ?? cash.high} displayValue={LME.fmt(tm.high ?? cash.high)} /></div>
        <div><span className="lbl">저가 L</span><CopyVal value={tm.low ?? cash.low} displayValue={LME.fmt(tm.low ?? cash.low)} /></div>
        <div><span className="lbl">종가 C</span><CopyVal value={tm.close ?? cash.close} displayValue={LME.fmt(tm.close ?? cash.close)} /></div>
      </div>
    </div>
  );
}

function HeroKrwFirst({ metal, latest, series, onExpand }) {
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const krw = latest.krw || {};
  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;
  const dirCls = LME.dirClass(mainChange);
  const pctVal = mainChange != null && tm.prev_close ? (mainChange / tm.prev_close * 100) : null;
  const sym = LME.METAL_SYMBOLS[metal];
  const ko = LME.METAL_NAMES_KO[metal];
  const en = LME.METAL_NAMES_EN[metal];
  const rateSrc = krw.source ? krw.source.toUpperCase() : '—';
  return (
    <div className="hero hero--krw">
      <div className="hero__top">
        <div className="hero__id">
          <div className="hero__sym mono">{sym}</div>
          <div>
            <div className="hero__ko">{ko}</div>
            <div className="hero__en">{en} · 3M KRW 환산 · ₩/t</div>
          </div>
        </div>
        <button className="hero__expand" onClick={onExpand} aria-label="expand chart">
          <span className="mono">30D</span> <span style={{opacity:.5}}>↗</span>
        </button>
      </div>
      <div className="hero__price-row">
        <CopyVal className="hero__price mono" value={krw['3m']} displayValue={'₩' + LME.fmtInt(krw['3m'])} />
      </div>
      <div className={"hero__change mono " + dirCls}>
        <span className="muted">USD</span>
        <span className="mono">${LME.fmt(mainPrice)}</span>
        <span>{LME.arrow(mainChange)}</span>
        <span>{LME.fmtSigned(mainChange)}</span>
        {pctVal != null && <span className="hero__pct">{LME.fmtSigned(pctVal, 2)}%</span>}
      </div>
      <div className="hero__krw-row">
        <div className="hero__krw-cell">
          <div className="lbl">Cash KRW</div>
          <div className="mono"><CopyVal value={krw.cash} displayValue={'₩' + LME.fmtInt(krw.cash)} /></div>
        </div>
        <div className="hero__krw-cell">
          <div className="lbl">적용환율 · FX</div>
          <div className="mono">
            <CopyVal value={krw.rate} displayValue={LME.fmt(krw.rate)} />
            <span className="src-flag">{rateSrc}</span>
          </div>
        </div>
      </div>
      <div className="hero__spark" onClick={onExpand}>
        <Sparkline series={series} height={48} width={320} strokeWidth={1.25} />
      </div>
    </div>
  );
}

function HeroArbFirst({ metal, latest, series, onExpand }) {
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const shfe = latest.shfe || {};
  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;
  const dirCls = LME.dirClass(mainChange);
  const sym = LME.METAL_SYMBOLS[metal];
  const ko = LME.METAL_NAMES_KO[metal];
  const en = LME.METAL_NAMES_EN[metal];
  const prem = shfe.premium_usd;
  const premDir = LME.dirClass(prem);

  return (
    <div className="hero hero--arb">
      <div className="hero__top">
        <div className="hero__id">
          <div className="hero__sym mono">{sym}</div>
          <div>
            <div className="hero__ko">{ko}</div>
            <div className="hero__en">{en} · LME ↔ SHFE 차익 · USD/t</div>
          </div>
        </div>
        <button className="hero__expand" onClick={onExpand} aria-label="expand chart">
          <span className="mono">30D</span> <span style={{opacity:.5}}>↗</span>
        </button>
      </div>

      <div className="hero__arb-grid">
        <div className="hero__arb-cell">
          <div className="lbl">LME 3M</div>
          <div className="hero__arb-val mono">{LME.fmt(mainPrice)}</div>
          <div className={"mono small " + dirCls}>{LME.arrow(mainChange)} {LME.fmtSigned(mainChange)}</div>
        </div>
        <div className={"hero__arb-prem mono " + premDir}>
          <div className="lbl">프리미엄 · Premium USD</div>
          <div className="hero__arb-prem-val">
            {LME.arrow(prem)} {LME.fmtSigned(prem, 2)}
          </div>
        </div>
        <div className="hero__arb-cell">
          <div className="lbl">SHFE 정산가</div>
          <div className="hero__arb-val mono">{LME.fmtInt(shfe.shfe_settle)}</div>
          <div className="mono small muted">CNY/t</div>
        </div>
      </div>

      <div className="hero__arb-table mono">
        <div><span className="lbl">LME 3M (CNY)</span><CopyVal value={shfe.lme_3m_cny} displayValue={LME.fmtInt(shfe.lme_3m_cny)} /></div>
        <div><span className="lbl">+ 세금포함</span><CopyVal value={shfe.lme_3m_incl_tax} displayValue={LME.fmtInt(shfe.lme_3m_incl_tax)} /></div>
        <div><span className="lbl">SHFE 3M</span><CopyVal value={shfe.shfe_3m} displayValue={LME.fmtInt(shfe.shfe_3m)} /></div>
      </div>

      <div className="hero__spark" onClick={onExpand}>
        <Sparkline series={series} height={40} width={320} strokeWidth={1.25} />
      </div>
    </div>
  );
}

function DataRow({ label, ko, en, value, displayValue, mono = true, dir, suffix, prefix, copyable = true, dim }) {
  const cls = ['kv', dim ? 'kv--dim' : '', dir ? `kv--${dir}` : ''].filter(Boolean).join(' ');
  return (
    <div className={cls}>
      <div className="kv__lbl">
        <span className="kv__ko">{ko}</span>
        {en && <span className="kv__en">{en}</span>}
      </div>
      <div className={"kv__val " + (mono ? "mono" : "")}>
        {copyable ? (
          <CopyVal value={value} displayValue={(prefix||'') + (displayValue != null ? displayValue : LME.fmt(value)) + (suffix||'')} />
        ) : (
          <span>{(prefix||'') + (displayValue != null ? displayValue : LME.fmt(value)) + (suffix||'')}</span>
        )}
      </div>
    </div>
  );
}

function MetalSection({ metal, ts, heroVariant, onActivate, onExpand }) {
  const ref = useRefMS(null);
  const latest = ts && ts.data && ts.data[0];

  useEffectMS(() => {
    if (!ref.current) return;
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('is-entering');
          if (e.intersectionRatio > 0.5) onActivate(metal);
        }
      });
    }, { threshold: [0, 0.5, 1] });
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [metal, onActivate]);

  if (!latest) {
    return <section ref={ref} className="metal-section" data-screen-label={`${LME.METAL_SYMBOLS[metal]} ${LME.METAL_NAMES_KO[metal]}`} />;
  }
  const series = useMemoMS(() => LME.priceSeries(ts.data, 'close'), [ts]);
  const invSeriesData = useMemoMS(() => LME.invSeries(ts.data), [ts]);

  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const inv = latest.inventory || {};
  const sett = latest.settlement || {};
  const shfe = latest.shfe || {};
  const krw = latest.krw || {};
  const hasCash = cash && cash.close != null;

  let Hero;
  if (heroVariant === 'krw') Hero = HeroKrwFirst;
  else if (heroVariant === 'arb') Hero = HeroArbFirst;
  else Hero = HeroPriceFirst;

  const monthlyDeltaCash = sett.monthly_avg && sett.prev_monthly_avg
    ? (sett.monthly_avg.cash - sett.prev_monthly_avg.cash) : null;
  const monthlyDelta3m = sett.monthly_avg && sett.prev_monthly_avg
    ? (sett.monthly_avg['3m'] - sett.prev_monthly_avg['3m']) : null;

  return (
    <section
      ref={ref}
      className="metal-section"
      data-metal={metal}
      data-screen-label={`${LME.METAL_SYMBOLS[metal]} ${LME.METAL_NAMES_KO[metal]}`}
    >
      <Hero metal={metal} latest={latest} series={series} onExpand={() => onExpand({metal, series, label: `${LME.METAL_NAMES_KO[metal]} · ${LME.METAL_SYMBOLS[metal]} 3M`})} />

      <div className="block">
        <div className="block__h">
          <span className="block__h-ko">LME 시세</span>
          <span className="block__h-en">LME quote · USD/t</span>
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="현금 Cash" en="" value={cash.close} dim={!hasCash} />
          <DataRow ko="3개월 3M" en="" value={tm.close} />
          <DataRow ko="시가 Open" en="" value={tm.open ?? cash.open} dim={!hasCash && (tm.open == null)} />
          <DataRow ko="고가 High" en="" value={tm.high ?? cash.high} />
          <DataRow ko="저가 Low" en="" value={tm.low ?? cash.low} />
          <DataRow ko="전일종가" en="prev close" value={tm.prev_close ?? cash.prev_close} />
          <DataRow ko="매수호가" en="bid" value={lme.bid} />
          <DataRow ko="매도호가" en="ask" value={lme.ask} />
        </div>
        <div className="kv-grid kv-grid--1 kv-grid--accent">
          <DataRow ko="미결제약정" en="open interest · contracts" value={lme.open_interest} displayValue={LME.fmtInt(lme.open_interest)} />
        </div>
        {!hasCash && (
          <div className="block__note">
            <span className="dot dot--dim" /> Cash 시세 미공개 — Zn/Pb/Ni/Sn은 LME에서 3M만 게시
          </div>
        )}
      </div>

      <div className="block">
        <div className="block__h">
          <span className="block__h-ko">정산가</span>
          <span className="block__h-en">Settlement · USD/t</span>
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="Cash 정산" en="cash settle" value={sett.cash} />
          <DataRow ko="3M 정산" en="3M settle" value={sett['3m']} />
          <DataRow ko="당월평균 Cash" en="MTD avg cash" value={sett.monthly_avg?.cash} dir={LME.dirClass(monthlyDeltaCash)} />
          <DataRow ko="당월평균 3M" en="MTD avg 3M" value={sett.monthly_avg?.['3m']} dir={LME.dirClass(monthlyDelta3m)} />
          <DataRow ko="전월평균 Cash" en="prev mo. cash" value={sett.prev_monthly_avg?.cash} dim />
          <DataRow ko="전월평균 3M" en="prev mo. 3M" value={sett.prev_monthly_avg?.['3m']} dim />
        </div>
        <div className="forwards">
          <div className="forwards__lbl">
            <span className="block__h-ko" style={{fontSize:'10.5px'}}>선물커브</span>
            <span className="block__h-en">forward curve</span>
          </div>
          <div className="forwards__row mono">
            <div><div className="lbl">M+1</div><div>{LME.fmt(sett.forwards?.m1)}</div></div>
            <div><div className="lbl">M+2</div><div>{LME.fmt(sett.forwards?.m2)}</div></div>
            <div><div className="lbl">M+3</div><div>{LME.fmt(sett.forwards?.m3)}</div></div>
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block__h">
          <span className="block__h-ko">LME 재고</span>
          <span className="block__h-en">Inventory · tonnes</span>
          <div className="block__h-spark"><Sparkline series={invSeriesData} height={20} width={70} strokeWidth={1} accent="var(--text-mute)" /></div>
        </div>
        <div className="inv-row">
          <div className="inv-row__main mono">
            <CopyVal value={inv.current} displayValue={LME.fmtInt(inv.current)} />
            <span className={"inv-row__delta mono " + LME.dirClass(inv.change)}>
              {LME.arrow(inv.change)} {LME.fmtSignedInt(inv.change)}
            </span>
          </div>
          <div className="inv-row__sub mono">
            <span className="lbl">전일</span> {LME.fmtInt(inv.prev)}
          </div>
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="반입 In" en="" value={inv['in']} displayValue={LME.fmtInt(inv['in'])} />
          <DataRow ko="반출 Out" en="" value={inv.out} displayValue={LME.fmtInt(inv.out)} />
          <DataRow ko="유효재고" en="on warrant" value={inv.on_warrant} displayValue={LME.fmtInt(inv.on_warrant)} />
          <DataRow ko="취소창고" en="cancelled warrant" value={inv.cancelled_warrant} displayValue={LME.fmtInt(inv.cancelled_warrant)} />
        </div>
        <div className="kv-grid kv-grid--1">
          <DataRow ko="취소창고 변동" en="CW change" value={inv.cw_change} displayValue={LME.fmtSignedInt(inv.cw_change)} dir={LME.dirClass(inv.cw_change)} />
        </div>
      </div>

      <div className="block">
        <div className="block__h">
          <span className="block__h-ko">SHFE 비교</span>
          <span className="block__h-en">SHFE arbitrage</span>
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="SHFE 정산가" en="SHFE settle · CNY" value={shfe.shfe_settle} displayValue={LME.fmtInt(shfe.shfe_settle)} />
          <DataRow ko="SHFE 3M" en="SHFE 3M · CNY" value={shfe.shfe_3m} displayValue={LME.fmtInt(shfe.shfe_3m)} />
          <DataRow ko="LME 3M (CNY)" en="excl. tax" value={shfe.lme_3m_cny} displayValue={LME.fmtInt(shfe.lme_3m_cny)} />
          <DataRow ko="LME 3M (CNY)" en="incl. tax" value={shfe.lme_3m_incl_tax} displayValue={LME.fmtInt(shfe.lme_3m_incl_tax)} />
          <DataRow ko="LME 현금 (CNY)" en="excl. tax" value={shfe.lme_near_cny} displayValue={LME.fmtInt(shfe.lme_near_cny)} dim={!hasCash} />
          <DataRow ko="LME 현금 (CNY)" en="incl. tax" value={shfe.lme_near_incl_tax} displayValue={LME.fmtInt(shfe.lme_near_incl_tax)} dim={!hasCash} />
        </div>
        <div className="kv-grid kv-grid--1 kv-grid--accent">
          <DataRow ko="프리미엄" en="premium · USD/t" value={shfe.premium_usd} displayValue={LME.fmtSigned(shfe.premium_usd, 2)} dir={LME.dirClass(shfe.premium_usd)} />
        </div>
      </div>

      <div className="block">
        <div className="block__h">
          <span className="block__h-ko">원화 환산</span>
          <span className="block__h-en">KRW conversion · ₩/t</span>
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="Cash" en="₩" value={krw.cash} displayValue={LME.fmtInt(krw.cash)} prefix="₩" dim={!hasCash} />
          <DataRow ko="3M" en="₩" value={krw['3m']} displayValue={LME.fmtInt(krw['3m'])} prefix="₩" />
        </div>
        <div className="kv-grid kv-grid--2">
          <DataRow ko="적용환율" en="applied FX" value={krw.rate} />
          <DataRow ko="환율 출처" en="source" value={krw.source} displayValue={(krw.source||'—').toUpperCase()} mono={true} copyable={false} />
        </div>
      </div>

      <div className="block block--meta">
        <span className="lbl">데이터 기준 · as of</span>
        <span className="mono">{latest.date}</span>
        <span className="block__sep">·</span>
        <span className="lbl">단위 · unit</span>
        <span className="mono">{ts.unit || 'USD/t'}</span>
      </div>
    </section>
  );
}

window.MetalSection = MetalSection;
