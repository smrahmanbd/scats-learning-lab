# SCATS Learning Lab

Learn the **Sydney Coordinated Adaptive Traffic System (SCATS)** in three levels, with
interactive browser simulators, quizzes, a mind map and a runnable SCATS-style controller
for **Eclipse SUMO**.

| Level | What you learn | Browser simulators | SUMO labs |
|---|---|---|---|
| **1 Foundation** | cycle, phase, split, offset, intergreen · stop-line loops · degree of saturation (DS) and VK · tactical vs strategic control | live intersection (fixed / actuated / SCATS), DS calculator, cycle builder, controller race, Webster | `01_ds_lab`, `02_calibrate_h`, `03_fixed_vs_scats` |
| **2 Advanced** | every SCATS mechanism: CI-based cycle length, stretch, split plans + voting, offset plans + voting, subsystems, marriage/divorce, gap-out, phase skipping, coordinated-phase hold, transit priority (high/medium/low), Masterlink/Flexilink/Isolated | cycle controller, split selector, time-space diagram, marriage logic, gap-out timer, priority planner | `01_corridor_scats`, `02_ablation_study` |
| **3 Mastery** | research directions with implementations | CV sampling, RL agent you train in the browser, pressure vs DS split, detector faults | `01_cv_ds_estimation`, `02_rl_split_selection`, `03_maxpressure_hybrid`, `04_detector_faults`, `05_spat_prediction` |

**Website:** https://smrahmanbd.github.io/scats-learning-lab/

Plus a **42-question quiz bank** with explanations and an explorable **mind map**.

## Study guides and slides

Beginner-friendly study guides (plain-language explanations, worked hand calculations, a memory route, mind maps, an 18-question self-quiz with answers, a cheat sheet and a revision plan) and a matching slide deck with speaker notes for each level:

| Level | Study guide | Slides |
|---|---|---|
| Foundation | [SCATS_Foundation_Study_Guide.pdf](docs/materials/SCATS_Foundation_Study_Guide.pdf) | [SCATS_Foundation_Presentation.pptx](docs/materials/SCATS_Foundation_Presentation.pptx) |
| Advanced | [SCATS_Advanced_Study_Guide.pdf](docs/materials/SCATS_Advanced_Study_Guide.pdf) | [SCATS_Advanced_Presentation.pptx](docs/materials/SCATS_Advanced_Presentation.pptx) |
| Mastery | [SCATS_Mastery_Study_Guide.pdf](docs/materials/SCATS_Mastery_Study_Guide.pdf) | [SCATS_Mastery_Presentation.pptx](docs/materials/SCATS_Mastery_Presentation.pptx) |

## The website

Everything in `docs/` is a static site. To publish it on GitHub Pages:
**Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`**.
The site is published at https://smrahmanbd.github.io/scats-learning-lab/.

To view it locally:

```bash
cd docs && python -m http.server 8000     # then open http://localhost:8000
```

## The SUMO code

```bash
cd sumo
python -m pip install -r requirements.txt   # installs SUMO itself via eclipse-sumo
python foundation/03_fixed_vs_scats.py --gui
python run_all.py                           # all 10 labs, ~10 minutes
python tools/export_site_results.py         # refresh website figures and tables
python -m pytest tests -q
```

See [`sumo/README.md`](sumo/README.md) for the controller design and research hooks.

### Results from the included run (seed 1)

Four-intersection arterial, 90 minutes, tidal peaks, buses every 4 min:

| Controller | Mean delay (s/veh) | Stops/veh | Bus delay (s) |
|---|---|---|---|
| Fixed time (90 s plan) | 77.2 | 1.82 | 110.8 |
| Isolated actuated | 40.9 | 1.57 | 51.8 |
| **SCATS-style** | **36.9** | **1.30** | **29.7** |

Ablation (SCATS with one mechanism removed): no tactical 62.0 · no marriage 50.3 ·
no offset adaptation 45.2 · no bus priority 42.5 · no split adaptation 37.5 · no cycle adaptation 34.4.

Mastery studies are deliberately reported as found: with loop faults, plausibility alarms
recover delay from 59.2 to 40.7 s; the first RL split agent and the max-pressure hybrid do
**not** yet beat SCATS on this corridor — they are baselines for further research.

## Disclaimer

SCATS is owned by Transport for NSW. This project is an independent, educational
re-implementation of concepts published in the literature (degree of saturation, plan
voting, marriage/divorce, etc.). Parameter values are illustrative and are not official
SCATS settings.

MIT licensed.
