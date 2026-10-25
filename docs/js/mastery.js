(function () {
  const $ = id => document.getElementById(id);
  const S = SCATS;
  const bind = (id, fmt, fn) => { const el = $(id), out = $(id + 'o'); const f = () => { out.textContent = fmt(+el.value); fn && fn(); }; el.addEventListener('input', f); return f; };
  const redraws = [];

  // ---------- CV sampling ----------
  function cvDraw() {
    const p = +$('cvP').value, n = +$('cvN').value, g = 40, trueDs = n * 2 / g, rand = S.rng(9);
    const est = []; let zero = 0;
    for (let k = 0; k < 2000; k++) { let c = 0; for (let i = 0; i < n; i++) if (rand() < p) c++; if (!c) zero++; est.push(c / p * 2 / g); }
    const mean = est.reduce((a, b) => a + b, 0) / est.length, sd = Math.sqrt(est.reduce((a, b) => a + (b - mean) ** 2, 0) / est.length);
    $('cvTrue').textContent = trueDs.toFixed(2); $('cvSd').textContent = sd.toFixed(2); $('cvZero').textContent = Math.round(100 * zero / 2000) + ' %';
    const cv = $('cvCv'), r = cv.getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d;
    const c = cv.getContext('2d'); c.setTransform(d, 0, 0, d, 0, 0); c.clearRect(0, 0, r.width, r.height);
    const bins = 40, max = 2.4, h = new Array(bins).fill(0); est.forEach(e => h[Math.min(bins - 1, Math.floor(e / max * bins))]++);
    const top = Math.max(...h), L = 30, W = r.width - L - 10, H = r.height - 28;
    c.fillStyle = tok('--phase-b'); h.forEach((v, i) => c.fillRect(L + i * W / bins + 1, 8 + H - H * v / top, W / bins - 2, H * v / top));
    c.fillStyle = tok('--stop'); c.fillRect(L + trueDs / max * W - 1, 4, 3, H + 4);
    c.fillStyle = tok('--muted'); c.font = '12px Barlow, sans-serif';
    for (let x = 0; x <= max; x += 0.4) c.fillText(x.toFixed(1), L + x / max * W - 8, r.height - 6);
    c.fillText('estimated DS (red line = true DS)', L + 4, 18);
  }
  [bind('cvP', v => Math.round(v * 100) + ' %', cvDraw), bind('cvN', v => v, cvDraw)].forEach(f => f());
  redraws.push(cvDraw);

  // ---------- RL toy ----------
  const SPL = [.55, .65, .45, .75], AV = 50;
  function episode(policy, rand, learn) {
    let qa = 4, qb = 4, tot = 0, prev = null, ds = { A: .5, B: .5 }, served = { A: 0, B: 0 };
    const voter = new S.Voter(0, 3, 2); let plan = 0;
    for (let k = 0; k < 60; k++) {
      const ph = 2 * Math.PI * k / 60, la = (800 + 450 * Math.sin(ph)) / 60, lb = (560 - 300 * Math.sin(ph)) / 60;
      const st = Math.min(3, Math.floor(qa / 6)) * 4 + Math.min(3, Math.floor(qb / 6));
      let a;
      if (policy === 'fixed') a = 0;
      else if (policy === 'ds') { const gNow = { A: AV * SPL[plan], B: AV * (1 - SPL[plan]) }; const sel = S.selectSplit(ds, gNow, SPL.map(s => ({ A: AV * s, B: AV * (1 - s) }))); plan = voter.vote(sel.best); a = plan; }
      else a = policy.act(st, rand);
      const gA = AV * SPL[a], gB = AV - gA;
      qa += S.poisson(rand, la); qb += S.poisson(rand, lb);
      const sa = Math.min(qa, Math.floor(gA / 2)), sb = Math.min(qb, Math.floor(gB / 2));
      ds = { A: Math.min(1.2, sa * 2 / gA + (qa > sa ? .1 : 0)), B: Math.min(1.2, sb * 2 / gB + (qb > sb ? .1 : 0)) };
      qa -= sa; qb -= sb; tot += qa + qb;
      if (learn && prev) policy.update(prev[0], prev[1], -(qa + qb) / 10, Math.min(3, Math.floor(qa / 6)) * 4 + Math.min(3, Math.floor(qb / 6)));
      prev = [st, a];
    }
    return tot / 60;
  }
  function Agent() { this.Q = Array.from({ length: 16 }, () => [0, 0, 0, 0]); this.eps = .3; }
  Agent.prototype.act = function (s, rand) { if (rand() < this.eps) return Math.floor(rand() * 4); const q = this.Q[s]; return q.indexOf(Math.max(...q)); };
  Agent.prototype.update = function (s, a, r, s2) { this.Q[s][a] += 0.1 * (r + 0.9 * Math.max(...this.Q[s2]) - this.Q[s][a]); };
  let agent, curve, baseDs, baseFix, rlRunning = false;
  function rlReset() {
    agent = new Agent(); curve = [];
    const r1 = S.rng(77), r2 = S.rng(77); baseDs = 0; baseFix = 0;
    for (let i = 0; i < 20; i++) { baseDs += episode('ds', r1) / 20; baseFix += episode('fixed', r2) / 20; }
    $('rlEp').textContent = 0; $('rlQ').textContent = '–'; $('rlDs').textContent = baseDs.toFixed(1); rlDraw();
  }
  function rlDraw() {
    const sm = curve.map((_, i) => { const w = curve.slice(Math.max(0, i - 19), i + 1); return w.reduce((a, b) => a + b, 0) / w.length; });
    const n = Math.max(sm.length, 2);
    lineChart($('rlCv'), [{ color: '--fg', data: sm }, { color: '--amber', data: new Array(n).fill(baseDs) }, { color: '--muted', data: new Array(n).fill(baseFix), width: 1 }],
      { ymin: 0, xlabel: 'training episodes (20-episode moving average)' });
  }
  $('rlGo').addEventListener('click', () => {
    if (rlRunning) return; rlRunning = true; $('rlGo').disabled = true;
    const rand = S.rng(1000 + curve.length); let done = 0;
    const chunk = () => {
      for (let i = 0; i < 10; i++) { agent.eps = Math.max(.02, .3 * (1 - curve.length / 300)); curve.push(episode(agent, rand, true)); done++; }
      $('rlEp').textContent = curve.length; const last = curve.slice(-20); $('rlQ').textContent = (last.reduce((a, b) => a + b, 0) / last.length).toFixed(1);
      rlDraw(); if (done < 300) setTimeout(chunk, 16); else { rlRunning = false; $('rlGo').disabled = false; $('rlGo').textContent = 'Train 300 more'; }
    };
    chunk();
  });
  $('rlReset').addEventListener('click', () => { if (!rlRunning) { rlReset(); $('rlGo').textContent = 'Train 300 episodes'; } });
  rlReset(); redraws.push(rlDraw);

  // ---------- pressure vs DS ----------
  function mpDraw() {
    const qa = +$('mpQa').value, da = +$('mpDa').value, qb = +$('mpQb').value, db = +$('mpDb').value, beta = +$('mpBeta').value, avail = 70;
    const gNow = { A: 35, B: 35 }, ds = { A: .95, B: .6 };
    const plans = [.5, .6, .4, .7].map(s => ({ A: avail * s, B: avail * (1 - s) }));
    const dsPlan = plans[S.selectSplit(ds, gNow, plans).best];
    const pa = Math.max(0, qa - .5 * da) + .5, pb = Math.max(0, qb - .5 * db) + .5;
    const mp = { A: avail * pa / (pa + pb), B: avail * pb / (pa + pb) };
    const hy = { A: (1 - beta) * dsPlan.A + beta * mp.A, B: (1 - beta) * dsPlan.B + beta * mp.B };
    $('mpT').innerHTML = [['SCATS DS split', dsPlan], ['Pressure split', mp], [`Hybrid β = ${beta.toFixed(2)}`, hy]]
      .map(([n, g]) => `<tr><td>${n}</td><td class="num">${g.A.toFixed(0)} s</td><td class="num">${g.B.toFixed(0)} s</td></tr>`).join('');
  }
  ['mpQa', 'mpDa', 'mpQb', 'mpDb'].forEach(id => bind(id, v => v + ' veh', mpDraw)());
  bind('mpBeta', v => v.toFixed(2), mpDraw)();

  // ---------- faults ----------
  let ft = 'ok', fh = 'none';
  function ftDraw() {
    const g = 30, h = 1.55, occ = .45;
    const ds1 = S.degreeOfSaturation(g, g - 7 * occ, 7, h);
    const ds2 = ft === 'ok' ? S.degreeOfSaturation(g, g - 13 * occ, 13, h) : ft === 'off' ? S.degreeOfSaturation(g, g, 0, h) : S.degreeOfSaturation(g, 0, 0, h);
    const alarmed = ft !== 'ok';
    let phase, gap;
    if (!alarmed || fh === 'none') {
      phase = Math.max(ds1, ds2);
      gap = ft === 'on' ? 'never gaps out: runs to max green' : ft === 'off' ? 'gaps out early on loop 1 while lane 2 still queues' : 'normal';
    } else if (fh === 'exclude') { phase = ds1; gap = 'loop 1 decides alone; lane 2 demand unseen'; }
    else { phase = Math.max(ds1, 0.86); gap = 'loop 1 decides; DS uses lane 2 history (0.86)'; }
    $('ftL1').textContent = ds1.toFixed(2); $('ftL2').textContent = ds2.toFixed(2) + (alarmed ? ' (alarm)' : '');
    $('ftPh').textContent = phase.toFixed(2) + (Math.abs(phase - 0.87) > 0.1 ? ' (wrong)' : ''); $('ftGo').textContent = gap;
  }
  const seg = (id, attr, set) => document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(`#${id} button`).forEach(x => x.setAttribute('aria-pressed', x === b)); set(b.dataset[attr]); ftDraw(); }));
  seg('ftType', 'f', v => ft = v); seg('ftHand', 'h', v => fh = v); ftDraw();

  // ---------- SUMO result tables ----------
  const R = window.RESULTS || {};
  const table = (rows, cols) => !rows ? '<p class="muted">Run the script to generate results.</p>' : `<table class="data"><thead><tr>${cols.map(c => `<th>${c[1]}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${r[c[0]] ?? '–'}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const cols = [['label', 'Run'], ['avg_delay', 'Mean delay (s)'], ['stops_per_veh', 'Stops / veh'], ['bus_avg_delay', 'Bus delay (s)']];
  $('cvTable').innerHTML = table(R.cv, cols);
  $('rlTable').innerHTML = table(R.rl, cols);
  $('mpTable').innerHTML = table(R.maxpressure, cols);
  $('ftTable').innerHTML = table(R.faults, cols.concat([['failed_loops', 'Failed loops']]));
  $('spTable').innerHTML = table(R.spat, [['predictor', 'Predictor'], ['mae_s', 'Mean absolute error (s)']]);

  Quiz($('quizM'), QUIZ.mastery, 'mastery');
  addEventListener('themechange', () => redraws.forEach(f => f()));
  addEventListener('resize', () => redraws.forEach(f => f()));
})();
