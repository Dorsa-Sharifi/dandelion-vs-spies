# Dandelion Routing vs. Deanonymization Attacks — P2P Network Simulation

A Computer Networks course project (Spring 2026) that simulates a peer-to-peer gossip network in which every node is a **real, separate OS process** talking to its neighbours over **UDP on localhost**. On top of this network we implement:

1. plain flooding (diffusion) as a baseline,
2. two **source-deanonymization attacks** run by colluding "spy" nodes,
3. the **Dandelion** (Stem/Fluff) privacy protocol as a defence, and
4. a **Dandelion-aware attack** plus a final, more realistic spy model (bounded intentional delay).

The goal is to measure the trade-off between **privacy** (how often the attacker identifies the true originator of a message) and **speed** (how long a message takes to reach 80% of the network, `T_80%`).

---

## How it works

### Topology (`topology_generator.py`)

- Nodes are placed on a `1000 × 1000` grid, grouped into **4–6 clusters** with Gaussian scatter (σ = 60) around random cluster centres. The total is **20–30 nodes**.
- **Intra-cluster links:** each cluster is wired as a ring, so every node has degree ≥ 2 and each cluster is internally connected.
- **Inter-cluster links:** cluster *i* is linked to clusters *i+1* and *i+2*, which gives multiple independent paths between clusters and keeps the graph connected if one inter-cluster link fails.
- **Link delay:** the Euclidean distance between endpoints (1 unit = 1 ms). At send time, ±20% random **jitter** is added.
- Each node gets `127.0.0.1` and a UDP port starting at `5000`.
- Output: `topology.json`. The topology included in this repo has **24 nodes, 5 clusters, 34 links**.

### Node (`node.py`)

Every node is an `asyncio` UDP endpoint that:

- loads its neighbours and base delays from `topology.json`,
- keeps a **seen set** of packet IDs to deduplicate and avoid loops,
- reports every *first* reception to the simulator on UDP port `4999` (`node`, `packet_id`, `time`, `sender`, `state`),
- simulates link latency with `asyncio.sleep(base_delay + jitter)` before each send,
- routes packets according to their state:

| State | Behaviour at a relay node |
|-------|---------------------------|
| `Fluff` | Broadcast to all neighbours except the sender (ordinary diffusion). |
| `Stem` | With probability **p**, forward to one random neighbour (not the sender); with probability **1 − p**, switch to `Fluff` and broadcast. |
| `Stem` seen twice | Loop detected → immediately switch to `Fluff` and broadcast. |

The **originating** node starts a packet as `Stem` (Dandelion) by sending it to one random neighbour, or as `Fluff` when plain flooding is being tested (phases 1–2).

### Simulator (all `N_*simulator*.py` files)

The simulator:

1. loads the topology and picks the spy set with a fixed random seed,
2. spawns one `node.py` process per node,
3. injects **200 packets** from random honest nodes at random 50–200 ms intervals,
4. collects reception logs over UDP,
5. runs the attack(s) on what the spies observed and computes the metrics,
6. shuts the nodes down and writes JSON logs.

---

## Project structure

```
.
├── topology_generator.py                  # Generates topology.json
├── topology.json                          # 24-node, 5-cluster network used in the experiments
├── node.py                                # Node process (phases 1–4)
├── 8_node_phase5.py                       # Node process with spy intentional delay (phase 5)
│
├── 1_base_diffusion_simulator.py          # Phase 1: flooding + First-Spy attack (30% spies)
├── 2_attack_simulator.py                  # Phase 2: First-Spy vs. time-difference triangulation (15% spies)
├── 3_visualize_initial_phases.py          # Plots for phases 1–2
│
├── 4_dandelion_simulator_phase3.py        # Phase 3: Dandelion with parameter p
├── 5_parameter_swip_phase3.py             # Sweep p ∈ {0.9, 0.5, 0.1} × 5 seeds
├── 6_dandeliion_aware_attack_simulator_phase4.py   # Phase 4: Dandelion-aware attack
├── 7_parameter_swip_phase4.py             # Sweep for phase 4
├── 9_dandeliion_aware_attack_simulator_phase5.py   # Phase 5: spies delay packets
├── 10_parameter_swip_phase5.py            # Sweep for phase 5
├── 11_visualize_final_phases.py           # Plots for phases 3–4 sweep
│
├── figures/                               # Generated plots (PNG)
├── logs/                                  # Raw experiment output (JSON)
│   ├── base_diffusion_logs.json
│   ├── attack_diffusion_logs.json
│   ├── attack_summary.json
│   └── phase4/  phase5/                   # One summary file per (p, seed)
```

---

## Requirements

- Python 3.9+
- `numpy` and `matplotlib` (only for the visualization scripts)
- Free UDP ports **4999** (simulator) and **5000 – 5000+N−1** (nodes) on `127.0.0.1`

```bash
pip install numpy matplotlib
```

The simulators and nodes use only the Python standard library.

---

## Quick start

Run all commands from the project root (nodes are launched as `node.py` / `8_node_phase5.py` relative to the working directory). Make sure the `logs/` folder exists (it ships with the repo).

```bash
# 0. (Optional) generate a fresh random topology — this overwrites topology.json
python topology_generator.py

# Phase 1 — baseline flooding + First-Spy attack
python 1_base_diffusion_simulator.py

# Phase 2 — baseline vs. triangulation attack, then plots
python 2_attack_simulator.py
python 3_visualize_initial_phases.py

# Phase 3 — Dandelion, parameter sweep (15 runs)
python 5_parameter_swip_phase3.py

# Phase 4 — Dandelion-aware attack, sweep, then plots
python 7_parameter_swip_phase4.py
python 11_visualize_final_phases.py

# Phase 5 — spies with bounded intentional delay, sweep
python 10_parameter_swip_phase5.py
```

A single configuration can also be run directly:

```bash
python 6_dandeliion_aware_attack_simulator_phase4.py --p 0.5 --seed 42
```

Each run takes roughly 30–45 seconds (2 s node start-up, ~25 s of packet injection for 200 packets, plus a 5 s or 15 s propagation wait). Sweeps run sequentially so the ports never collide; **don't run two simulations at the same time**.

> If a run is killed abruptly, leftover `node.py` processes may keep the ports busy. Stop them before re-running.

---

## Evaluation metrics

Let *A* = attacker accuracy (fraction of the 200 packets whose true source was guessed correctly).

- **Attacker score:** `Score_adv = A / (number of spies)`
- **Honest-network score:** `Score_honest = (1 / T_80%) × (1 − A)`
- **`T_80%`:** time from injection until the packet has reached 80% of the nodes (`int(0.8 × N)` nodes).

---

## The phases

| Phase | Script(s) | Protocol | Attack(s) | Spies |
|-------|-----------|----------|-----------|-------|
| 1 | `1_base_diffusion_simulator.py` | Flooding | **First-Spy**: the neighbour that handed the packet to the earliest spy is declared the source | 30% |
| 2 | `2_attack_simulator.py` | Flooding | First-Spy and **Time-Difference Triangulation** | 15% |
| 3 | `4_…phase3.py`, `5_…phase3.py` | Dandelion (p = 0.9 / 0.5 / 0.1) | First-Spy and Triangulation | 15% |
| 4 | `6_…phase4.py`, `7_…phase4.py` | Dandelion | Adds the **Dandelion-aware attack** | 15% |
| 5 | `8_node_phase5.py`, `9_…phase5.py`, `10_…phase5.py` | Dandelion | Same as phase 4, but spies add a random extra delay (up to the link's base delay) before forwarding | 15% |

**Triangulation attack.** Dijkstra gives the expected delay from every candidate to every spy. For each honest candidate, the attack sums `|observed Δt − expected Δt|` over all spy pairs and picks the candidate with the smallest error. This works on flooding, where the spread is a clean wavefront from the source.

**Dandelion-aware attack.** Triangulation only finds the *Fluff* origin (the node where the stem ended), not the real source. The aware attack therefore:
- if a spy saw the packet while it was still in **Stem** state → blames the sender of that stem packet;
- otherwise → triangulates the Fluff origin, then picks the honest node whose network distance to it best matches the expected stem length `E[L] = 1/(1−p)` (capped at 5 hops) × average hop delay (reverse random walk).

**Phase 5** models spies that can't drop or hold packets forever, only delay them by at most the link's base delay.

---

## Results

All results below are from `topology.json` (24 nodes, 3 spies in phases 2–5), 200 packets per run. Phases 3–5 average **5 seeds** (42, 101, 202, 303, 404) per value of `p`.

### Flooding (phases 1–2)

| Attack | Accuracy | Score_adv | Score_honest |
|--------|---------:|----------:|-------------:|
| First-Spy (baseline) | 35.5% | 0.1183 | 0.738 |
| Triangulation | **62.0%** | 0.2067 | 0.435 |

Triangulation raises accuracy from 35.5% to 62%, since it cancels out per-link jitter by using timing information from every spy at once. The `T_80%` of plain flooding is about **0.87 s**, with σ ≈ 0.10 s.

### Dandelion (phases 3–5)

Mean accuracy (%) and mean `T_80%` over 5 seeds:

| Phase | p | First-Spy | Triangulation | Dandelion-aware | `T_80%` (s) |
|-------|--:|----------:|--------------:|----------------:|------------:|
| 3 | 0.9 | 16.0 | 7.4 | — | 2.361 |
| 3 | 0.5 | 15.0 | 7.6 | — | 1.457 |
| 3 | 0.1 | 15.1 | 9.6 | — | 1.227 |
| 4 | 0.9 | 15.3 | 7.7 | 16.7 | 2.358 |
| 4 | 0.5 | 14.2 | 9.0 | 17.0 | 1.462 |
| 4 | 0.1 | 14.4 | 9.2 | **22.3** | 1.236 |
| 5 | 0.9 | 15.8 | 8.0 | 16.5 | 2.527 |
| 5 | 0.5 | 13.6 | 8.0 | 16.9 | 1.565 |
| 5 | 0.1 | 14.5 | 9.1 | 21.2 | 1.310 |

**Takeaways**

- Dandelion cuts the triangulation attack from 62% down to under 10%, because the stem phase decouples the broadcast origin from the true source.
- Triangulation actually does *worse* than First-Spy under Dandelion — it locates the Fluff origin, not the sender.
- The Dandelion-aware attack recovers some accuracy, mostly when `p` is small (shorter stems are easier to reverse): 22.3% at p = 0.1.
- Larger `p` buys privacy at a latency cost: `T_80%` roughly doubles from ~1.2 s (p = 0.1) to ~2.4 s (p = 0.9).
- Letting spies add bounded delay (phase 5) slightly increases `T_80%` but barely changes attacker accuracy.

### Figures

| File | Content |
|------|---------|
| `figures/t80_distribution.png` | Histogram of `T_80%` under flooding (mean / median / σ) |
| `figures/attack_comparison.png` | Accuracy and scores: First-Spy vs. Triangulation |
| `figures/p_sweep_accuracy.png` | Attack accuracy vs. `p` |
| `figures/p_sweep_t80.png` | `T_80%` vs. `p` |
| `figures/results1.png`, `figures/result2.png` | Result summary screenshots |

---

## Log formats

- `logs/base_diffusion_logs.json`, `logs/attack_diffusion_logs.json`: per-packet records — `true_source`, `start_time`, `rx_times{node: t}`, and (phase 2) `senders{node: sender}`.
- `logs/attack_summary.json`: `accuracy`, `score_adv`, `score_honest`, each as `[baseline, proposed]`.
- `logs/phase4/…`, `logs/phase5/…`: `config` and `results` (`baseline_accuracy`, `proposed_accuracy`, `phase4_accuracy`, `avg_t80`). Per-packet data is not stored.
- Phase 3 re-running writes its logs to `logs/phase3/` (not included in the repo to keep it small).

---

## Notes and limitations

- **Everything runs on one machine.** Real network latency is emulated with `asyncio.sleep`; the numbers are comparable between experiments, but not to a real WAN.
- **Processing delay is zero** inside nodes in phases 1–4, so all measured timing comes from the emulated link delays plus jitter.
- **Spies behave honestly** in phases 1–4 (they relay normally and just log). Only phase 5 changes their behaviour.
- **Spy count differs between phases:** 30% in phase 1 (the maximum allowed), 15% in phases 2–5 (3 of 24 nodes), 
- **Small sample:** 24 nodes and 200 packets per run mean the per-seed accuracy varies noticeably (see `logs/phase*/`), which is why results are averaged over 5 seeds.
- Phases 4–5 each need a longer end-of-run wait (15 s) so late packets are not missed.
- Some scripts and filenames contain spelling quirks (`swip`, `dandeliion`); they are kept as-is so that the sweep scripts keep matching.

---

## Authors

- Dorsa Sharifi Ghombavani
- Diba Hadi
