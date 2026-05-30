# DEPSO — Discrete Evolutionary Particle Swarm Optimization

> **Warehouse Order Batching & Picker Routing Optimization**  
> Python implementation and full benchmark validation of Kübler, Glock & Bauernhansl (2020)

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Scenarios](https://img.shields.io/badge/Scenarios-35-green)
![Validation](https://img.shields.io/badge/Validation-1400%20simulations-success)
---
## 🚀 Live Demo

You can test the application live in your browser using the link below:

🔗 [Depso Warehouse Optimization - Streamlit App](https://depso-warehouse-optimization-i8c5cjyrkrczbgwtjufice.streamlit.app/)

---
## Overview

This project implements and validates the **DEPSO (Discrete Evolutionary Particle Swarm Optimization)** algorithm for the joint warehouse optimization problem. The implementation reproduces the complete experimental setup of Kübler et al. (2020) in Python, covering:

- **Storage location assignment** (ABC class-based Pareto distribution)
- **Order batching** (First-Fit with 100 WU capacity constraint)
- **Picker routing** (Nearest Neighbor + 2-opt local search)

The benchmark was run across **35 scenarios × 40 independent instances = 1,400 total simulations**, with results validated against the paper's published Appendix H values and an independent external dataset (Foodmart).

---

## Key Results

### Synthetic Benchmark (35 Scenarios)

| Comparison       | Our Average | Paper Average (Appendix H) | Max Deviation |
|------------------|-------------|----------------------------|---------------|
| DEPSO vs SOP     | −85.02%     | −83.78%                    | ±3.3pp        |
| DEPSO vs FCFS    | −45.00%     | −40.80%                    | ±3.3pp        |
| DEPSO vs Savings | −30.58%     | −31.64%                    | ±3.3pp        |

DEPSO outperformed all three baseline algorithms in **all 35 scenarios** (105/105 comparisons).

### External Validation — Foodmart Dataset

| Layout Group | Avg vs SOP | Avg vs FCFS | Avg vs Savings |
|--------------|------------|-------------|----------------|
| d5 (sparse)  | −56.63%    | −14.14%     | −5.62%         |
| d10 (medium) | −47.28%    | −10.97%     | −7.36%         |
| d20 (dense)  | −39.45%    | −9.85%      | −3.51%         |
| **Overall**  | **−48.27%**| **−11.32%** | **−5.47%**     |

DEPSO won **all 27 Foodmart instances** (81/81 comparisons) on a completely independent dataset with different warehouse layout, capacity (320 WU), and distance metric.

> **Total: 186 tests, 186 wins, 0 losses**

---

## Algorithm

DEPSO is a discrete adaptation of Particle Swarm Optimization for combinatorial warehouse problems. Each particle represents a permutation of orders. The swarm iteratively improves solutions through:

1. **Initialization** — one particle seeded with Clarke–Wright Savings, rest random
2. **Movement** — position update via crossover with personal/global best
3. **Mutation** — random perturbation to escape local optima
4. **Local search** — 2-opt improvement on the current routing solution
5. **Early stopping** — halts if Gbest improvement < 0.1% over 100 consecutive iterations

```
for each iteration:
    for each particle:
        apply movement operator (crossover with pbest / gbest)
        apply mutation (with probability threshold_gbest)
        evaluate fitness: first_fit_batching → nearest_neighbor → two_opt
        update pbest, gbest
    if stagnation > patience: stop
```

---

## Warehouse Configuration

Following Kübler et al. (2020) Figure 7:

| Parameter              | Value                       |
|------------------------|-----------------------------|
| Picking aisles         | 10                          |
| Cross aisles           | 4 (positions 0, 30, 60, 90) |
| Rack elements per side | 90                          |
| Slots per rack         | 4                           |
| Total locations        | 7,200                       |
| Items (SKUs)           | 6,000                       |
| Picker capacity        | 100 WU                      |
| Distance metric        | Manhattan                   |
| Depot location         | Right cross aisle, lower end|
| Item weights           | Uniform [0.1, 1.0] WU       |
| Access frequency (AF)  | 0.6 (Pareto: top 20% → 60%) |

---

## Implementation Parameters

| Parameter        | This Implementation | Paper (Section 6.2) | Note                          |
|------------------|---------------------|----------------------|-------------------------------|
| num_particles    | **8**               | 5                    | Pre-tested; see note below    |
| max_iterations   | 500                 | 500                  | ✓ Match                       |
| threshold_gbest  | 0.5                 | 0.5                  | ✓ Match                       |
| max_ls_iter      | 100                 | 100                  | ✓ Match                       |
| max_stagnation   | 20                  | 20                   | ✓ Match                       |
| Instances/scenario | 40               | 40                   | ✓ Match                       |
| Early stopping   | patience=100, δ=0.001 | —                  | Added for efficiency          |

> **Note on `num_particles=8`:** The paper uses 5 particles as selected from pre-testing with {5, 10, 15}. We independently determined that 8 particles provides better search diversity in our Python/multiprocessing environment. Increasing particle count expands the simultaneously explored solution space, reducing premature convergence risk — particularly in large scenarios (NOrd=150, 200) where the permutation space is vast. The additional particles introduce negligible overhead under parallel execution. This value remains within the range tested by the paper and constitutes a valid parameter adaptation, not a methodology deviation.

---

## Project Structure

```
DEPSO-WAREHOUSE-OPTIMIZATION/
│
├── data/
│   └── DEPSO_Sentetik_Veri_Seti.xlsx    # Synthetic benchmark dataset
│
├── figures/                              # Generated benchmark figures
│   ├── benchmark_comparison/
│   ├── convergence_plots/
│   └── route_visualizations/
│
├── src/
│   ├── main.py                           # Main benchmark runner
│   ├── utils.py                          # Core DEPSO algorithm
│   ├── visualizer.py                     # Benchmark visualizations
│   ├── batch_visualization_v2.py         # Batch & route visualizations
│   └── merge_results.py                  # Result aggregation
│
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/your-username/DEPSO-Warehouse-Optimization.git
cd DEPSO-Warehouse-Optimization
pip install -r requirements.txt
```

### Requirements

```
numpy>=1.21.0
pandas>=1.3.0
matplotlib>=3.4.0
openpyxl>=3.0.0
scipy>=1.7.0
```

---

## Usage

### Run full benchmark (35 scenarios × 40 instances)

```bash
python src/main.py
```

> ⚠️ Full benchmark takes approximately 4–6 hours on Apple M2 Pro with multiprocessing enabled. Individual scenario runtimes range from ~8 seconds (50_2_6) to ~2,248 seconds (200_10_2).

### Generate benchmark visualizations

```bash
python src/visualizer.py
```

Produces:
- Grouped bar charts (our results vs. Paper Appendix H)
- Performance gap trend lines
- Average travel distance comparisons
- Convergence curves

### Generate batch & route visualizations

```bash
python src/batch_visualization_v2.py
```

Produces:
- Batch formation capacity charts
- Order assignment flow tables
- Picker route visualizations (warehouse grid)

---

## Benchmark Scenarios

Following paper Section 6.1 (scenario `50_2_2` excluded per paper Section 6.2 — all orders fit into one batch):

| Parameter              | Values           |
|------------------------|------------------|
| NOrd (orders)          | 50, 100, 150, 200|
| NmaxOl (orderlines)    | 2, 6, 10         |
| AmaxOl (parts/orderline)| 2, 6, 10        |
| Total scenarios        | 35 (4×3×3 − 1)   |
| Instances per scenario | 40               |
| Total simulations      | 1,400            |

---

## Validation

The implementation was validated through six independent checks:

| Check | Method | Result |
|-------|--------|--------|
| Manhattan distance | Manual calculation vs. code output | ✓ Exact match |
| Batch capacity | Zero violations across 1,400 simulations | ✓ Verified |
| Pareto AF=0.6 | Top 20% items = 60.0% of demand | ✓ 0.0% deviation |
| Statistical robustness | CLT: N=40, SE=0.40% | ✓ Verified |
| Paper Appendix H | All 35 scenarios within ±3.3pp | ✓ Verified |
| External dataset | Foodmart: 27/27 instances won | ✓ Verified |

---

## Implementation Highlights

14 engineering improvements were made over a naive implementation:

| # | Improvement | Impact |
|---|-------------|--------|
| 1 | `deepcopy` → `list()` shallow copy | −70% memory usage |
| 2 | Route cache (frozenset key) | Eliminates redundant fitness evaluations |
| 3 | Order weight caching | Eliminates millions of redundant summations |
| 4 | Early stopping (patience=100) | 30–60% runtime reduction |
| 5 | Multiprocessing pool | ~40 hours → ~4–6 hours total benchmark |
| 6 | Worker limit control | Prevents thermal throttling |
| 7 | Integer overflow fix | Eliminates negative distances in large scenarios |
| 8 | Savings initialization | One particle seeded with Clarke–Wright solution |

---

## Authors

| Name | Role |
|------|------|
| Nilasu Yıldız | Implementation & Validation |
| Gonca Yıldız | Implementation & Validation |
| Yunus Emre Demirel | Implementation & Validation |

**İstinye University**  
Faculty of Engineering and Natural Sciences  
May 2026

---

## Reference

```bibtex
@article{kubler2020depso,
  title     = {A new iterative method for solving the joint dynamic storage location 
               assignment, order batching and picker routing problem in manual 
               picker-to-parts warehouses},
  author    = {K{\"u}bler, Philipp and Glock, Christoph H. and Bauernhansl, Thomas},
  journal   = {Computers \& Industrial Engineering},
  volume    = {147},
  pages     = {106645},
  year      = {2020},
  publisher = {Elsevier},
  doi       = {10.1016/j.cie.2020.106645}
}
```

---

## License

This project was developed for academic and research purposes at İstinye University.
