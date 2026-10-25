/* SCATS engine - JavaScript mirror of sumo/scats/core.py.
   Educational re-implementation of published SCATS concepts; parameters are illustrative. */
(function (g) {
  const S = {};

  S.degreeOfSaturation = (green, T, n, h) => green <= 0 ? 0 : Math.max(0, (green - (T - n * h)) / green);
  S.effectiveGreen = (green, T, n, h) => Math.max(0, green - (T - n * h));
  S.vk = (ds, green, mf) => ds * green * mf / 3600;

  S.cycleDefaults = { lmin: 40, lmax: 140, lstretch: 110, target: 0.9, up: 6, upFast: 9, down: 6, fastDs: 1.0 };
  S.nextCycle = (C, ds, p = S.cycleDefaults) => {
    const desired = ds > 0 ? C * ds / p.target : p.lmin;
    const up = ds >= p.fastDs ? p.upFast : p.up;
    const delta = Math.max(-p.down, Math.min(up, desired - C));
    return Math.max(p.lmin, Math.min(p.lmax, C + delta));
  };

  // split: {A:0.6,B:0.4}; intergreen/minGreen per phase
  S.allocateGreens = (C, split, inter, mins, stretch, lstretch) => {
    const ph = Object.keys(split);
    const lost = ph.reduce((a, p) => a + inter[p], 0);
    let base = C, extra = 0;
    if (stretch && lstretch && C > lstretch) { base = lstretch; extra = C - lstretch; }
    const avail = Math.max(0, base - lost);
    const tot = ph.reduce((a, p) => a + split[p], 0) || 1;
    const gr = {};
    ph.forEach(p => gr[p] = avail * split[p] / tot);
    const deficit = ph.reduce((a, p) => a + Math.max(0, mins[p] - gr[p]), 0);
    if (deficit > 0) {
      const slack = {}; let st = 0;
      ph.forEach(p => { if (gr[p] > mins[p]) { slack[p] = gr[p] - mins[p]; st += slack[p]; } });
      ph.forEach(p => { if (gr[p] < mins[p]) gr[p] = mins[p]; else if (slack[p]) gr[p] -= deficit * slack[p] / (st || 1); });
    }
    if (extra && stretch in gr) gr[stretch] += extra;
    return gr;
  };

  S.predictPlanDs = (ds, gNow, gPlan) => {
    const o = {};
    for (const p in ds) o[p] = gPlan[p] > 0 ? ds[p] * gNow[p] / gPlan[p] : 9.9;
    return o;
  };
  S.selectSplit = (ds, gNow, planGreens, criterion = 'max') => {
    const scores = planGreens.map(gp => {
      const v = Object.values(S.predictPlanDs(ds, gNow, gp));
      return criterion === 'max' ? Math.max(...v) : v.reduce((a, b) => a + b, 0);
    });
    let best = 0; scores.forEach((s, i) => { if (s < scores[best]) best = i; });
    return { best, scores };
  };

  S.Voter = class {
    constructor(initial, window = 3, needed = 2) { this.current = initial; this.window = window; this.needed = needed; this.history = []; }
    vote(choice) {
      this.history.push(choice); if (this.history.length > this.window) this.history.shift();
      if (choice !== this.current && this.history.filter(c => c === choice).length >= this.needed) this.current = choice;
      return this.current;
    }
  };

  S.offsetPlanNames = ['OP1 eastbound wave', 'OP2 westbound wave', 'OP3 simultaneous', 'OP4 alternate'];
  S.offsetsForPlan = (plan, xs, ref, speed, C) => xs.map((x, k) => {
    const tt = (x - xs[ref]) / speed;
    let o = plan === 0 ? tt : plan === 1 ? -tt : plan === 2 ? 0 : (C / 2) * (((k - ref) % 2 + 2) % 2);
    return ((o % C) + C) % C;
  });
  S.selectOffsetPlan = (east, west, linkTt, C, low = 3, ratio = 1.3) => {
    if (east + west < low) return 2;
    if (east > ratio * west) return 0;
    if (west > ratio * east) return 1;
    return Math.abs(linkTt - C / 2) < 0.2 * C ? 3 : 2;
  };

  S.Marriage = class {
    constructor(p = {}) { this.p = Object.assign({ marry: 18, divorce: 10, gap: 25, votes: 3 }, p); this.married = false; this.streak = 0; }
    vote(linkVk, ca, cb) {
      const want = this.married ? linkVk >= this.p.divorce : (linkVk >= this.p.marry && Math.abs(ca - cb) <= this.p.gap);
      if (want !== this.married) { this.streak++; if (this.streak >= this.p.votes) { this.married = want; this.streak = 0; } }
      else this.streak = 0;
      return this.married;
    }
  };

  S.webster = (L, Y) => Y >= 0.95 ? Infinity : (1.5 * L + 5) / (1 - Y);

  // seeded RNG so demos are repeatable
  S.rng = seed => { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 1e9) / 1e9; }; };
  S.poisson = (rand, lambda) => { let L = Math.exp(-lambda), k = 0, p = 1; do { k++; p *= rand(); } while (p > L); return k - 1; };

  g.SCATS = S;
})(window);
