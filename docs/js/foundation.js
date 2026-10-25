(function () {
  const $ = id => document.getElementById(id);
  const S = SCATS;
  const bind = (id, fmt, fn) => { const el = $(id), out = $(id + 'o'); const f = () => { out.textContent = fmt(+el.value); fn && fn(); }; el.addEventListener('input', f); return f; };

  // ---------- cycle builder ----------
  function drawCycle() {
    const C = +$('cycC').value, a = +$('cycS').value / 100, I = +$('cycI').value;
    const gr = S.allocateGreens(C, { A: a, B: 1 - a }, { A: I, B: I }, { A: 6, B: 6 });
    const cv = $('cycCv'), r = cv.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    cv.width = r.width * dpr; cv.height = r.height * dpr; const c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, r.width, r.height);
    const x0 = 4, w = r.width - 8, sc = w / C; let x = x0;
    const seg = (len, col, label) => { c.fillStyle = tok(col); c.fillRect(x, 30, len * sc, 40); if (label && len * sc > 40) { c.fillStyle = tok('--fg'); c.font = '600 14px Barlow, sans-serif'; c.fillText(label, x + 6, 55); } x += len * sc; };
    seg(gr.A, '--phase-a', `A green ${gr.A.toFixed(0)} s`); seg(3, '--amber'); seg(I - 3, '--stop');
    seg(gr.B, '--phase-b', `B green ${gr.B.toFixed(0)} s`); seg(3, '--amber'); seg(I - 3, '--stop');
    c.fillStyle = tok('--muted'); c.font = '13px Barlow, sans-serif';
    for (let t = 0; t <= C; t += 10) { const xx = x0 + t * sc; c.fillRect(xx, 74, 1, 6); if (t % 20 === 0) c.fillText(t + ' s', xx - 8, 94); }
    c.fillText('one cycle', x0, 20);
    $('cycF').textContent = `C = gA + gB + 2 × intergreen\n${C} = ${gr.A.toFixed(1)} + ${gr.B.toFixed(1)} + 2 × ${I}\nlost share of cycle = ${(200 * I / C).toFixed(0)} %`;
  }
  [bind('cycC', v => v + ' s', drawCycle), bind('cycS', v => v + ' %', drawCycle), bind('cycI', v => v + ' s', drawCycle)].forEach(f => f());

  // ---------- DS calculator ----------
  let seed = 3;
  function drawDs() {
    const g = +$('dsGr').value, q = +$('dsQ').value, h = +$('dsH').value;
    const rand = S.rng(seed), occ = 0.45, head = 2.0;
    // generate arrivals during green; vehicles queue behind each other at 2 s headway; first crosses after 2 s startup
    const cross = []; let tNext = 2;
    // initial queue from red: proportional to flow
    const queued = Math.round(q / 3600 * 30 * (0.6 + 0.8 * rand()));
    let arrivals = []; for (let i = 0; i < queued; i++) arrivals.push(0);
    let t = 0; while (t < g) { t += -Math.log(1 - rand()) * 3600 / q; if (t < g) arrivals.push(t); }
    arrivals.forEach(a => { const tc = Math.max(a + 0.5, tNext); if (tc + occ <= g) { cross.push(tc); tNext = tc + head; } });
    const n = cross.length, T = g - n * occ;
    const ds = S.degreeOfSaturation(g, T, n, h), used = S.effectiveGreen(g, T, n, h);
    $('dsT').textContent = T.toFixed(1); $('dsN').textContent = n; $('dsW').textContent = (T - n * h).toFixed(1);
    $('dsG').textContent = used.toFixed(1); $('dsV').textContent = ds.toFixed(2); $('dsK').textContent = S.vk(ds, g, 1800).toFixed(1);
    const cv = $('dsCv'), r = cv.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    cv.width = r.width * dpr; cv.height = r.height * dpr; const c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, r.width, r.height);
    const x0 = 4, w = r.width - 8, sc = w / g;
    c.fillStyle = tok('--sunk'); c.fillRect(x0, 24, w, 40);
    c.fillStyle = tok('--fg'); cross.forEach(tc => c.fillRect(x0 + tc * sc, 24, Math.max(1.5, occ * sc), 40));
    c.fillStyle = tok('--muted'); c.font = '13px Barlow, sans-serif'; c.fillText('green starts', x0, 16); c.textAlign = 'right'; c.fillText('green ends', x0 + w, 16); c.textAlign = 'left';
    for (let s = 0; s <= g; s += 5) c.fillRect(x0 + s * sc, 66, 1, 5);
    c.fillText(`${n} vehicles · DS ${ds.toFixed(2)}`, x0, 92);
  }
  [bind('dsGr', v => v + ' s', drawDs), bind('dsQ', v => v + ' veh/h', drawDs), bind('dsH', v => v.toFixed(2) + ' s', drawDs)].forEach(f => f());
  $('dsNew').addEventListener('click', () => { seed++; drawDs(); });

  // ---------- live intersection ----------
  const sim = new IntersectionSim($('liveCv'), { mode: 'scats', speed: 6 });
  const setD = () => sim.setDemand({ W: +$('lvMain').value, E: +$('lvMain').value * 0.92, N: +$('lvSide').value, S: +$('lvSide').value * 0.92 });
  [bind('lvMain', v => v + ' veh/h', setD), bind('lvSide', v => v + ' veh/h', setD), bind('lvSpd', v => v + '×', () => sim.setSpeed(+$('lvSpd').value))].forEach(f => f());
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-mode]').forEach(x => x.setAttribute('aria-pressed', x === b));
    sim.setMode(b.dataset.mode); setD(); chart();
  }));
  let running = true;
  $('lvPause').addEventListener('click', () => { running = !running; running ? sim.start() : sim.stop(); $('lvPause').textContent = running ? 'Pause' : 'Resume'; });
  $('lvReset').addEventListener('click', () => { sim.reset(); setD(); chart(); });
  function chart() {
    const H = sim.history.slice(-40);
    lineChart($('lvChart'), [
      { color: '--fg', data: H.map(r => r.C / 100), step: true },
      { color: '--go', data: H.map(r => r.ds.A) },
      { color: '--phase-b', data: H.map(r => r.ds.B) },
    ], { ymin: 0, ymax: 1.5, hlines: [{ y: 0.9, color: '--amber' }], xlabel: 'last 40 cycles' });
  }
  sim.on(chart);
  setInterval(() => { const s = sim.stats(); $('lvC').textContent = s.C.toFixed(0); $('lvP').textContent = sim.opts.mode === 'scats' ? 'SP' + (s.plan + 1) : 'SP1 fixed';
    $('lvDs').textContent = `${s.ds.A.toFixed(2)} / ${s.ds.B.toFixed(2)}`; $('lvD').textContent = s.avgDelay.toFixed(1); }, 500);
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) sim.start(); else { for (let i = 0; i < 600; i++) sim.tick(); sim.draw(); running = false; $('lvPause').textContent = 'Resume'; }
  chart();
  addEventListener('themechange', () => { sim.draw(); chart(); drawCycle(); drawDs(); });
  addEventListener('resize', () => { chart(); drawCycle(); drawDs(); });

  // ---------- race ----------
  $('raceBtn').addEventListener('click', () => {
    const rows = [];
    for (const mode of ['fixed', 'actuated', 'scats']) {
      const cv = document.createElement('canvas');
      const s = new IntersectionSim(cv, { mode, seed: 11, demand: { W: 450, E: 420, N: 220, S: 200 } });
      for (let t = 0; t < 3600; t++) {
        const peak = t >= 1200 && t < 2400;
        s.setDemand(peak ? { W: 820, E: 760, N: 420, S: 380 } : { W: 450, E: 420, N: 220, S: 200 });
        s.tick();
      }
      const st = s.stats(); rows.push([mode, st.avgDelay, st.avgQueue, st.served, s.history.length]);
    }
    const best = Math.min(...rows.map(r => r[1]));
    $('raceT').tBodies[0].innerHTML = rows.map(r => `<tr class="${r[1] === best ? 'best' : ''}"><td>${r[0]}</td><td>${r[1].toFixed(1)}</td><td>${r[2].toFixed(1)}</td><td>${r[3]}</td><td>${r[4]}</td></tr>`).join('');
  });

  // ---------- webster ----------
  function web() {
    const L = +$('wL').value, a = +$('wA').value, b = +$('wB').value, Y = a + b, C = S.webster(L, Y);
    $('wY').textContent = Y.toFixed(2);
    if (!isFinite(C)) { $('wC').textContent = 'over capacity'; $('wS').textContent = '–'; return; }
    const eff = C - L; $('wC').textContent = C.toFixed(0); $('wS').textContent = `${(eff * a / Y).toFixed(0)} / ${(eff * b / Y).toFixed(0)}`;
  }
  [bind('wL', v => v + ' s', web), bind('wA', v => v.toFixed(2), web), bind('wB', v => v.toFixed(2), web)].forEach(f => f());

  Quiz($('quizF'), QUIZ.foundation, 'foundation');
})();
