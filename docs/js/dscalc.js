/* Step-by-step DS workbench: build a loop record by hand and watch
   n, T, n·t, waste, used green and DS being calculated. */
(function () {
  const $ = id => document.getElementById(id);
  const cv = $('wbCv'); if (!cv) return;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#888';
  const NEED = '#2f7fd1';
  const f1 = v => (Math.round(v * 10) / 10).toFixed(1), f2 = v => v.toFixed(2);

  let g = 30, occ = 0.67, t = 1.0, cars = [], drag = null, mode = 'all', stepShown = 6;

  // ---------- presets
  const PRESETS = {
    slide: { g: 30, n: 12, occ: 2 / 3, t: 1.0, label: 'Slide example' },
    light: { g: 30, n: 6, occ: 0.5, t: 1.0, label: 'Light traffic' },
    sat: { g: 30, n: 15, occ: 1.0, t: 1.0, label: 'Saturated' },
    jam: { g: 30, n: 12, occ: 2.2, t: 1.0, label: 'Crawling jam' },
  };
  function spread(n) {
    const free = g - n * occ; if (free < 0) { n = Math.floor(g / occ); }
    const gap = (g - n * occ) / n; cars = [];
    for (let i = 0; i < n; i++) cars.push(+(gap / 2 + i * (occ + gap)).toFixed(3));
  }
  function load(k) {
    const p = PRESETS[k]; g = p.g; occ = p.occ; t = p.t;
    $('wbG').value = g; $('wbOcc').value = occ; $('wbT').value = t;
    spread(p.n); syncOut(); render();
    document.querySelectorAll('#wbPre button').forEach(x => x.setAttribute('aria-pressed', x.dataset.p === k));
  }

  // ---------- geometry
  const PAD = 8, BAR_Y = 30, BAR_H = 46;
  let W = 600, H = 150, sc = 1;
  function size() {
    const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2.5);
    W = r.width; H = r.height; cv.width = W * d; cv.height = H * d;
    const c = cv.getContext('2d'); c.setTransform(d, 0, 0, d, 0, 0); sc = (W - 2 * PAD) / g; return c;
  }
  const X = s => PAD + s * sc, S = x => (x - PAD) / sc;

  function gapsOf() {
    const cs = [...cars].sort((a, b) => a - b), gs = []; let prev = 0;
    cs.forEach(a => { if (a - prev > 1e-6) gs.push([prev, a]); prev = Math.max(prev, a + occ); });
    if (g - prev > 1e-6) gs.push([prev, g]);
    return gs;
  }
  function calc() {
    const gs = gapsOf(), n = cars.length;
    const T = gs.reduce((s, [a, b]) => s + (b - a), 0);
    const need = n * t, waste = T - need, used = g - waste, ds = used / g;
    return { gs, n, T, need, waste, used, ds };
  }

  // ---------- drawing
  function draw(R) {
    const c = size(); c.clearRect(0, 0, W, H);
    c.font = '600 13px Barlow, sans-serif'; c.fillStyle = css('--muted');
    c.textAlign = 'left'; c.fillText('green starts', PAD, 18); c.textAlign = 'right'; c.fillText(`green ends · g = ${g} s`, W - PAD, 18);
    c.fillStyle = css('--sunk'); c.fillRect(PAD, BAR_Y, W - 2 * PAD, BAR_H);
    let left = R.need;
    R.gs.forEach(([a, b]) => {
      const len = b - a, nd = Math.max(0, Math.min(len, t, left)); left -= nd;
      c.globalAlpha = 0.55; c.fillStyle = NEED; c.fillRect(X(a), BAR_Y, nd * sc, BAR_H);
      if (len - nd > 1e-6) { c.fillStyle = css('--stop'); c.fillRect(X(a + nd), BAR_Y, (len - nd) * sc, BAR_H); }
      c.globalAlpha = 1;
      if (len * sc > 30) { c.fillStyle = css('--fg'); c.textAlign = 'center'; c.font = '600 11.5px Barlow, sans-serif'; c.fillText(f1(len), X(a + len / 2), BAR_Y + BAR_H + 14); }
    });
    cars.forEach((a, i) => {
      c.fillStyle = drag && drag.i === i ? css('--amber') : css('--fg');
      c.fillRect(X(a), BAR_Y, Math.max(2, occ * sc), BAR_H);
    });
    // ticks
    c.fillStyle = css('--muted'); c.font = '11px Barlow, sans-serif'; c.textAlign = 'center';
    const step = g > 40 ? 10 : 5;
    for (let s = 0; s <= g; s += 1) { const big = s % step === 0; c.fillRect(X(s) - 0.5, BAR_Y + BAR_H + (big ? 18 : 20), 1, big ? 6 : 3); if (big) { c.textAlign = s === 0 ? 'left' : s >= g - 0.01 ? 'right' : 'center'; c.fillText(s + ' s', X(s), BAR_Y + BAR_H + 36); } }
    c.textAlign = 'left'; c.font = '12px Barlow, sans-serif';
    c.fillText('numbers under the bar = length of each empty gap (s)', PAD, H - 6);
  }

  // ---------- steps
  function steps(R) {
    const list = R.gs.map(([a, b]) => f1(b - a));
    const sum = list.length > 8 ? list.slice(0, 4).join(' + ') + ' + … + ' + list.slice(-2).join(' + ') : list.join(' + ');
    const wasteTxt = R.waste >= 0 ? f1(R.waste) : `−${f1(-R.waste)}`;
    return [
      ['Count the cars', 'n', `<b>${R.n}</b>`, 'every dark block on the loop'],
      ['Add up the empty time on the loop', `T = ${sum || '0'}`, `<b>${f1(R.T)} s</b>`, `${list.length} gaps`],
      ['Gap the cars deserved', `n·t = ${R.n} × ${f2(t)}`, `<b>${f1(R.need)} s</b>`, 'standard space time per car'],
      ['Wasted green', `waste = T − n·t = ${f1(R.T)} − ${f1(R.need)}`, `<b>${wasteTxt} s</b>`, R.waste < 0 ? 'negative: gaps smaller than needed (a queue)' : 'empty time nobody needed'],
      ['Green actually used', `g′ = g − waste = ${g} − ${R.waste >= 0 ? f1(R.waste) : '(' + wasteTxt + ')'}`, `<b>${f1(R.used)} s</b>`, ''],
      ['Degree of saturation', `DS = g′ / g = ${f1(R.used)} / ${g}`, `<b>${f2(R.ds)}</b>`, R.ds < 0.75 ? 'light: green to spare' : R.ds <= 1.0 ? 'busy: green well used' : 'over-saturated: needs more green'],
    ];
  }
  const ANS = R => [null, null, R.need, R.waste, R.used, R.ds];

  function renderSteps(R) {
    const Sx = steps(R), ans = ANS(R), ol = $('wbSteps');
    const inStyle = 'width:5.5em;font:inherit;padding:2px 6px;border:1px solid var(--line);border-radius:4px;background:var(--surface);color:var(--fg)';
    ol.innerHTML = Sx.map(([title, expr, val, note], i) => {
      const hidden = mode === 'step' && i >= stepShown;
      let content;
      if (hidden) content = '<span class="muted">…</span>';
      else if (mode === 'quiz' && ans[i] !== null) content = `${expr} = <input class="wbIn" data-i="${i}" inputmode="decimal" aria-label="${title}" style="${inStyle}"> <span class="wbFb" data-i="${i}"></span>`;
      else content = `${expr} = ${val}`;
      const nt = note && !hidden && mode !== 'quiz' ? ` <span class="muted" style="font-size:.85rem">· ${note}</span>` : '';
      return `<li style="margin:.35rem 0"><b>${title}</b><br><span style="font-family:var(--mono);font-size:.93rem">${content}</span>${nt}</li>`;
    }).join('');
    $('wbNext').hidden = mode !== 'step'; $('wbCheck').hidden = mode !== 'quiz';
    $('wbNext').disabled = stepShown >= 6;
  }
  function gauge(R) {
    const pct = Math.max(0, Math.min(1.4, R.ds)) / 1.4 * 100;
    $('wbFill').style.width = pct + '%';
    $('wbFill').style.background = R.ds < 0.75 ? 'var(--go)' : R.ds <= 1.0 ? 'var(--amber)' : 'var(--stop)';
    $('wbDS').textContent = mode === 'quiz' ? '?' : f2(R.ds);
  }
  function render() { const R = calc(); draw(R); renderSteps(R); gauge(R); }

  // ---------- controls
  function syncOut() {
    $('wbGo').textContent = g + ' s'; $('wbOcco').textContent = f2(occ) + ' s'; $('wbTo').textContent = f2(t) + ' s';
    $('wbNo').textContent = cars.length + ' cars';
  }
  function clampAll() {
    cars = cars.map(a => Math.max(0, Math.min(g - occ, a))).sort((a, b) => a - b);
    for (let i = 1; i < cars.length; i++) if (cars[i] < cars[i - 1] + occ) cars[i] = cars[i - 1] + occ;
    cars = cars.filter(a => a + occ <= g + 1e-6);
  }
  $('wbG').addEventListener('input', e => { g = +e.target.value; clampAll(); syncOut(); render(); });
  $('wbOcc').addEventListener('input', e => { occ = +e.target.value; clampAll(); syncOut(); render(); });
  $('wbT').addEventListener('input', e => { t = +e.target.value; syncOut(); render(); });
  $('wbAdd').addEventListener('click', () => {
    const gs = gapsOf().filter(([a, b]) => b - a >= occ);
    if (!gs.length) return;
    const [a, b] = gs.reduce((m, x) => (x[1] - x[0] > m[1] - m[0] ? x : m));
    cars.push((a + b - occ) / 2); clampAll(); syncOut(); render();
  });
  $('wbDel').addEventListener('click', () => { if (cars.length) { cars.pop(); syncOut(); render(); } });
  $('wbSpread').addEventListener('click', () => { spread(cars.length); syncOut(); render(); });
  document.querySelectorAll('#wbPre button').forEach(b => b.addEventListener('click', () => load(b.dataset.p)));
  document.querySelectorAll('#wbMode button').forEach(b => b.addEventListener('click', () => {
    mode = b.dataset.m; stepShown = mode === 'step' ? 1 : 6;
    document.querySelectorAll('#wbMode button').forEach(x => x.setAttribute('aria-pressed', x === b));
    render();
  }));
  $('wbNext').addEventListener('click', () => { stepShown = Math.min(6, stepShown + 1); render(); });
  $('wbCheck').addEventListener('click', () => {
    const R = calc(), ans = ANS(R);
    document.querySelectorAll('.wbIn').forEach(inp => {
      const i = +inp.dataset.i, v = parseFloat(inp.value.replace(',', '.').replace('−', '-')), want = ans[i];
      const tol = i === 5 ? 0.02 : 0.15, ok = isFinite(v) && Math.abs(v - want) <= tol;
      const fb = document.querySelector(`.wbFb[data-i="${i}"]`);
      fb.textContent = ok ? '✓' : `✗ (${i === 5 ? f2(want) : f1(want)})`;
      fb.style.color = ok ? 'var(--go)' : 'var(--stop)'; fb.style.fontWeight = 700;
    });
    $('wbDS').textContent = f2(R.ds);
  });

  // ---------- pointer: click empty = add car, drag car = move, double-click car = remove
  const hit = x => { const s = S(x); return cars.findIndex(a => s >= a - 0.15 && s <= a + occ + 0.15); };
  cv.addEventListener('pointerdown', e => {
    const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    if (y < BAR_Y - 6 || y > BAR_Y + BAR_H + 6) return;
    const i = hit(x);
    if (i >= 0) { drag = { i, dx: S(x) - cars[i], moved: false }; cv.setPointerCapture(e.pointerId); render(); return; }
    const s = Math.max(0, Math.min(g - occ, S(x) - occ / 2));
    if (cars.every(a => s + occ <= a || s >= a + occ)) { cars.push(s); cars.sort((a, b) => a - b); syncOut(); render(); }
  });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const r = cv.getBoundingClientRect(), s = S(e.clientX - r.left) - drag.dx;
    const others = cars.filter((_, j) => j !== drag.i);
    let lo = 0, hi = g - occ; const me = cars[drag.i];
    others.forEach(a => { if (a + occ <= me + 1e-6) lo = Math.max(lo, a + occ); if (a >= me + occ - 1e-6) hi = Math.min(hi, a - occ); });
    cars[drag.i] = Math.max(lo, Math.min(hi, s)); drag.moved = true; render();
  });
  const end = () => { if (drag) { drag = null; cars.sort((a, b) => a - b); render(); } };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
  cv.addEventListener('dblclick', e => {
    const r = cv.getBoundingClientRect(), i = hit(e.clientX - r.left);
    if (i >= 0) { cars.splice(i, 1); syncOut(); render(); }
  });
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(render, 120); });
  addEventListener('themechange', render);
  load('slide');
})();
