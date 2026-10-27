/* Standard space time: two interactive explainers for the SCATS Foundation page.
   1) Where h comes from: a saturated queue crossing the stop-line loop.
   2) Same count, three stories: how gap time separates free flow from a jam. */
(function () {
  const $ = id => document.getElementById(id);
  if (!$('stCv') || !$('s3Cv')) return;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#888';
  const COL = {
    get occ() { return css('--fg'); }, get need() { return '#2f7fd1'; }, get waste() { return css('--stop'); },
    get road() { return css('--road'); }, get mark() { return css('--marking'); }, get loop() { return css('--amber'); },
    get car() { return css('--car-alt'); }, get muted() { return css('--muted'); }, get sunk() { return css('--sunk'); },
    get go() { return css('--go'); }, get fg() { return css('--fg'); },
  };
  function setup(cv) {
    const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2.5);
    cv.width = Math.max(1, r.width * d); cv.height = Math.max(1, r.height * d);
    const c = cv.getContext('2d'); c.setTransform(d, 0, 0, d, 0, 0);
    return { c, W: r.width, H: r.height };
  }
  function bind(id, fmt, fn) {
    const el = $(id), out = $(id + 'o');
    const upd = () => { out.textContent = fmt(+el.value); fn(); };
    el.addEventListener('input', upd); return upd;
  }
  const f1 = v => v.toFixed(1), f2 = v => v.toFixed(2);

  // ===================================================== 1. where h comes from
  let tSim = 0, last = null, paused = false;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  function p1() {
    const s = +$('stS').value, Lc = +$('stL').value, Ll = +$('stLoop').value, v = +$('stV').value;
    const Hd = 3600 / s, occ = (Lc + Ll) / v, h = Hd - occ;
    return { s, Lc, Ll, v, Hd, occ, h };
  }
  function read1() {
    const p = p1();
    $('stHd').textContent = f2(p.Hd); $('stOcc').textContent = f2(p.occ);
    $('stH').textContent = p.h > 0 ? f2(p.h) : '< 0';
    $('stSp').textContent = f1(p.v * p.Hd);
    $('stNote').textContent = p.h > 0
      ? `Each car takes ${f2(p.Hd)} s from front bumper to front bumper. For ${f2(p.occ)} s of that it covers the loop, so the loop is empty for only ${f2(p.h)} s. That shortest gap is the standard space time h.`
      : 'These settings are impossible: cars would have to overlap. Lower the saturation flow or the car length, or raise the speed.';
  }
  function draw1() {
    const cv = $('stCv'); const { c, W, H } = setup(cv); const p = p1();
    c.clearRect(0, 0, W, H);
    // road (top) — metres mapped to px
    const narrow = W < 560, roadY = 18, roadH = 46, mPx = W / (narrow ? 32 : 70), loopX = W * 0.62;
    c.fillStyle = COL.road; c.fillRect(0, roadY, W, roadH);
    c.strokeStyle = COL.mark; c.setLineDash([10, 10]); c.lineWidth = 2;
    c.beginPath(); c.moveTo(0, roadY + 3); c.lineTo(W, roadY + 3); c.moveTo(0, roadY + roadH - 3); c.lineTo(W, roadY + roadH - 3); c.stroke(); c.setLineDash([]);
    // loop
    const loopW = p.Ll * mPx;
    // which cars are on the loop now; car fronts every v*Hd metres, moving at v
    const gapM = p.v * p.Hd, phase = (tSim * p.v) % gapM;
    let onLoop = false;
    for (let k = -2; k < (W / mPx) / Math.max(gapM, 0.5) + 3; k++) {
      const frontM = phase + k * gapM; const fx = frontM * mPx; const bx = fx - p.Lc * mPx;
      if (fx < -10 || bx > W + 10) continue;
      if (fx > loopX && bx < loopX + loopW) onLoop = true;
      c.fillStyle = COL.car; c.beginPath();
      c.roundRect ? c.roundRect(bx, roadY + 12, p.Lc * mPx, roadH - 24, 4) : c.rect(bx, roadY + 12, p.Lc * mPx, roadH - 24); c.fill();
    }
    c.strokeStyle = COL.loop; c.lineWidth = onLoop ? 4 : 2.5; c.strokeRect(loopX, roadY + 8, loopW, roadH - 16);
    c.fillStyle = COL.muted; c.font = '600 13px Barlow, sans-serif'; c.textAlign = 'left';
    c.fillText('stop-line loop' + (onLoop ? ' · ON' : ' · empty'), loopX, roadY + roadH + 16);
    c.fillText('queue leaving on green →', 6, roadY + roadH + 16);
    // timeline (bottom): last 12 s of loop state
    const tlY = 122, tlH = 30, span = narrow ? 5 : 12, sc = W / span;
    c.fillStyle = COL.sunk; c.fillRect(0, tlY, W, tlH);
    // occupancy intervals: a car is on the loop when its front has passed loopX and its back hasn't passed loopX+loopW.
    // In time, each car occupies the loop for occ seconds, once every Hd seconds.
    const t0 = tSim - span;
    const tOffset = ((loopX / mPx) / p.v); // time for a front at 0 to reach the loop
    const firstK = Math.floor((t0 - tOffset) / p.Hd) - 1;
    for (let k = firstK; k * p.Hd + tOffset < tSim + p.Hd; k++) {
      const ts = k * p.Hd + tOffset; // front reaches loop (relative to phase origin)
      // align with phase: fronts are at phase + k*gap at time tSim; arrival time of a front at loopX:
      const a = ts, b = ts + p.occ;
      const x1 = (a - t0) * sc, x2 = (Math.min(b, a + p.Hd) - t0) * sc;
      if (x2 < 0 || x1 > W) continue;
      c.fillStyle = COL.occ; c.fillRect(Math.max(0, x1), tlY, Math.min(W, x2) - Math.max(0, x1), tlH);
      if (p.h > 0) {
        const g1 = (b - t0) * sc, g2 = (a + p.Hd - t0) * sc;
        c.fillStyle = COL.need; c.globalAlpha = 0.55; c.fillRect(Math.max(0, g1), tlY, Math.min(W, g2) - Math.max(0, g1), tlH); c.globalAlpha = 1;
      }
    }
    // bracket one headway in the middle
    const mid = tSim - span / 2;
    const kk = Math.floor((mid - tOffset) / p.Hd), a0 = kk * p.Hd + tOffset;
    const xa = (a0 - t0) * sc, xb = (a0 + p.occ - t0) * sc, xc = (a0 + p.Hd - t0) * sc;
    c.strokeStyle = COL.fg; c.lineWidth = 1.5; c.fillStyle = COL.fg; c.font = '600 12.5px Barlow, sans-serif'; c.textAlign = 'center';
    const br = (x1, x2, y, label, above) => {
      const d = above ? 6 : -6;
      c.beginPath(); c.moveTo(x1, y + d); c.lineTo(x1, y); c.lineTo(x2, y); c.lineTo(x2, y + d); c.stroke();
      c.fillText(label, (x1 + x2) / 2, above ? y - 5 : y + 15);
    };
    br(xa, xc, tlY - 8, `one headway = ${f2(p.Hd)} s`, true);
    if (p.h > 0) { br(xa, xb, tlY + tlH + 8, `on loop ${f2(p.occ)}`, false); br(xb, xc, tlY + tlH + 8, `h ${f2(p.h)}`, false); }
    c.textAlign = 'left'; c.fillStyle = COL.muted; c.font = '12px Barlow, sans-serif';
    c.fillText(`loop record, last ${span} s (dark = car on loop, blue = loop empty)`, 0, tlY + tlH + 50);
  }
  function loop1(ts) {
    if (last === null) last = ts;
    const dt = Math.min(0.1, (ts - last) / 1000); last = ts;
    if (!paused && !reduce) tSim += dt * 0.6;
    draw1(); requestAnimationFrame(loop1);
  }
  ['stS', 'stL', 'stLoop', 'stV'].forEach((id, i) => bind(id, [v => v + ' veh/h', v => f1(v) + ' m', v => f1(v) + ' m', v => f1(v) + ' m/s'][i], read1)());
  $('stPause').addEventListener('click', () => { paused = !paused; $('stPause').textContent = paused ? 'Play' : 'Pause'; });
  tSim = 12; requestAnimationFrame(loop1);

  // ===================================================== 2. same count, three stories
  const TRUE_H = 1.0;
  let story = 'free';
  function record() {
    const g = +$('s3G').value, n = +$('s3N').value;
    let occ, gap, lead;
    if (story === 'free') { occ = 0.5; gap = (g - n * occ) / n; lead = gap / 2; }
    else if (story === 'sat') { occ = Math.max(0.3, g / n - TRUE_H); gap = TRUE_H; lead = 0; }
    else { occ = Math.max(0.3, g / n - 0.35); gap = 0.35; lead = 0; }
    // cars: [start, end] on the loop within the green
    const cars = []; let t = lead;
    for (let i = 0; i < n; i++) { cars.push([t, Math.min(g, t + occ)]); t += occ + gap; }
    // gaps: before each car (the leading gap counts for the first car), plus the tail
    const gaps = []; let prev = 0;
    cars.forEach(([a, b]) => { if (a - prev > 1e-6) gaps.push([prev, a]); prev = b; });
    if (g - prev > 1e-6) gaps.push([prev, g]);
    return { g, n, occ, cars, gaps };
  }
  function draw3() {
    const R = record(), hA = +$('s3H').value;
    const T = R.gaps.reduce((s, [a, b]) => s + (b - a), 0);
    const need = hA * R.n, waste = T - need, used = R.g - waste, ds = used / R.g;
    const cnt = R.n / (R.g * 1800 / 3600);
    $('s3T').textContent = f1(T); $('s3Need').textContent = f1(need);
    $('s3W').textContent = f1(waste); $('s3DS').textContent = f2(ds); $('s3Cnt').textContent = f2(cnt);
    const ok = ds < 0.75 ? ['Lots of wasted green: traffic is light. SCATS can give this phase less time.', COL.go]
      : ds <= 1.02 ? ['The gaps are just what the cars need: the green is fully used.', css('--amber-ink')]
      : ['The loop was almost never empty: cars are crawling in a queue. DS above 1 asks for more green.', COL.waste];
    $('s3Verdict').textContent = ok[0]; $('s3Verdict').style.borderLeftColor = ok[1];

    const cv = $('s3Cv'); const { c, W, H } = setup(cv); c.clearRect(0, 0, W, H);
    const x0 = 2, w = W - 4, sc = w / R.g, y = 26, bh = 40;
    c.fillStyle = COL.sunk; c.fillRect(x0, y, w, bh);
    // gaps: needed part (up to h each, applied per car-gap) and wasted part
    let needLeft = need;
    R.gaps.forEach(([a, b]) => {
      const len = b - a, nd = Math.max(0, Math.min(len, hA, needLeft));
      needLeft -= nd;
      c.fillStyle = COL.need; c.globalAlpha = 0.6; c.fillRect(x0 + a * sc, y, nd * sc, bh); c.globalAlpha = 1;
      if (len - nd > 1e-6) { c.fillStyle = COL.waste; c.globalAlpha = 0.55; c.fillRect(x0 + (a + nd) * sc, y, (len - nd) * sc, bh); c.globalAlpha = 1; }
    });
    c.fillStyle = COL.occ; R.cars.forEach(([a, b]) => c.fillRect(x0 + a * sc, y, Math.max(1.5, (b - a) * sc), bh));
    c.fillStyle = COL.muted; c.font = '600 13px Barlow, sans-serif';
    c.textAlign = 'left'; c.fillText('green starts', x0, 16); c.textAlign = 'right'; c.fillText(`green ends (${R.g} s)`, x0 + w, 16);
    for (let s = 0; s <= R.g; s += 5) { c.fillRect(x0 + s * sc - 0.5, y + bh + 2, 1, 5); }
    // the DS bar: used green vs wasted
    const y2 = y + bh + 30;
    c.textAlign = 'left'; c.fillStyle = COL.fg; c.font = '600 13px Barlow, sans-serif';
    c.fillText('green, re-sorted:', x0, y2 - 6);
    const usedW = Math.max(0, Math.min(R.g, used)) * sc;
    c.fillStyle = COL.go; c.fillRect(x0, y2, usedW, 18);
    if (waste > 0) { c.fillStyle = COL.waste; c.globalAlpha = 0.55; c.fillRect(x0 + usedW, y2, waste * sc, 18); c.globalAlpha = 1; }
    c.font = '600 12.5px Barlow, sans-serif'; c.fillStyle = '#fff';
    if (usedW > 120) c.fillText(`used ${f1(Math.min(R.g, used))} s`, x0 + 6, y2 + 13.5);
    if (ds > 1) {
      c.strokeStyle = COL.waste; c.lineWidth = 2; c.setLineDash([5, 4]);
      c.strokeRect(x0 + w - 1, y2 - 2, Math.min(60, (used - R.g) * sc), 22); c.setLineDash([]);
      c.fillStyle = COL.waste; c.textAlign = 'right'; c.fillText(`demand exceeds the green by ${f1(used - R.g)} s`, x0 + w - 4, y2 + 36);
    }
  }
  document.querySelectorAll('#s3Seg button').forEach(b => b.addEventListener('click', () => {
    story = b.dataset.story;
    document.querySelectorAll('#s3Seg button').forEach(x => x.setAttribute('aria-pressed', x === b));
    draw3();
  }));
  [bind('s3G', v => v + ' s', draw3), bind('s3N', v => v + ' cars', draw3), bind('s3H', v => f2(v) + ' s', draw3)].forEach(f => f());
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(draw3, 120); });
  addEventListener('themechange', draw3);
})();
