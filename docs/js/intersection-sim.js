/* A live, single-intersection queue simulation with three controllers:
   fixed time, vehicle actuated, and SCATS (DS-driven cycle + split voting).
   One stop-line loop per approach feeds the DS calculation exactly as in SCATS. */
(function (g) {
  const S = g.SCATS;
  const PH = ['A', 'B'];                       // A = east-west (main road), B = north-south
  const APPR = { W: 'A', E: 'A', N: 'B', S: 'B' };
  const SPLITS = [{ A: .55, B: .45 }, { A: .65, B: .35 }, { A: .45, B: .55 }, { A: .75, B: .25 }];
  const INTER = { A: 5, B: 5 }, MINS = { A: 8, B: 6 };
  const SAT_HEADWAY = 2.0, OCC_TIME = 0.45, STARTUP = 2, H = 1.55;

  class IntersectionSim {
    constructor(canvas, opts = {}) {
      this.cv = canvas; this.ctx = canvas.getContext('2d');
      this.opts = Object.assign({ mode: 'scats', demand: { W: 650, E: 600, N: 320, S: 300 }, speed: 4, seed: 7, compact: false }, opts);
      this.listeners = [];
      this.reset();
      this._raf = null; this._last = 0;
      new ResizeObserver(() => this.resize()).observe(canvas);
      this.resize();
    }
    on(fn) { this.listeners.push(fn); }
    reset() {
      this.rand = S.rng(this.opts.seed);
      this.t = 0;
      this.q = { W: [], E: [], N: [], S: [] };
      this.crossing = [];
      this.acc = { W: 0, E: 0, N: 0, S: 0 };
      this.loop = {};
      Object.keys(this.q).forEach(a => this.loop[a] = { gap: 9, occFlash: 0, T: 0, n: 0, g: 0 });
      this.C = this.opts.mode === 'scats' ? 60 : 90;
      this.plan = 0; this.voter = new S.Voter(0, 3, 2);
      this.history = [];
      this.delaySum = 0; this.served = 0; this.queueInt = 0;
      this.lastDs = { A: 0, B: 0 };
      this._startCycle();
    }
    setMode(m) { this.opts.mode = m; this.reset(); }
    setDemand(d) { Object.assign(this.opts.demand, d); }
    setSpeed(s) { this.opts.speed = s; }

    _startCycle() {
      if (this.rec) this._closeCycle();
      const split = this.opts.mode === 'fixed' || this.opts.mode === 'actuated' ? SPLITS[0] : SPLITS[this.plan];
      this.greens = S.allocateGreens(this.C, split, INTER, MINS);
      this.cycleStart = this.t;
      this.rec = { t: this.t, C: this.C, plan: this.plan, g: {}, ds: {}, greensPlanned: { ...this.greens } };
      this.carry = 0;
      this._startGreen(0);
    }
    _startGreen(i) {
      this.idx = i; this.stage = 'green'; this.stageStart = this.t;
      this.alloc = this.greens[PH[i]] + this.carry; this.carry = 0;
      Object.keys(APPR).filter(a => APPR[a] === PH[i]).forEach(a => { const L = this.loop[a]; L.T = 0; L.n = 0; L.g = 0; });
    }
    _endGreen() {
      const p = PH[this.idx], el = this.t - this.stageStart;
      let ds = 0;
      Object.keys(APPR).filter(a => APPR[a] === p).forEach(a => {
        const L = this.loop[a]; ds = Math.max(ds, S.degreeOfSaturation(L.g, L.T, L.n, H));
      });
      this.rec.g[p] = el; this.rec.ds[p] = ds; this.lastDs[p] = ds;
      this.carry = Math.max(0, this.alloc - el);
      this.stage = 'yellow'; this.stageStart = this.t;
    }
    _closeCycle() {
      const r = this.rec; r.dur = this.t - r.t;
      PH.forEach(p => { if (r.ds[p] == null) r.ds[p] = 0; if (r.g[p] == null) r.g[p] = r.greensPlanned[p]; });
      if (this.opts.mode === 'scats') {
        const plans = SPLITS.map(s => S.allocateGreens(r.C, s, INTER, MINS));
        const gNow = {}; PH.forEach(p => gNow[p] = Math.max(1, r.g[p]));
        const sel = S.selectSplit(r.ds, gNow, plans);
        r.vote = sel.best; this.plan = this.voter.vote(sel.best);
        this.C = S.nextCycle(this.C, Math.max(r.ds.A, r.ds.B));
      }
      this.history.push(r); if (this.history.length > 80) this.history.shift();
      this.listeners.forEach(f => f(r, this));
    }

    tick() {               // one simulated second
      const t = ++this.t, d = this.opts.demand;
      // arrivals
      for (const a in this.q) {
        const k = S.poisson(this.rand, d[a] / 3600);
        for (let i = 0; i < k; i++) this.q[a].push({ arr: t, hue: this.rand() });
      }
      const green = this.stage === 'green' ? PH[this.idx] : null;
      for (const a in this.q) {
        const L = this.loop[a]; let occ = 0;
        if (green === APPR[a] && t - this.stageStart > STARTUP) {
          this.acc[a] = Math.min(this.acc[a] + 1 / SAT_HEADWAY, 1.0);
          while (this.acc[a] >= 1 && this.q[a].length) {
            const v = this.q[a].shift(); this.acc[a] -= 1;
            this.delaySum += Math.max(0, t - v.arr); this.served++;
            occ += OCC_TIME; L.n++; L.occFlash = 1;
            this.crossing.push({ a, born: performance.now(), hue: v.hue });
          }
        } else this.acc[a] = 0;
        L.gap = occ > 0 ? 0 : L.gap + 1;
        // measure over effective green (after start-up lost time), like a loop-based g' estimate
        if (green === APPR[a] && t - this.stageStart > STARTUP) { L.g += 1; L.T += 1 - Math.min(1, occ); }
        this.queueInt += this.q[a].length;
      }
      // controller
      if (this.stage === 'green') {
        const p = PH[this.idx], el = t - this.stageStart;
        const lanes = Object.keys(APPR).filter(a => APPR[a] === p);
        const gapOut = this.opts.mode !== 'fixed' && el >= MINS[p] && lanes.every(a => this.loop[a].gap >= 3);
        if (el >= this.alloc || gapOut) this._endGreen();
      } else if (this.stage === 'yellow' && t - this.stageStart >= 3) { this.stage = 'red'; this.stageStart = t; }
      else if (this.stage === 'red' && t - this.stageStart >= 2) {
        if (this.idx + 1 < PH.length) this._startGreen(this.idx + 1); else this._startCycle();
      }
    }

    stats() {
      return { avgDelay: this.served ? this.delaySum / this.served : 0, served: this.served,
        avgQueue: this.t ? this.queueInt / this.t : 0, C: this.C, plan: this.plan, ds: this.lastDs,
        phase: PH[this.idx], stage: this.stage, inStage: this.t - this.stageStart, t: this.t };
    }

    start() { if (this._raf) return; this._last = performance.now(); this._acc = 0; const loop = now => {
      this._acc += (now - this._last) / 1000 * this.opts.speed; this._last = now;
      let n = 0; while (this._acc >= 1 && n < 200) { this.tick(); this._acc -= 1; n++; }
      this.draw(); this._raf = requestAnimationFrame(loop); }; this._raf = requestAnimationFrame(loop); }
    stop() { cancelAnimationFrame(this._raf); this._raf = null; }

    resize() {
      const r = this.cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
      this.cv.width = Math.max(10, r.width * dpr); this.cv.height = Math.max(10, r.height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this.W = r.width; this.Hh = r.height; this.draw();
    }

    draw() {
      const c = this.ctx, W = this.W, Hh = this.Hh; if (!W) return;
      const css = getComputedStyle(document.documentElement);
      const tok = n => css.getPropertyValue(n).trim();
      const bar = this.opts.compact ? 0 : 34;
      const h = Hh - bar, cx = W / 2, cy = h / 2, rw = Math.min(W, h) * 0.17;
      c.clearRect(0, 0, W, Hh);
      c.fillStyle = tok('--road-verge'); c.fillRect(0, 0, W, h);
      c.fillStyle = tok('--road'); c.fillRect(0, cy - rw, W, 2 * rw); c.fillRect(cx - rw, 0, 2 * rw, h);
      // lane markings
      c.strokeStyle = tok('--marking'); c.lineWidth = 2; c.setLineDash([10, 10]);
      [[0, cy, cx - rw, cy], [cx + rw, cy, W, cy], [cx, 0, cx, cy - rw], [cx, cy + rw, cx, h]].forEach(([a, b, d, e]) => { c.beginPath(); c.moveTo(a, b); c.lineTo(d, e); c.stroke(); });
      c.setLineDash([]);
      // stop lines + loops + signals
      const geo = {
        W: { sx: cx - rw - 4, sy: cy + rw / 2, dx: -1, dy: 0, sl: [cx - rw - 3, cy, cx - rw - 3, cy + rw] },
        E: { sx: cx + rw + 4, sy: cy - rw / 2, dx: 1, dy: 0, sl: [cx + rw + 3, cy - rw, cx + rw + 3, cy] },
        N: { sx: cx - rw / 2, sy: cy - rw - 4, dx: 0, dy: -1, sl: [cx - rw, cy - rw - 3, cx, cy - rw - 3] },
        S: { sx: cx + rw / 2, sy: cy + rw + 4, dx: 0, dy: 1, sl: [cx, cy + rw + 3, cx + rw, cy + rw + 3] },
      };
      const green = this.stage === 'green' ? PH[this.idx] : null, yellow = this.stage === 'yellow' ? PH[this.idx] : null;
      const sz = Math.max(4, rw * 0.32), gapPx = sz * 1.55;
      for (const a in geo) {
        const G = geo[a];
        c.strokeStyle = tok('--marking'); c.lineWidth = 3; c.beginPath(); c.moveTo(G.sl[0], G.sl[1]); c.lineTo(G.sl[2], G.sl[3]); c.stroke();
        // loop detector
        const L = this.loop[a]; L.occFlash *= 0.86;
        c.strokeStyle = L.occFlash > 0.2 ? tok('--amber') : tok('--loop'); c.lineWidth = 1.5;
        c.strokeRect(G.sx + G.dx * 10 - sz * 0.7, G.sy + G.dy * 10 - sz * 0.7, sz * 1.4, sz * 1.4);
        // queue
        this.q[a].slice(0, 60).forEach((v, i) => {
          const x = G.sx + G.dx * (8 + i * gapPx), y = G.sy + G.dy * (8 + i * gapPx);
          if (x < -10 || x > W + 10 || y < -10 || y > h + 10) return;
          c.fillStyle = v.hue > 0.93 ? tok('--car-alt') : tok('--car');
          const horiz = G.dy === 0;
          c.fillRect(x - (horiz ? sz * 0.75 : sz * 0.45), y - (horiz ? sz * 0.45 : sz * 0.75), horiz ? sz * 1.5 : sz * 0.9, horiz ? sz * 0.9 : sz * 1.5);
        });
        // signal head
        const col = green === APPR[a] ? tok('--go') : yellow === APPR[a] ? tok('--amber') : tok('--stop');
        const hx = { W: cx - rw - 14, E: cx + rw + 14, N: cx - rw - 14, S: cx + rw + 14 }[a];
        const hy = { W: cy + rw + 14, E: cy - rw - 14, N: cy - rw - 14, S: cy + rw + 14 }[a];
        c.fillStyle = tok('--signal-body'); c.beginPath(); c.arc(hx, hy, 8, 0, 7); c.fill();
        c.fillStyle = col; c.beginPath(); c.arc(hx, hy, 5.5, 0, 7); c.fill();
      }
      // crossing vehicles
      const now = performance.now(), life = 1400 / Math.max(1, this.opts.speed / 3);
      this.crossing = this.crossing.filter(v => now - v.born < life);
      this.crossing.forEach(v => {
        const G = geo[v.a], k = (now - v.born) / life, dist = k * (2 * rw + 60);
        const x = G.sx - G.dx * dist, y = G.sy - G.dy * dist, horiz = G.dy === 0;
        c.fillStyle = v.hue > 0.93 ? tok('--car-alt') : tok('--car');
        c.fillRect(x - (horiz ? sz * 0.75 : sz * 0.45), y - (horiz ? sz * 0.45 : sz * 0.75), horiz ? sz * 1.5 : sz * 0.9, horiz ? sz * 0.9 : sz * 1.5);
      });
      // timing bar: planned cycle with position marker
      if (bar) {
        const y0 = h + 10, bw = W - 20, x0 = 10, C = this.rec.C;
        let x = x0;
        PH.forEach((p, i) => {
          const gw = this.greens[p] / C * bw, iw = INTER[p] / C * bw;
          c.fillStyle = i === 0 ? tok('--phase-a') : tok('--phase-b'); c.fillRect(x, y0, gw, 14);
          c.fillStyle = tok('--fg'); c.font = '600 11px Barlow, system-ui, sans-serif'; c.fillText(`${p}  ${this.greens[p].toFixed(0)}s`, x + 4, y0 + 11);
          x += gw; c.fillStyle = tok('--amber'); c.fillRect(x, y0, iw * 0.6, 14); c.fillStyle = tok('--stop'); c.fillRect(x + iw * 0.6, y0, iw * 0.4, 14); x += iw;
        });
        const pos = Math.min(1, (this.t - this.cycleStart) / C);
        c.fillStyle = tok('--fg'); c.fillRect(x0 + pos * bw - 1, y0 - 4, 2, 22);
      }
    }
  }
  IntersectionSim.SPLITS = SPLITS;
  g.IntersectionSim = IntersectionSim;
})(window);
