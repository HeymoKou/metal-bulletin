// Sparkline + expanded chart components.
const { useMemo, useState, useRef, useEffect } = React;

function Sparkline({ series, height, width, strokeWidth, accent }) {
  const h = height || 28;
  const w = width || 84;
  const sw = strokeWidth || 1.25;
  if (!series || series.length < 2) {
    return <svg width={w} height={h} aria-hidden="true" />;
  }
  const vals = series.map(p => p.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const pad = 2;
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;
  const step = innerW / (series.length - 1);
  const pts = series.map((p, i) => {
    const x = pad + i * step;
    const y = pad + innerH - ((p.v - min) / range) * innerH;
    return [x, y];
  });
  const dLine = pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(2)+' '+p[1].toFixed(2)).join(' ');
  const trending = vals[vals.length - 1] >= vals[0];
  const stroke = accent || (trending ? 'var(--up)' : 'var(--down)');
  const fillId = 'spk-' + Math.random().toString(36).slice(2, 8);
  const dArea = dLine + ` L ${pts[pts.length-1][0].toFixed(2)} ${(h-pad).toFixed(2)} L ${pts[0][0].toFixed(2)} ${(h-pad).toFixed(2)} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display:'block' }}>
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={dArea} fill={`url(#${fillId})`} />
      <path d={dLine} fill="none" stroke={stroke} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r={1.6} fill={stroke} />
    </svg>
  );
}

function ExpandedChart({ series, label, onClose, accent, markers, bigMoveTons }) {
  const [hover, setHover] = useState(null);
  const [activeMarker, setActiveMarker] = useState(null);
  const ref = useRef(null);
  const W = 360, H = 200, padL = 44, padR = 12, padT = 16, padB = 28;

  const { pts, min, max, dLine, dArea, dates } = useMemo(() => {
    if (!series || series.length < 2) return { pts: [] };
    const vals = series.map(p => p.v);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;
    const step = innerW / (series.length - 1);
    const pts = series.map((p, i) => [padL + i * step, padT + innerH - ((p.v - min) / range) * innerH]);
    const dLine = pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(2)+' '+p[1].toFixed(2)).join(' ');
    const dArea = dLine + ` L ${pts[pts.length-1][0].toFixed(2)} ${(padT+innerH).toFixed(2)} L ${pts[0][0].toFixed(2)} ${(padT+innerH).toFixed(2)} Z`;
    return { pts, min, max, dLine, dArea, dates: series.map(p=>p.date) };
  }, [series]);

  function onMove(e){
    if (!pts.length) return;
    const rect = ref.current.getBoundingClientRect();
    const x = ((e.touches?e.touches[0].clientX:e.clientX) - rect.left) * (W / rect.width);
    let best = 0, bestD = Infinity;
    for (let i=0;i<pts.length;i++){
      const d = Math.abs(pts[i][0] - x);
      if (d < bestD){ bestD = d; best = i; }
    }
    setHover(best);
  }
  function onLeave(){ setHover(null); }

  const trending = series && series.length>1 ? (series[series.length-1].v >= series[0].v) : true;
  const stroke = accent || (trending ? 'var(--up)' : 'var(--down)');
  const fillId = 'exp-fill';
  const ticks = useMemo(() => {
    if (min == null) return [];
    return [max, (max+min)/2, min];
  }, [min, max]);

  if (!series || series.length < 2) return null;

  const cur = hover != null ? series[hover] : series[series.length - 1];

  return (
    <div className="chart-overlay" role="dialog" aria-modal="true">
      <div className="chart-overlay__backdrop" onClick={onClose} />
      <div className="chart-overlay__panel">
        <div className="chart-overlay__head">
          <div>
            <div className="chart-overlay__title">{label}</div>
            <div className="chart-overlay__sub">최근 30일 · 30-day · {series[0].date} → {series[series.length-1].date}</div>
          </div>
          <button className="chart-overlay__close" onClick={onClose} aria-label="close">✕</button>
        </div>
        <div className="chart-overlay__readout">
          <div>
            <div className="lbl">{cur.date}</div>
            <div className="val mono">{LME.fmt(cur.v)}</div>
          </div>
          <div>
            <div className="lbl">변동 vs 시작 · vs start</div>
            <div className={"val mono " + LME.dirClass(cur.v - series[0].v)}>
              {LME.fmtSigned(cur.v - series[0].v)} <span className="muted">({LME.fmtSigned((cur.v-series[0].v)/series[0].v*100, 2)}%)</span>
            </div>
          </div>
        </div>
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width="100%" height="200"
             onMouseMove={onMove} onMouseLeave={onLeave}
             onTouchStart={onMove} onTouchMove={onMove}>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>
          {ticks.map((t,i)=>{
            const y = padT + (H - padT - padB) * (i / (ticks.length - 1));
            return (
              <g key={i}>
                <line x1={padL} x2={W - padR} y1={y} y2={y} stroke="var(--border)" strokeDasharray="2 3" />
                <text x={padL - 6} y={y + 3} textAnchor="end" className="chart-tick">{LME.fmt(t, t > 1000 ? 0 : 2)}</text>
              </g>
            );
          })}
          <path d={dArea} fill={`url(#${fillId})`} />
          <path d={dLine} fill="none" stroke={stroke} strokeWidth="1.5" />
          {hover != null && (
            <g>
              <line x1={pts[hover][0]} x2={pts[hover][0]} y1={padT} y2={H-padB} stroke="var(--text-muted)" strokeDasharray="2 3" />
              <circle cx={pts[hover][0]} cy={pts[hover][1]} r="3" fill={stroke} stroke="var(--bg-1)" strokeWidth="1.5" />
            </g>
          )}
          {markers && markers.map((mk, i) => {
            const idx = dates.indexOf(mk.date);
            if (idx < 0) return null;
            const x = pts[idx][0];
            const hasBig = mk.stock && mk.stock.some(s => Math.abs(s.magnitude) >= (bigMoveTons || 5000));
            const sentSum = (mk.news || []).reduce((a,n) => a + n.sentiment, 0);
            const cls = hasBig ? 'mk--big' : sentSum > 0 ? 'mk--up' : sentSum < 0 ? 'mk--down' : 'mk--flat';
            const stroke = hasBig ? 'var(--accent)' : sentSum > 0 ? 'var(--up)' : sentSum < 0 ? 'var(--down)' : 'var(--text-mute)';
            return (
              <g key={i} className={'chart-mk ' + cls} style={{cursor:'pointer'}}
                 onClick={(ev) => { ev.stopPropagation(); setActiveMarker(activeMarker === i ? null : i); }}>
                <line x1={x} x2={x} y1={padT} y2={H-padB} stroke={stroke} strokeWidth="1" opacity={hasBig ? 0.85 : 0.45} strokeDasharray={hasBig?'':'2 2'} />
                <circle cx={x} cy={padT - 2} r="3.5" fill={stroke} stroke="var(--bg-1)" strokeWidth="1" />
                {(mk.news||[]).length > 1 && (
                  <text x={x} y={padT + 1} textAnchor="middle" fontSize="7" fill="var(--bg-0)" fontFamily="IBM Plex Mono">{mk.news.length}</text>
                )}
              </g>
            );
          })}
          <text x={padL} y={H - 8} className="chart-tick">{dates[0]}</text>
          <text x={W - padR} y={H - 8} textAnchor="end" className="chart-tick">{dates[dates.length-1]}</text>
        </svg>
        {activeMarker != null && markers && markers[activeMarker] && (
          <div className="chart-mk-pop">
            <div className="chart-mk-pop__h">
              <span className="mono">{markers[activeMarker].date}</span>
              <button className="chart-mk-pop__x" onClick={() => setActiveMarker(null)} aria-label="close">×</button>
            </div>
            {(markers[activeMarker].stock||[]).map((s,i) => (
              <div key={'s'+i} className="chart-mk-pop__row">
                <span className="etag" style={{color:'var(--accent)', borderColor:'var(--accent)'}}>⚑ {Math.abs(s.magnitude) >= (bigMoveTons||5000) ? '큰변동' : '재고'}</span>
                <span className={"mono " + (s.magnitude>0?'up':'down')}>{s.magnitude>0?'+':''}{s.magnitude}t</span>
                <span className="chart-mk-pop__t">{s.title}</span>
              </div>
            ))}
            {(markers[activeMarker].news||[]).slice(0,4).map((n,i) => (
              <div key={'n'+i} className="chart-mk-pop__row">
                <span className={"sntm sntm--"+(n.sentiment>0?'up':n.sentiment<0?'down':'flat')}>{n.sentiment>0?'+':n.sentiment<0?'−':'·'}</span>
                <span className="chart-mk-pop__t">{n.summary_ko}</span>
                <span className="src" style={{flexShrink:0}}>{(window.LME_NEWS.SOURCE_LABEL[n.source]||n.source).toUpperCase()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

window.Sparkline = Sparkline;
window.ExpandedChart = ExpandedChart;
