# WiFi Channel Optimisation System

A Python-based system that scans your 2.4GHz WiFi environment, identifies interference, and recommends the optimal channel using a custom interference scoring algorithm. Includes network path analysis using Dijkstra's shortest path algorithm on real traceroute data.

**Real hardware. Real measurements. Real before/after proof.**

---

## Results at a Glance

| Metric | Before | After | Improvement |
|---             |---|---|---|
| WiFi Channel | 2 (neighbour busy) | 7 (zero interference) | Algorithm recommendation |
| Ping spike count | 12 spikes / 60 sec | 5 spikes / 60 sec | 58% reduction |
| Raw average ping | 47.9 ms | 45.5 ms | 2.4 ms improvement |
| Clean average ping | 43.5 ms | 44.3 ms | Stable baseline maintained |

---

## Table of Contents

1. [Phase 1 — WiFi Channel Optimisation](#phase-1--wifi-channel-optimisation)
   - [Step 1: Ping Logger](#step-1-ping-logger)
   - [Theory: 2.4GHz Band and Channel Interference](#theory-24ghz-band-and-channel-interference)
   - [The Algorithm](#the-algorithm)
   - [Results](#results--phase-1)
2. [Phase 2 — Network Path Optimisation](#phase-2--network-path-optimisation)
   - [Theory: Network Graphs](#theory-network-graphs)
   - [The Algorithm](#the-algorithm-1)
   - [Results](#results--phase-2)
3. [Complexity Analysis](#complexity-analysis)
4. [How to Run](#how-to-run)
5. [Project Structure](#project-structure)

---

## Phase 1 — WiFi Channel Optimisation

### Step 1: Ping Logger

Before applying any algorithm, we needed a baseline measurement of network latency. The ping logger measures real ping to a target server every second for a set duration and saves every reading to a CSV file.

**Why Python instead of the built-in Windows ping command:**

| Feature | Windows Ping | Python Ping Logger |
|---|---|---|
| Samples | Manual, limited | Automated, hundreds |
| Data storage | Screen only | CSV saved permanently |
| Spike detection | Misses between samples | Catches every spike |
| Graph generation | Not possible | Full matplotlib graphs |
| Before/after comparison | Not possible | CSV files compared automatically |

**The code:**

```python
import subprocess
import csv
import time
import statistics
from datetime import datetime

TARGET   = "8.8.8.8"
DURATION = 60
OUTPUT   = "ping_sample.csv"

def ping_once(host):
    result = subprocess.run(["ping", "-n", "1", host],
                            capture_output=True, text=True)
    for line in result.stdout.split("\n"):
        if "time=" in line:
            return float(line.split("time=")[1].split("ms")[0].strip())
    return None

def remove_outliers(readings):
    sorted_r = sorted(readings)
    q1 = sorted_r[len(sorted_r) // 4]
    q3 = sorted_r[(3 * len(sorted_r)) // 4]
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    return [r for r in readings if lower <= r <= upper]
```

**What each part does:**

- `ping_once()` — runs a single Windows ping command and parses the latency value from the text output
- `remove_outliers()` — uses the IQR (Interquartile Range) statistical method to remove abnormal spikes before calculating averages. This gives a clean baseline that represents stable network performance rather than occasional interference events.

**Validation — proving our code is accurate:**

We ran our logger and the built-in Windows ping simultaneously on the same target:

| Metric | Windows Ping | Our Logger | Difference |
|---|---|---|---|
| Average | 48 ms | 49.9 ms | 1.9 ms |
| Min | 43 ms | 43 ms | 0 ms |

A 1.9 ms difference is within acceptable bounds — just normal code execution overhead. The logger is accurate.

---

### Theory: 2.4GHz Band and Channel Interference

**What is the 2.4GHz band?**

WiFi routers communicate using radio frequencies. The 2.4GHz band is divided into 13 channels, each 22MHz wide. The channels are spaced only 5MHz apart, which means neighbouring channels physically overlap with each other.

**The 13 channels and their frequencies:**

| Channel | Frequency (MHz) |
|---|---|
| 1 | 2412 |
| 2 | 2417 |
| 3 | 2422 |
| 4 | 2427 |
| 5 | 2432 |
| 6 | 2437 |
| 7 | 2442 |
| 8 | 2447 |
| 9 | 2452 |
| 10 | 2457 |
| 11 | 2462 |
| 12 | 2467 |
| 13 | 2472 |

**How channel overlap causes interference:**

Because each channel is 22MHz wide but channels are only 5MHz apart, a signal on channel 1 actually overlaps with channels 2, 3, 4, and 5. This means if your neighbour's router is on channel 3, your router on channel 1 will experience interference — even though they are on different channels.

**The overlap map — which channels interfere with which:**

```
Channel 1  overlaps with: 2, 3, 4, 5
Channel 2  overlaps with: 1, 3, 4, 5, 6
Channel 3  overlaps with: 1, 2, 4, 5, 6, 7
Channel 4  overlaps with: 1, 2, 3, 5, 6, 7, 8
Channel 5  overlaps with: 1, 2, 3, 4, 6, 7, 8, 9
Channel 6  overlaps with: 2, 3, 4, 5, 7, 8, 9, 10
Channel 7  overlaps with: 3, 4, 5, 6, 8, 9, 10, 11
Channel 8  overlaps with: 4, 5, 6, 7, 9, 10, 11, 12
Channel 9  overlaps with: 5, 6, 7, 8, 10, 11, 12, 13
Channel 10 overlaps with: 6, 7, 8, 9, 11, 12, 13
Channel 11 overlaps with: 7, 8, 9, 10, 12, 13
Channel 12 overlaps with: 8, 9, 10, 11, 13
Channel 13 overlaps with: 9, 10, 11, 12
```

When two routers operate on overlapping channels, their signals collide. This causes packet retransmission — your device sends a packet, it collides with the neighbour's signal, gets corrupted, and has to be sent again. Each retransmission adds latency. This is what causes ping spikes during gaming.

---

### The Algorithm

**How the algorithm selects the best channel:**

```
Step 1: Scan all 13 channels
        Measure signal strength on each channel using netsh
        Classify each channel as BUSY (signal >= -80 dBm) or QUIET

Step 2: Build the busy set B and quiet set Q
        B = all channels with active networks
        Q = all channels with no active networks

Step 3: For each quiet channel, count its busy overlaps
        n(q) = how many busy channels physically overlap with q
        φ(q) = what is the strongest signal among those busy channels

Step 4: Select the best quiet channel
        q* = the quiet channel with the lowest n(q)
        If tie on n(q) → pick the one with lowest φ(q)
        If still tied → pick the lower channel number
```

This is called lexicographic minimisation — we rank candidates by the most important criterion first, then use secondary criteria only to break ties.

**The full code:**

```python
BUSY_THRESHOLD = -80
NOISE_FLOOR    = -95.0

OVERLAP_MAP = {
    1:  [2, 3, 4, 5],       2:  [1, 3, 4, 5, 6],
    3:  [1, 2, 4, 5, 6, 7], 4:  [1, 2, 3, 5, 6, 7, 8],
    5:  [1, 2, 3, 4, 6, 7, 8, 9],
    6:  [2, 3, 4, 5, 7, 8, 9, 10],
    7:  [3, 4, 5, 6, 8, 9, 10, 11],
    8:  [4, 5, 6, 7, 9, 10, 11, 12],
    9:  [5, 6, 7, 8, 10, 11, 12, 13],
    10: [6, 7, 8, 9, 11, 12, 13],
    11: [7, 8, 9, 10, 12, 13],
    12: [8, 9, 10, 11, 13],
    13: [9, 10, 11, 12]
}

def classify_channels(signal_dict):
    B = {ch for ch, sig in signal_dict.items() if sig >= BUSY_THRESHOLD and ch <= 13}
    Q = {ch for ch, sig in signal_dict.items() if sig < BUSY_THRESHOLD and ch <= 13}
    return B, Q

def compute_scores(Q, B, signal_dict):
    scores = {}
    for q in sorted(Q):
        overlapping_busy = [ch for ch in OVERLAP_MAP.get(q, []) if ch in B]
        n_q   = len(overlapping_busy)
        phi_q = max(signal_dict[ch] for ch in overlapping_busy) if overlapping_busy else -999
        scores[q] = {'n': n_q, 'phi': phi_q, 'busy_overlaps': overlapping_busy}
    return scores

def select_best_channel(scores):
    return min(scores.keys(), key=lambda q: (scores[q]['n'], scores[q]['phi'], q))
```

**What each function does:**

`classify_channels()` — separates all 13 channels into two groups. Busy means a real network is actively transmitting there. Quiet means the channel is free.

`compute_scores()` — for each quiet channel, looks up the overlap map to find which busy channels it would interfere with. Counts them (n) and records the strongest one (φ).

`select_best_channel()` — picks the winner using the two scores. The channel with the fewest busy overlaps wins. If multiple channels have the same overlap count, the one with the weakest interfering neighbour wins.

---

### Results — Phase 1

**Real scan output:**

```
Ch   Signal(dBm)   Status
  1        -95.0    QUIET
  2        -50.0    BUSY   ← neighbour router
  3        -95.0    QUIET
  ...
  7        -95.0    QUIET
  ...

BUSY channels  B = [2]
QUIET channels Q = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

Interference scores:
Ch 1 → overlaps busy ch2 → n=1, φ=-50.0
Ch 7 → overlaps NO busy channels → n=0, φ=-∞  ← WINNER

Recommendation: Switch to Channel 7
```

**Channel analysis graph:**

![Channel Analysis](graphs/channel_analysis.png)

**Before/after ping comparison:**

![Ping Comparison](graphs/ping_comparison.png)

**Before/after proof screenshots:**

The screenshots below show the router admin panel and ping logger running simultaneously before and after the channel switch.

Before — Channel 2 (busy, neighbour occupying it):
- Raw average: 47.9 ms
- Spikes detected: 12

After — Channel 7 (zero interference):
- Raw average: 45.5 ms
- Spikes detected: 5

**Result: 58% reduction in ping spikes after switching to the algorithm-recommended channel.**

---

## Phase 2 — Network Path Optimisation

### Theory: Network Graphs

Your internet connection travels through multiple network nodes between your device and the game server. Each link between nodes has a latency cost in milliseconds. The complete path can be modelled as a weighted graph where:

- **Nodes** = network hops (your router, ISP nodes, backbone nodes, server)
- **Edges** = connections between hops
- **Edge weight** = measured latency in milliseconds

The problem then becomes: find the path from your device to the server with the minimum total latency. This is the classic shortest path problem.

**Real network topology measured via traceroute:**

```
Device → Router (9ms) → ISP_1 (10ms) → ISP_2 (8ms) → ISP_3 (5ms)
       → Backbone_1 (4ms) → Backbone_2 (4ms) → Intl_GW (18ms)
       → Google_P (48ms) → Google_1 (40ms) → Google_2 (39ms)
       → Google_3 (46ms) → Google_E (39ms) → Server (45ms)
```

Total measured hops: 14 nodes, 15 edges.

---

### The Algorithm

**How Dijkstra works:**

Dijkstra's algorithm is a greedy shortest path algorithm. At every step it asks: "which unvisited node has the lowest total distance from the start?" and extends the path through that node. It never revisits a node once it has found the minimum distance to it.

```
Step 1: Start at Device with distance 0
        All other nodes start with distance infinity

Step 2: Visit the node with lowest known distance
        Update distances to all its unvisited neighbours

Step 3: Repeat until the target (Server) is visited

Greedy rule: always extend through the lowest-distance node
This guarantees the minimum total latency path
```

**Step by step trace on real data:**

```
Step  1: Visit Device          cumulative = 0 ms
         → Router: 0 + 9 = 9 ms

Step  2: Visit Router          cumulative = 9 ms
         → ISP_1: 9 + 10 = 19 ms

Step  3: Visit ISP_1           cumulative = 19 ms
         → ISP_2: 19 + 8 = 27 ms
         → Backbone_1 (alt): 19 + 25 = 44 ms

Step  4: Visit ISP_2           cumulative = 27 ms
         → ISP_3: 27 + 5 = 32 ms

...

Step  8: Visit Intl_GW         cumulative = 58 ms
         → Google_P: 58 + 48 = 106 ms  ✗ not better (best=105)

Step  9: Visit Google_P        cumulative = 105 ms
         → Google_1: 105 + 40 = 145 ms

TARGET REACHED in 14 steps — Total: 314 ms
```

At Step 8, Dijkstra correctly rejected the 106 ms alternative because it had already found a 105 ms path to Google_P via Backbone_2 at Step 7. This is the greedy selection in action.

**Time complexity: O((V + E) log V)**

For our network: V=14 nodes, E=15 edges = O(110) operations. For a national ISP with V=10,000 nodes and E=50,000 edges, Dijkstra still runs in milliseconds.

---

### Results — Phase 2

**Network path graph:**

![Dijkstra Path](graphs/dijkstra_path.png)

**Path comparison:**

| Path | Route | Total Latency |
|---|---|---|
| Primary (Dijkstra optimal) | All 13 hops via real traceroute | 314 ms |
| Alternative A | Skip ISP nodes 2 and 3 | 327 ms |
| Alternative B | Skip international gateway | 315 ms |

Dijkstra correctly identified the 314 ms path as minimum.

> Note: Alternative paths use hypothetical edge weights to demonstrate the algorithm's selection capability. In a real network management system, these would correspond to actual routing table entries.

---

## Complexity Analysis

**D&C vs Linear scan benchmark:**

![Complexity Growth](graphs/complexity_growth.png)

| Input size | D&C (ms) | Linear (ms) | D&C overhead |
|---|---|---|---|
| 13 | 0.0076 | 0.0008 | 9.5x |
| 25 | 0.0149 | 0.0012 | 12.4x |
| 50 | 0.0306 | 0.0021 | 14.6x |
| 100 | 0.0629 | 0.0039 | 16.1x |
| 200 | 0.1310 | 0.0074 | 17.7x |

Both algorithms are O(n). D&C shows higher overhead on a single CPU core due to recursive function calls. However D&C is architecturally parallelisable — each half of the channel list can be processed simultaneously on separate CPU cores, reducing effective time to O(log n) in parallel systems. Linear scan cannot be parallelised in the same way. For a national operator scanning thousands of channels across distributed nodes, D&C offers a significant advantage.

---

## How to Run

**Requirements:**

```
Python 3.8+
Windows OS (uses netsh and tracert commands)
```

**Install dependencies:**

```bash
pip install matplotlib
```

**Run in order:**

```bash
# Step 1 — Measure baseline ping
python src/ping_logger.py

# Step 2 — Scan channels and get recommendation
python src/wifi_channel_optimiser.py

# Step 3 — Switch your router to the recommended channel manually
# Then run ping logger again to measure improvement

# Step 4 — Run Dijkstra on your real network
python src/dijkstra.py

# Step 5 — Generate before/after comparison graph
python src/plot_comparison.py
```

---

## Project Structure

```
wifi-optimisation/
├── src/
│   ├── ping_logger.py           # Measures real ping every second
│   ├── wifi_channel_optimiser.py # Channel scan + interference scoring
│   ├── dijkstra.py              # Network graph + shortest path
│   └── plot_comparison.py       # Before/after comparison graph
├── data/
│   ├── baseline_ping.csv        # Ping before channel switch
│   └── ping_sample.csv          # Ping after channel switch
├── graphs/
│   ├── channel_analysis.png     # 13 channel interference map
│   ├── complexity_growth.png    # Algorithm benchmark chart
│   ├── dijkstra_path.png        # Network topology diagram
│   └── ping_comparison.png      # Before/after ping proof
└── README.md
```

---

## Author

**Nimesha Nanayakkara**
Telecommunications Engineering

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://www.linkedin.com/in/projectswnimee)
[![GitHub](https://img.shields.io/badge/GitHub-projectswnimee-black)](https://github.com/projectswnimee)
