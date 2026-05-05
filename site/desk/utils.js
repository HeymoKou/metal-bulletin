// Plain JS utility helpers loaded as a global.
(function(){
  const METAL_NAMES_KO = {
    copper: '전기동', aluminum: '알루미늄', zinc: '아연',
    nickel: '니켈', lead: '납', tin: '주석',
  };
  const METAL_NAMES_EN = {
    copper: 'Copper', aluminum: 'Aluminium', zinc: 'Zinc',
    nickel: 'Nickel', lead: 'Lead', tin: 'Tin',
  };
  const METAL_SYMBOLS = {
    copper: 'Cu', aluminum: 'Al', zinc: 'Zn',
    nickel: 'Ni', lead: 'Pb', tin: 'Sn',
  };
  const METAL_ORDER = ['copper','aluminum','zinc','nickel','lead','tin'];

  function fmt(n, digits){
    if (n == null || isNaN(n)) return '—';
    const d = digits == null ? 2 : digits;
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function fmtInt(n){
    if (n == null || isNaN(n)) return '—';
    return Math.round(n).toLocaleString('en-US');
  }
  function fmtSigned(n, digits){
    if (n == null || isNaN(n)) return '—';
    const s = fmt(Math.abs(n), digits);
    if (n > 0) return '+' + s;
    if (n < 0) return '−' + s;
    return s;
  }
  function fmtSignedInt(n){
    if (n == null || isNaN(n)) return '—';
    const s = fmtInt(Math.abs(n));
    if (n > 0) return '+' + s;
    if (n < 0) return '−' + s;
    return s;
  }
  function pct(curr, prev){
    if (curr == null || prev == null || !prev) return null;
    return ((curr - prev) / prev) * 100;
  }
  function dirClass(n){
    if (n == null || n === 0) return 'flat';
    return n > 0 ? 'up' : 'down';
  }
  function arrow(n){
    if (n == null || n === 0) return '·';
    return n > 0 ? '▲' : '▼';
  }

  // last30 returns array oldest→newest of {date, close}
  function priceSeries(data, key){
    const k = key || 'close';
    return data.slice(0, 30).reverse().map(d => {
      const lme = d.lme || {};
      const ref = lme['3m'] || lme.cash || {};
      return { date: d.date, v: ref[k] != null ? ref[k] : null };
    }).filter(p => p.v != null);
  }
  function invSeries(data){
    return data.slice(0, 30).reverse().map(d => ({
      date: d.date, v: (d.inventory && d.inventory.current != null) ? d.inventory.current : null
    })).filter(p => p.v != null);
  }

  window.LME = {
    METAL_NAMES_KO, METAL_NAMES_EN, METAL_SYMBOLS, METAL_ORDER,
    fmt, fmtInt, fmtSigned, fmtSignedInt, pct, dirClass, arrow,
    priceSeries, invSeries,
  };
})();
