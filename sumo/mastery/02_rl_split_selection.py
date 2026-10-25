"""
MASTERY 2 - Reinforcement-learning split-plan selection on top of SCATS
=======================================================================
Research question: can a learning agent choose split plans better than
SCATS's DS-equalisation rule, while keeping everything else (cycle length,
offsets, marriage, tactical control) exactly as SCATS does it?

Why this framing: replacing SCATS wholesale with deep RL is hard to deploy;
learning *inside* the SCATS plan library keeps the safety envelope (pre-
approved plans, min greens, intergreens) and is explainable.

Agent: tabular Q-learning, one Q-table shared by all intersections.
  state  : (bin(DS_A), bin(DS_B), bin(DS_C), current plan)   bins 0-.5-.8-1.0-inf
  action : split plan index 0..3
  reward : - mean number of halted vehicles on the approaches during the cycle
  update : Q(s,a) += alpha * (r + gamma * max_a' Q(s',a') - Q(s,a))

    python mastery/02_rl_split_selection.py --episodes 12
Outputs: results/mastery/rl/{q_table.json, learning_curve.png, rl_vs_scats.csv}
"""
import _path  # noqa: F401
import json
import os
import random
from collections import defaultdict

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import advanced

BINS = [0.5, 0.8, 1.0]


def bin_ds(x):
    return sum(x > b for b in BINS)


class QSplitAgent:
    def __init__(self, n_actions=4, alpha=0.2, gamma=0.7, epsilon=0.3):
        self.Q = defaultdict(lambda: [0.0] * n_actions)
        self.n_actions, self.alpha, self.gamma, self.epsilon = n_actions, alpha, gamma, epsilon
        self.prev = {}          # tls -> (state, action)
        self.rewards = []

    def state(self, ix, ds):
        return tuple(bin_ds(ds[p]) for p in ix.names) + (ix.plan,)

    # signature required by ControllerConfig.split_selector
    def __call__(self, ix, ds, g_now, plan_greens):
        rec = ix.last_cycle
        s = self.state(ix, ds)
        r = -rec["queue"] / max(rec["dur"], 1.0)
        if ix.tls in self.prev and self.epsilon > 0:
            ps, pa = self.prev[ix.tls]
            target = r + self.gamma * max(self.Q[s])
            self.Q[ps][pa] += self.alpha * (target - self.Q[ps][pa])
        self.rewards.append(r)
        if random.random() < self.epsilon:
            a = random.randrange(self.n_actions)
        else:
            q = self.Q[s]
            a = max(range(self.n_actions), key=lambda i: q[i])
        self.prev[ix.tls] = (s, a)
        return a

    def to_json(self):
        return {str(k): v for k, v in self.Q.items()}


def main():
    p = cli.parser(__doc__)
    p.add_argument("--episodes", type=int, default=12)
    args = p.parse_args()
    out = cli.outdir(args, "mastery/rl")
    random.seed(args.seed)
    agent = QSplitAgent()
    curve = []
    train_end = args.end or 3600
    for ep in range(args.episodes):
        agent.epsilon = max(0.05, 0.3 * (1 - ep / max(args.episodes - 1, 1)))
        agent.prev, agent.rewards = {}, []
        res = run(advanced(train_end), mode_config("scats", bus_priority=True, split_selector=agent),
                  f"train_ep{ep:02d}", out, seed=100 + ep, verbose=False)
        curve.append(res["avg_delay"])
        print(f"episode {ep:2d}  eps={agent.epsilon:.2f}  delay={res['avg_delay']:.1f}s  "
              f"states learned={len(agent.Q)}")
    with open(os.path.join(out, "q_table.json"), "w") as f:
        json.dump(agent.to_json(), f, indent=1)

    # evaluation on unseen seeds, greedy policy, full scenario
    agent.epsilon = 0.0
    rows = []
    for seed in (7, 8, 9):
        base = run(advanced(5400), mode_config("scats", bus_priority=True), f"scats_s{seed}", out, seed=seed)
        agent.prev = {}
        rl = run(advanced(5400), mode_config("scats", bus_priority=True, split_selector=agent),
                 f"rl_s{seed}", out, seed=seed)
        rows += [base, rl]
    cli.write_summary(rows, os.path.join(out, "rl_vs_scats.csv"))
    plots.line_compare(list(range(len(curve))), {"training delay": curve},
                       os.path.join(out, "learning_curve.png"), "Q-learning split selection - training",
                       "Episode", "Mean delay (s/veh)")
    s = [r["avg_delay"] for r in rows[0::2]]
    q = [r["avg_delay"] for r in rows[1::2]]
    print(f"\nEvaluation (3 unseen seeds): SCATS {sum(s)/3:.1f}s  vs  RL-split {sum(q)/3:.1f}s mean delay")
    print("Note: a small tabular agent will not always win - that is a research result too.\n"
          "Try: richer state (VK, queue), reward shaping, more episodes, DQN, or learning\n"
          "plan *contents* instead of choosing among 4 fixed plans.")


if __name__ == "__main__":
    main()
