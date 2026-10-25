/* Shared page chrome, charts and the quiz engine. */
(function (g) {
  const PAGES = [
    ['index.html', 'Home'], ['foundation.html', 'Foundation'], ['advanced.html', 'Advanced'],
    ['mastery.html', 'Mastery'], ['mindmap.html', 'Mind map'], ['sumo.html', 'SUMO code'], ['quiz.html', 'Quiz bank'],
  ];
  const here = location.pathname.split('/').pop() || 'index.html';

  function chrome() {
    const band = document.createElement('header');
    band.className = 'band';
    band.innerHTML = `<div class="band-inner">
      <a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true"><i style="background:#d23b2f"></i><i style="background:#d99a00"></i><i style="background:#1f9d55"></i></span>SCATS Learning Lab</a>
      <nav aria-label="Site">${PAGES.map(([h, t]) => `<a href="${h}"${h === here ? ' aria-current="page"' : ''}>${t}</a>`).join('')}</nav>
      <button class="theme-btn" type="button" id="themeBtn">Theme</button></div>`;
    document.body.prepend(band);
    const foot = document.createElement('footer');
    foot.className = 'site wrap';
    foot.innerHTML = `SCATS is owned by Transport for NSW. This lab is an independent, educational re-implementation of published SCATS concepts;
      timing parameters are illustrative, not official values. Simulator code: <a href="https://eclipse.dev/sumo/">Eclipse SUMO</a> + TraCI.`;
    document.body.append(foot);
    const btn = document.getElementById('themeBtn');
    const apply = m => { if (m) document.documentElement.setAttribute('data-theme', m); else document.documentElement.removeAttribute('data-theme'); btn.textContent = m === 'dark' ? 'Dark' : m === 'light' ? 'Light' : 'Auto theme'; };
    let mode = null; try { mode = localStorage.getItem('scats-theme'); } catch (e) {}
    apply(mode);
    btn.addEventListener('click', () => {
      mode = mode === null ? 'dark' : mode === 'dark' ? 'light' : null;
      try { mode ? localStorage.setItem('scats-theme', mode) : localStorage.removeItem('scats-theme'); } catch (e) {}
      apply(mode); g.dispatchEvent(new Event('themechange'));
    });
  }

  function routeIndex() {
    const nav = document.querySelector('.route ol'); if (!nav) return;
    const hs = [...document.querySelectorAll('.content h2[id]')];
    nav.innerHTML = hs.map(h => `<li><a href="#${h.id}">${h.dataset.short || h.textContent}</a></li>`).join('');
    const links = [...nav.querySelectorAll('a')];
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) links.forEach(l => l.classList.toggle('on', l.getAttribute('href') === '#' + e.target.id));
    }), { rootMargin: '-20% 0px -70% 0px' });
    hs.forEach(h => io.observe(h));
  }

  function copyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
      const b = document.createElement('button'); b.className = 'copy'; b.type = 'button'; b.textContent = 'Copy';
      b.addEventListener('click', () => {
        const txt = pre.querySelector('code') ? pre.querySelector('code').innerText : pre.innerText.replace(/Copy$/, '');
        const done = () => { b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200); };
        try { navigator.clipboard.writeText(txt).then(done, () => sel(pre)); } catch (e) { sel(pre); }
      });
      pre.append(b);
    });
    function sel(el) { const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  }

  // ---------- minimal canvas line/step chart ----------
  g.tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  g.lineChart = function (cv, series, o = {}) {
    const r = cv.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    cv.width = r.width * dpr; cv.height = r.height * dpr;
    const c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = r.width, H = r.height, L = 40, R = 10, T = 10, B = 24;
    c.clearRect(0, 0, W, H);
    const all = series.flatMap(s => s.data.filter(v => v != null && isFinite(v)));
    const n = Math.max(1, ...series.map(s => s.data.length));
    let ymin = o.ymin ?? Math.min(0, ...all), ymax = o.ymax ?? Math.max(1, ...all) * 1.08;
    if (ymax === ymin) ymax = ymin + 1;
    const X = i => L + (W - L - R) * (n <= 1 ? 0 : i / (n - 1)), Y = v => T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin));
    c.font = '12px Barlow, system-ui, sans-serif'; c.fillStyle = tok('--muted'); c.strokeStyle = tok('--line'); c.lineWidth = 1;
    const ticks = o.ticks || 4;
    for (let k = 0; k <= ticks; k++) {
      const v = ymin + (ymax - ymin) * k / ticks, y = Y(v);
      c.beginPath(); c.moveTo(L, y); c.lineTo(W - R, y); c.stroke();
      c.fillText(Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(2), 2, y + 4);
    }
    if (o.xlabel) c.fillText(o.xlabel, L, H - 6);
    (o.hlines || []).forEach(hl => { c.strokeStyle = tok(hl.color || '--muted'); c.setLineDash([5, 4]); c.beginPath(); c.moveTo(L, Y(hl.y)); c.lineTo(W - R, Y(hl.y)); c.stroke(); c.setLineDash([]); });
    series.forEach(s => {
      c.strokeStyle = s.color.startsWith('--') ? tok(s.color) : s.color; c.lineWidth = s.width || 2; c.beginPath();
      let started = false;
      s.data.forEach((v, i) => {
        if (v == null || !isFinite(v)) { started = false; return; }
        const x = X(i), y = Y(v);
        if (!started) { c.moveTo(x, y); started = true; }
        else if (s.step) { c.lineTo(x, Y(s.data[i - 1] ?? v)); c.lineTo(x, y); }
        else c.lineTo(x, y);
      });
      c.stroke();
      const last = s.data.length - 1;
      if (last >= 0 && s.data[last] != null && isFinite(s.data[last])) { c.fillStyle = c.strokeStyle; c.beginPath(); c.arc(X(last), Y(s.data[last]), 3, 0, 7); c.fill(); }
    });
  };

  // ---------- quiz engine ----------
  g.Quiz = function (el, questions, key) {
    let order = questions.map((_, i) => i), i = 0, score = 0, answered = false;
    let best = 0; try { best = +localStorage.getItem('quiz-' + key) || 0; } catch (e) {}
    function shuffle() { for (let k = order.length - 1; k > 0; k--) { const j = Math.floor(Math.random() * (k + 1)); [order[k], order[j]] = [order[j], order[k]]; } }
    function render() {
      if (i >= order.length) return finish();
      const q = questions[order[i]]; answered = false;
      el.innerHTML = `<div class="quiz-top"><strong class="num">Question ${i + 1} of ${order.length}</strong>
        <span class="muted num">Score ${score} · best ${best}/${order.length}</span></div>
        <div class="quiz-progress"><i style="width:${100 * i / order.length}%"></i></div>
        <div class="quiz-q">${q.q}</div><div class="quiz-opts">${q.o.map((t, k) => `<button type="button" data-k="${k}">${t}</button>`).join('')}</div>
        <div class="quiz-exp" hidden></div><div class="quiz-nav"><button class="btn" type="button" id="${key}-next" hidden>Next question</button></div>`;
      el.querySelectorAll('.quiz-opts button').forEach(b => b.addEventListener('click', () => pick(+b.dataset.k)));
      el.querySelector(`#${key}-next`).addEventListener('click', () => { i++; render(); });
    }
    function pick(k) {
      if (answered) return; answered = true;
      const q = questions[order[i]], bs = el.querySelectorAll('.quiz-opts button');
      bs.forEach((b, j) => { b.disabled = true; if (j === q.a) b.classList.add('right'); else if (j === k) b.classList.add('wrong'); });
      if (k === q.a) score++;
      const ex = el.querySelector('.quiz-exp'); ex.hidden = false;
      ex.innerHTML = `<strong>${k === q.a ? 'Correct.' : 'Not quite.'}</strong> ${q.e}`;
      const nx = el.querySelector(`#${key}-next`); nx.hidden = false; if (i === order.length - 1) nx.textContent = 'See result'; nx.focus();
    }
    function finish() {
      best = Math.max(best, score); try { localStorage.setItem('quiz-' + key, best); } catch (e) {}
      const pct = Math.round(100 * score / order.length);
      el.innerHTML = `<div class="quiz-q">You scored ${score} of ${order.length} (${pct}%)</div>
        <p>${pct >= 80 ? 'Ready for the next level.' : pct >= 50 ? 'Good base. Revisit the sections behind the questions you missed.' : 'Work through the simulators on this page again, then retry.'}</p>
        <div class="quiz-nav"><button class="btn" type="button" id="${key}-again">Retry in a new order</button></div>`;
      el.querySelector(`#${key}-again`).addEventListener('click', () => { shuffle(); i = 0; score = 0; render(); });
    }
    render();
  };

  document.addEventListener('DOMContentLoaded', () => { chrome(); routeIndex(); copyButtons(); });
})(window);
