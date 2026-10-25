(function () {
  const $ = id => document.getElementById(id);
  const S = SCATS;
  const bind = (id, fmt, fn) => { const el = $(id), out = $(id + 'o'); const f = () => { out.textContent = fmt(+el.value); fn && fn(); }; el.addEventListener('input', f); return f; };
  const prep = cv => { const r = cv.getBoundingClientRect(), d = devicePixelRatio || 1; cv.width = r.width * d; cv.height = r.height * d; const c = cv.getContext('2d'); c.setTransform(d, 0, 0, d, 0, 0); c.clearRect(0, 0, r.width, r.height); c.font = '13px Barlow, sans-serif'; return [c, r.width, r.height]; };
  const redraws = [];

  // ---------------- cycle length ----------------
  let Cs = [60], DSs = [null], playTimer = null;
  const params = () => Object.assign({}, S.cycleDefaults, { target: +$('clT').value, lmax: +$('clMax').value, lstretch: +$('clStr').value });
  function clDraw() {
    const p = params();
    lineChart($('clCv'), [
      { color: '--fg', data: Cs, step: true, width: 2.5 },
      { color: '--go', data: DSs.map(d => d == null ? null : d * 100) },
      { color: '--muted', data: Cs.map(() => p.lmin), width: 1 },
      { color: '--muted', data: Cs.map(() => p.lmax), width: 1 },
    ], { ymin: 0, ymax: 200, ticks: 4, xlabel: 'cycles →' });
    const C = Cs[Cs.length - 1], ds = DSs[DSs.length - 1];
    if (ds != null) {
      const prevC = Cs[Cs.length - 2], desired = prevC * ds / p.target;
      $('clF').textContent = `desired = ${prevC.toFixed(1)} × ${ds.toFixed(2)} / ${p.target.toFixed(2)} = ${desired.toFixed(1)} s\nstep    = ${(C - prevC).toFixed(1)} s   (limit +${ds >= 1 ? 9 : 6} / −6)\nC_next  = ${C.toFixed(1)} s`;
    } else $('clF').textContent = `C = ${C} s. Press "Step one cycle".`;
    const [c, W] = prep($('clBar'));
    const gr = S.allocateGreens(C, { A: .5, B: .15, C: .35 }, { A: 5, B: 5, C: 5 }, { A: 10, B: 5, C: 7 }, 'A', p.lstretch);
    let x = 4; const sc = (W - 8) / p.lmax;
    [['A', '--phase-a'], ['B', '--phase-c'], ['C', '--phase-b']].forEach(([ph, col]) => {
      c.fillStyle = tok(col); c.fillRect(x, 8, gr[ph] * sc, 26); c.fillStyle = tok('--fg');
      if (gr[ph] * sc > 34) c.fillText(`${ph} ${gr[ph].toFixed(0)}s`, x + 4, 26);
      x += gr[ph] * sc; c.fillStyle = tok('--amber'); c.fillRect(x, 8, 5 * sc, 26); x += 5 * sc;
    });
    c.fillStyle = tok('--muted'); c.fillText(C > p.lstretch ? `above stretch (${p.lstretch} s): extra ${(C - p.lstretch).toFixed(0)} s goes to phase A` : 'below stretch: greens shared by the split plan', 4, 50);
  }
  function clStep(ds) { const C = Cs[Cs.length - 1]; Cs.push(S.nextCycle(C, ds, params())); DSs.push(ds); if (Cs.length > 60) { Cs.shift(); DSs.shift(); } clDraw(); }
  [bind('clDs', v => v.toFixed(2)), bind('clT', v => v.toFixed(2), clDraw), bind('clMax', v => v + ' s', clDraw), bind('clStr', v => v + ' s', clDraw)].forEach(f => f());
  $('clStep').addEventListener('click', () => clStep(+$('clDs').value));
  $('clReset').addEventListener('click', () => { clearInterval(playTimer); playTimer = null; $('clPlay').textContent = 'Play rush hour'; Cs = [60]; DSs = [null]; clDraw(); });
  $('clPlay').addEventListener('click', () => {
    if (playTimer) { clearInterval(playTimer); playTimer = null; $('clPlay').textContent = 'Play rush hour'; return; }
    Cs = [60]; DSs = [null]; let k = 0; const rand = S.rng(5); $('clPlay').textContent = 'Stop';
    playTimer = setInterval(() => {
      // demand (as DS the CI would show at a 60 s cycle) rises and falls; DS seen depends on the cycle in force
      const demand = 0.45 + 0.75 * Math.exp(-((k - 24) ** 2) / 90) + (rand() - .5) * .08;
      const C = Cs[Cs.length - 1]; const ds = Math.min(1.3, demand * 60 / C * (1 + 12 / C) / (1 + 12 / 60));
      $('clDs').value = ds.toFixed(2); $('clDso').textContent = ds.toFixed(2);
      clStep(ds); if (++k > 50) { clearInterval(playTimer); playTimer = null; $('clPlay').textContent = 'Play rush hour'; }
    }, 180);
  });
  clDraw(); redraws.push(clDraw);

  // ---------------- split plans ----------------
  const PLANS = [{ A: .50, B: .15, C: .35 }, { A: .60, B: .12, C: .28 }, { A: .45, B: .20, C: .35 }, { A: .40, B: .12, C: .48 }];
  const INT = { A: 5, B: 5, C: 5 }, MIN = { A: 10, B: 5, C: 7 };
  const greens = PLANS.map(p => S.allocateGreens(90, p, INT, MIN));
  let voter = new S.Voter(0, 3, 2);
  function spCompute() {
    const ds = { A: +$('spA').value, B: +$('spB').value, C: +$('spC').value };
    const gNow = greens[voter.current];
    const sel = S.selectSplit(ds, gNow, greens);
    $('spT').tBodies[0].innerHTML = greens.map((g, i) => {
      const pr = S.predictPlanDs(ds, gNow, g);
      return `<tr class="${i === sel.best ? 'best' : ''}"><td>SP${i + 1}${i === voter.current ? ' (in service)' : ''}</td><td>${Object.values(PLANS[i]).map(v => Math.round(v * 100)).join(' / ')}</td>
        <td>${['A', 'B', 'C'].map(p => g[p].toFixed(0)).join(' / ')}</td><td>${['A', 'B', 'C'].map(p => pr[p].toFixed(2)).join(' / ')}</td><td><strong>${sel.scores[i].toFixed(2)}</strong></td></tr>`;
    }).join('');
    $('spWin').textContent = 'SP' + (sel.best + 1);
    return sel.best;
  }
  ['spA', 'spB', 'spC'].forEach(id => bind(id, v => v.toFixed(2), spCompute)());
  $('spVote').addEventListener('click', () => {
    const best = spCompute(); voter.vote(best);
    $('spCur').textContent = 'SP' + (voter.current + 1); $('spHist').textContent = voter.history.map(v => 'SP' + (v + 1)).join(', ');
    spCompute();
  });
  $('spReset').addEventListener('click', () => { voter = new S.Voter(0, 3, 2); $('spCur').textContent = 'SP1'; $('spHist').textContent = '–'; spCompute(); });
  spCompute();

  // ---------------- time-space ----------------
  let tsPlan = 0, offVoter = new S.Voter(0, 5, 4);
  function band(C, xs, offs, gA, v, dir) {
    // longest continuous set of entry times (sampled) that clear every signal without stopping
    const order = dir > 0 ? xs.map((_, i) => i) : xs.map((_, i) => xs.length - 1 - i);
    const first = order[0], ok = [];
    for (let s = 0; s < C; s += 0.25) {
      const t0 = offs[first] + s; if (s > gA) { ok.push(false); continue; }
      let pass = true;
      for (const i of order) { const t = t0 + Math.abs(xs[i] - xs[first]) / v; const m = (((t - offs[i]) % C) + C) % C; if (m > gA) { pass = false; break; } }
      ok.push(pass);
    }
    let best = 0, run = 0; ok.forEach(o => { run = o ? run + 1 : 0; best = Math.max(best, run); });
    return best * 0.25;
  }
  function tsDraw() {
    const C = +$('tsC').value, sp = +$('tsX').value, v = +$('tsV').value;
    const xs = [0, sp, 2 * sp, 3 * sp], offs = S.offsetsForPlan(tsPlan, xs, 0, v, C), gA = 0.55 * C;
    const [c, W, H] = prep($('tsCv'));
    const L = 44, R = 10, T = 14, B = 26, span = 3 * C;
    const X = t => L + (W - L - R) * t / span, Y = x => H - B - (H - T - B) * x / xs[3];
    c.fillStyle = tok('--muted');
    xs.forEach((x, i) => {
      c.fillText('J' + (i + 1), 6, Y(x) + 4);
      for (let k = -1; k < 4; k++) {
        const s = offs[i] + k * C;
        c.fillStyle = tok('--stop'); c.fillRect(X(Math.max(0, s - (C - gA))), Y(x) - 3, Math.max(0, X(Math.min(span, s)) - X(Math.max(0, s - (C - gA)))), 6);
        c.fillStyle = tok('--go'); const a = Math.max(0, s), b = Math.min(span, s + gA); if (b > a) c.fillRect(X(a), Y(x) - 3, X(b) - X(a), 6);
      }
    });
    const traj = (dir, col) => {
      c.strokeStyle = tok(col); c.lineWidth = 1.2; const start = dir > 0 ? 0 : 3;
      for (let t0 = offs[start] - C; t0 < span; t0 += 6) {
        let t = t0, i = start; c.beginPath(); c.moveTo(X(t), Y(xs[i]));
        while (true) {
          const m = (((t - offs[i]) % C) + C) % C;
          if (m > gA) { const wait = C - m; c.lineTo(X(t + wait), Y(xs[i])); t += wait; }
          const ni = i + dir; if (ni < 0 || ni > 3) break;
          t += sp / v; c.lineTo(X(t), Y(xs[ni])); i = ni; if (t > span) break;
        }
        c.stroke();
      }
    };
    c.save(); c.beginPath(); c.rect(L, 0, W - L - R, H - B + 4); c.clip();
    traj(1, '--fg'); c.globalAlpha = 0.55; traj(-1, '--phase-b'); c.restore();
    c.fillStyle = tok('--muted'); for (let k = 0; k <= 3; k++) c.fillText(`${k * C} s`, X(k * C) - 8, H - 8);
    c.fillText('distance ↑', L + 4, T - 2);
    $('tsBe').textContent = band(C, xs, offs, gA, v, 1).toFixed(0); $('tsBw').textContent = band(C, xs, offs, gA, v, -1).toFixed(0);
  }
  document.querySelectorAll('#tsPlans button').forEach(b => b.addEventListener('click', () => { tsPlan = +b.dataset.p; setPlanBtn(); tsDraw(); }));
  const setPlanBtn = () => document.querySelectorAll('#tsPlans button').forEach(x => x.setAttribute('aria-pressed', +x.dataset.p === tsPlan));
  [bind('tsC', v => v + ' s', tsDraw), bind('tsX', v => v + ' m', tsDraw), bind('tsV', v => v + ' m/s', tsDraw), bind('tsE', v => v), bind('tsW', v => v)].forEach(f => f());
  $('tsAuto').addEventListener('click', () => {
    const C = +$('tsC').value, choice = S.selectOffsetPlan(+$('tsE').value, +$('tsW').value, +$('tsX').value / +$('tsV').value, C, 3, 1.3);
    offVoter.current = tsPlan; tsPlan = offVoter.vote(choice); setPlanBtn(); tsDraw();
    $('tsVoteTxt').textContent = `wants OP${choice + 1}; votes ${offVoter.history.map(v => v + 1).join(',')}; in service OP${tsPlan + 1}`;
  });
  tsDraw(); redraws.push(tsDraw);

  // ---------------- marriage ----------------
  function mgDraw() {
    const rand = S.rng(21), n = 96, vk = [];
    for (let k = 0; k < n; k++) vk.push(Math.max(0, 7 + 45 * Math.exp(-((k - 26) ** 2) / 70) + 38 * Math.exp(-((k - 70) ** 2) / 60) + (rand() - .5) * 16));
    const m = new S.Marriage({ marry: +$('mgM').value, divorce: +$('mgD').value, votes: +$('mgV').value, gap: 999 });
    const st = vk.map(v => m.vote(v, 60, 60));
    let sw = 0; st.forEach((s, i) => { if (i && s !== st[i - 1]) sw++; });
    $('mgSw').textContent = sw; $('mgPct').textContent = Math.round(100 * st.filter(Boolean).length / n) + ' %';
    const cv = $('mgCv'); lineChart(cv, [{ color: '--fg', data: vk }], { ymin: 0, ymax: 70, hlines: [{ y: +$('mgM').value, color: '--go' }, { y: +$('mgD').value, color: '--stop' }], xlabel: 'cycles through the day →' });
    const c = cv.getContext('2d'), W = cv.getBoundingClientRect().width, Hh = cv.getBoundingClientRect().height;
    c.globalAlpha = 0.35; c.fillStyle = tok('--phase-a');
    st.forEach((s, i) => { if (s) { const x0 = 40 + (W - 50) * i / (n - 1), x1 = 40 + (W - 50) * (i + 1) / (n - 1); c.fillRect(x0, 10, x1 - x0 + 0.5, Hh - 34); } });
    c.globalAlpha = 1;
  }
  [bind('mgM', v => v, mgDraw), bind('mgD', v => v, mgDraw), bind('mgV', v => v, mgDraw)].forEach(f => f());
  redraws.push(mgDraw);

  // ---------------- gap-out ----------------
  let goSeed = 4;
  function goDraw() {
    const q = +$('goQ').value, gap = +$('goG').value, gmin = +$('goMin').value, gmax = 40, rand = S.rng(goSeed);
    const arr = []; const queued = Math.round(q / 3600 * 35); for (let i = 0; i < queued; i++) arr.push(0);
    let t = 0; while (t < gmax) { t += -Math.log(1 - rand()) * 3600 / q; arr.push(t); }
    const cross = []; let nx = 2; arr.forEach(a => { const tc = Math.max(a, nx); if (tc < gmax) { cross.push(tc); nx = tc + 2; } });
    let end = gmax, why = 'max green', timer = [], last = 0, ci = 0;
    for (let s = 0; s <= gmax; s += 0.1) {
      while (ci < cross.length && cross[ci] <= s) { last = cross[ci]; ci++; }
      const gt = s - last; timer.push([s, gt]);
      if (s >= gmin && gt >= gap) { end = s; why = 'gap-out'; break; }
    }
    $('goEnd').textContent = end.toFixed(1); $('goWhy').textContent = why;
    const [c, W, H] = prep($('goCv')); const L = 40, R = 10, X = s => L + (W - L - R) * s / gmax, Y = v => H - 26 - (H - 70) * Math.min(v, 8) / 8;
    c.fillStyle = tok('--sunk'); c.fillRect(X(0), 10, X(end) - X(0), 18);
    c.fillStyle = tok('--fg'); cross.filter(x => x <= end).forEach(x => c.fillRect(X(x), 10, 2, 18));
    c.fillStyle = tok('--muted'); c.fillText('vehicles crossing the loop', L, 42);
    c.strokeStyle = tok('--amber'); c.setLineDash([5, 4]); c.beginPath(); c.moveTo(X(0), Y(gap)); c.lineTo(X(gmax), Y(gap)); c.stroke();
    c.strokeStyle = tok('--muted'); c.beginPath(); c.moveTo(X(gmin), 46); c.lineTo(X(gmin), H - 26); c.stroke(); c.setLineDash([]);
    c.strokeStyle = tok('--fg'); c.lineWidth = 2; c.beginPath(); timer.forEach(([s, v], i) => i ? c.lineTo(X(s), Y(v)) : c.moveTo(X(s), Y(v))); c.stroke();
    c.fillStyle = tok('--stop'); c.fillRect(X(end) - 1, 8, 3, H - 34);
    c.fillStyle = tok('--muted'); c.fillText('gap timer', L + 4, Y(gap) - 6); c.fillText('min green', X(gmin) + 4, 60);
    for (let s = 0; s <= gmax; s += 10) c.fillText(s + ' s', X(s) - 6, H - 8);
  }
  [bind('goQ', v => v + ' veh/h', goDraw), bind('goG', v => v.toFixed(1) + ' s', goDraw), bind('goMin', v => `${v} s / 40 s`, goDraw)].forEach(f => f());
  $('goNew').addEventListener('click', () => { goSeed++; goDraw(); });
  redraws.push(goDraw);

  // ---------------- transit priority ----------------
  let ptLevel = 'medium';
  function ptDraw() {
    const ta = +$('ptT').value, gA = 40, I = 5, gB = 30, C = 80, bmin = 10, ext = 10;
    const d0 = ta < gA ? 0 : C - ta;
    let segs = [['A', 0, gA], ['i', gA, gA + I], ['B', gA + I, gA + I + gB], ['i', 75, 80], ['A', 80, 120]], d1 = d0, act = 'waits its turn';
    const cutB = minB => { // shorten or cut phase B so A returns early
      const bEnd = Math.max(ta, gA + I + minB);
      segs = [['A', 0, gA], ['i', gA, gA + I], ['B', gA + I, bEnd], ['i', bEnd, bEnd + I], ['A', bEnd + I, 120]];
      d1 = bEnd + I - ta;
    };
    if (ptLevel !== 'low') {
      if (ta < gA) { act = 'no action needed'; d1 = 0; }
      else if (ptLevel === 'medium' && ta < gA + ext) {
        const e = ta - gA + 3;
        segs = [['A', 0, gA + e], ['i', gA + e, gA + e + I], ['B', gA + e + I, 75], ['i', 75, 80], ['A', 80, 120]]; d1 = 0; act = `extend A by ${e} s`;
      } else if (ta < 75 - (ptLevel === 'medium' ? 0 : 0)) {
        const before = d0; cutB(ptLevel === 'high' ? 5 : bmin);
        if (d1 >= before) { d1 = before; segs = segs; act = 'too late to help'; }
        else act = ptLevel === 'high' ? 'hurry call: cut B' : 'shorten B after its min green';
      } else act = 'already changing to A';
    }
    $('ptD0').textContent = d0.toFixed(0); $('ptD1').textContent = d1.toFixed(0); $('ptX').textContent = act;
    const [c, W, H] = prep($('ptCv')); const L = W < 500 ? 62 : 90, X = t => L + (W - L - 10) * t / 120;
    const row = (y, sg, label) => { c.fillStyle = tok('--fg'); c.fillText(label, 4, y + 15);
      sg.forEach(([k, a, b]) => { c.fillStyle = tok(k === 'A' ? '--phase-a' : k === 'B' ? '--phase-b' : '--amber'); c.fillRect(X(a), y, X(b) - X(a), 22); if (k !== 'i' && X(b) - X(a) > 20) { c.fillStyle = tok('--fg'); c.fillText(k, X(a) + 5, y + 15); } }); };
    row(12, [['A', 0, gA], ['i', gA, gA + I], ['B', gA + I, 75], ['i', 75, 80], ['A', 80, 120]], 'normal');
    row(52, segs, W < 500 ? ptLevel : ptLevel + ' priority');
    c.fillStyle = tok('--stop'); c.fillRect(X(ta) - 1, 4, 3, 76); c.fillText('bus arrives', Math.min(X(ta) + 4, W - 70), 96);
    c.fillStyle = tok('--muted'); for (let s = 0; s <= 100; s += 20) c.fillText(s + ' s', X(s) - 6, H - 6);
  }
  document.querySelectorAll('#ptLv button').forEach(b => b.addEventListener('click', () => { ptLevel = b.dataset.l; document.querySelectorAll('#ptLv button').forEach(x => x.setAttribute('aria-pressed', x === b)); ptDraw(); }));
  bind('ptT', v => v + ' s', ptDraw)(); redraws.push(ptDraw);

  // ---------------- SUMO result tables ----------------
  const R = window.RESULTS || {};
  const table = (rows, cols) => !rows ? '' : `<table class="data"><thead><tr>${cols.map(c => `<th>${c[1]}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${r[c[0]] ?? '–'}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const cols = [['label', 'Controller'], ['avg_delay', 'Mean delay (s)'], ['avg_travel_time', 'Travel time (s)'], ['stops_per_veh', 'Stops / veh'], ['bus_avg_delay', 'Bus delay (s)']];
  $('advTable').innerHTML = table(R.advanced, cols);
  $('ablTable').innerHTML = table(R.ablation, [['label', 'Variant'], ...cols.slice(1)]);

  Quiz($('quizA'), QUIZ.advanced, 'advanced');
  addEventListener('themechange', () => redraws.forEach(f => f()));
  addEventListener('resize', () => redraws.forEach(f => f()));
})();
