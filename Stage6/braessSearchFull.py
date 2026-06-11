

import os
import csv
import random
import subprocess

import sumolib
from Stage5.metrics import compute_metric, count_completed
from Stage5.pipeline import (
    generate_initial_trips, generate_flow_trips,
    generate_routes, generate_routes_modified, run_simulation,
)

# ---------------------------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------------------------
NET_FILE      = "net_xml/big_fragment_krakow_fixed.net.xml"

# test bazowy (single-edge): wiele seedów, top N najbardziej obciążonych
SEEDS         = [144, 42, 200, 777, 1337, 2024, 7, 99]   # 8 seedów
TOP_N         = 30             # ile najbardziej obciążonych krawędzi badać
MIN_OCCUPANCY = 0.1            # próg "obciążona niezerowa" (occupancy % > 0)

# testy kombinacji (wiele krawędzi usuwanych naraz) - jeden ustalony seed
FIXED_SEED    = 144            # seed dla testów kombinacji
N_BEST        = 15             # ile najlepszych krawędzi w puli
N_WORST       = 15             # ile najgorszych krawędzi w puli
COMBO_RNG     = 144            # seed losowania zestawów

RESULTS_DIR   = "output/results"           # pliki TXT per krawędź (test bazowy)
RESULTS_CSV   = "output/results.csv"       # zbiorczy CSV wszystkich testów


def find_related_edges(net_file, base_edge_id):
    net = sumolib.net.readNet(net_file, withInternal=False)
    related = []
    base = base_edge_id.split("#")[0].lstrip("-")
    prefix = "-" if base_edge_id.startswith("-") else ""
    for edge in net.getEdges():
        eid = edge.getID()
        if eid == base_edge_id or eid.startswith(f"{prefix}{base}#"):
            related.append(eid)
    return related


def create_network_without_edges(base_edge_ids, output_net):
    related = []
    for base in base_edge_ids:
        related.extend(find_related_edges(NET_FILE, base))
    related = list(dict.fromkeys(related))  # unikaty, zachowaj kolejność
    edges_to_remove = ",".join(related) if related else ",".join(base_edge_ids)
    print(f"  Usuwam krawędzie: {edges_to_remove}")
    subprocess.run([
        "netconvert",
        "--sumo-net-file", NET_FILE,
        "--remove-edges.explicit", edges_to_remove,
        "--output-file", output_net,
    ], check=True)


def create_network_without_edge(base_edge_id, output_net):
    create_network_without_edges([base_edge_id], output_net)


def append_csv(row):
    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    fields = ["test", "label", "edges", "n_edges", "seed",
              "baseline_metric", "scenario_metric", "diff", "pct", "verdict"]
    new_file = not os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow(row)


def loaded_edges(edge_data_file, min_occupancy=MIN_OCCUPANCY):
    import xml.etree.ElementTree as ET
    if not os.path.exists(edge_data_file):
        return []
    tree = ET.parse(edge_data_file)
    agg = {}
    for interval in tree.getroot().findall("interval"):
        for edge in interval.findall("edge"):
            eid = edge.get("id")
            occ = float(edge.get("occupancy", 0))
            agg.setdefault(eid, []).append(occ)
    result = [(eid, sum(v) / len(v)) for eid, v in agg.items()]
    result = [(eid, occ) for eid, occ in result if occ > min_occupancy]
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def pick_top_edges(edge_data_file, n, log_top=10):
    """Top n najbardziej obciążonych (niezerowych) krawędzi wg occupancy."""
    candidates = loaded_edges(edge_data_file)
    if not candidates:
        print(f"  BRAK obciążonych krawędzi w {edge_data_file}")
        return []

    print(f"\n  TOP {log_top} najbardziej obciążonych krawędzi:")
    print(f"  {'#':>3} {'ID':<28} {'Occupancy%':>12}")
    print("  " + "-" * 45)
    for i, (eid, occ) in enumerate(candidates[:log_top], 1):
        mark = "  <- wybrana" if i <= n else ""
        print(f"  {i:>3} {eid:<28} {occ:>12.2f}{mark}")

    return [eid for eid, _ in candidates[:n]]


def write_edge_results(edge_id, baseline_metric, rows):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{edge_id}.txt")

    pcts = [r["pct"] for r in rows]
    better = sum(1 for p in pcts if p < 0)
    worse  = sum(1 for p in pcts if p > 0)
    avg_pct = sum(pcts) / len(pcts) if pcts else 0.0
    n = len(rows)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"KRAWĘDŹ USUNIĘTA: {edge_id}\n")
        f.write(f"Baseline metryka: {baseline_metric:.1f}\n")
        f.write("=" * 60 + "\n")
        f.write(f"{'seed':>6} {'metryka':>15} {'różnica':>14} {'%':>9}\n")
        f.write("-" * 60 + "\n")
        for r in rows:
            f.write(f"{r['seed']:>6} {r['scenario']:>15.1f} "
                    f"{r['diff']:>+14.1f} {r['pct']:>+8.3f}%\n")
        f.write("-" * 60 + "\n")
        f.write(f"Średnia zmiana:   {avg_pct:+.3f}%\n")
        f.write(f"Polepszyło:       {better}/{n}\n")
        f.write(f"Pogorszyło:       {worse}/{n}\n")
        braess = better == n and n > 0
        f.write(f"BRAESS (wszystkie polepszyły): {'TAK' if braess else 'NIE'}\n")
    print(f"  Zapisano wyniki: {path}")


def stage_baseline():
    print("\n=== ETAP 1: BASELINE (per seed) ===")
    for seed in SEEDS:
        seed = str(seed)
        print(f"\n  -- seed {seed} --")
        initial = f"data/initial_trips_seed{seed}.xml"
        flow = f"data/flow_trips_seed{seed}.xml"
        routes = f"data/routes_seed{seed}.rou.xml"
        baseline_dir = f"output/baseline_seed{seed}"

        print("  Generowanie tripów startowych...")
        generate_initial_trips(NET_FILE, initial, seed=seed)
        print("  Generowanie tripów flow...")
        generate_flow_trips(NET_FILE, flow, seed=seed)
        print("  Generowanie tras (duarouter)...")
        generate_routes(NET_FILE, initial, flow, routes, seed=seed)
        print("  Uruchamianie symulacji baseline...")
        run_simulation(NET_FILE, routes, baseline_dir, seed=seed)
        print(f"  Gotowe. Wyniki w: {baseline_dir}")


def stage_pick():
    print("\n=== ETAP 2: WYBÓR KANDYDATÓW (TOP) ===")
    edge_data = f"output/baseline_seed{SEEDS[0]}/edge_data.xml"
    edges = pick_top_edges(edge_data, TOP_N)
    print(f"  Top {TOP_N} obciążonych krawędzi: {edges}")
    return edges


def run_scenario(edge_id, seed):
    """Usuwa krawędź, generuje trasy, symuluje i zwraca metrykę dla 1 seeda."""
    seed = str(seed)
    safe_id = edge_id.replace("-", "neg_").replace("#", "_")
    net_file = f"net_xml/no_{safe_id}.net.xml"
    routes_file = f"data/routes_no_{safe_id}_seed{seed}.rou.xml"
    output_dir = f"output/no_{safe_id}_seed{seed}"

    if not os.path.exists(net_file):
        create_network_without_edge(edge_id, net_file)

    initial = f"data/initial_trips_seed{seed}.xml"
    flow = f"data/flow_trips_seed{seed}.xml"
    if not os.path.exists(initial):
        generate_initial_trips(NET_FILE, initial, seed=seed)
    if not os.path.exists(flow):
        generate_flow_trips(NET_FILE, flow, seed=seed)

    generate_routes_modified(net_file, initial, flow, routes_file, seed=seed)
    run_simulation(net_file, routes_file, output_dir, seed=seed)

    baseline_dir = f"output/baseline_seed{seed}"
    total_trips = count_completed(baseline_dir)
    return compute_metric(output_dir, total_trips)


def stage_run(candidates):
    print("\n=== ETAP 3: TEST BRAESSA (multi-seed) + ZAPIS ===")
    for edge_id in candidates:
        print(f"\n--- Krawędź: {edge_id} ---")
        rows = []
        baseline_for_print = None
        for seed in SEEDS:
            baseline_dir = f"output/baseline_seed{seed}"
            if not os.path.exists(baseline_dir):
                print(f"  BRAK baseline dla seed {seed} ({baseline_dir}) — pomijam")
                continue
            total_trips = count_completed(baseline_dir)
            baseline_metric = compute_metric(baseline_dir, total_trips)
            baseline_for_print = baseline_metric

            scenario_metric = run_scenario(edge_id, seed)
            diff = scenario_metric - baseline_metric
            pct = (diff / baseline_metric * 100) if baseline_metric else 0.0
            sign = "GORZEJ" if diff > 0 else "LEPIEJ"
            print(f"  seed {seed}: {diff:+.1f}s ({pct:+.3f}%) {sign}")
            rows.append({"seed": seed, "scenario": scenario_metric,
                         "diff": diff, "pct": pct})
            append_csv({
                "test": "single", "label": edge_id, "edges": edge_id,
                "n_edges": 1, "seed": seed,
                "baseline_metric": f"{baseline_metric:.1f}",
                "scenario_metric": f"{scenario_metric:.1f}",
                "diff": f"{diff:+.1f}", "pct": f"{pct:+.4f}", "verdict": sign,
            })

        if rows:
            write_edge_results(edge_id, baseline_for_print, rows)


def build_ranking():
    """Z CSV testu bazowego buduje ranking krawędzi wg średniego %.

    Zwraca (best, worst): listy edge_id posortowane od najlepszego/najgorszego."""
    if not os.path.exists(RESULTS_CSV):
        print(f"  BRAK {RESULTS_CSV} - najpierw odpal test bazowy (single).")
        return [], []
    agg = {}
    with open(RESULTS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["test"] != "single":
                continue
            agg.setdefault(r["edges"], []).append(float(r["pct"]))
    means = [(eid, sum(v) / len(v)) for eid, v in agg.items()]
    means.sort(key=lambda x: x[1])           # rosnąco po %
    best = [eid for eid, _ in means[:N_BEST]]          # najniższy % = najlepsze
    worst = [eid for eid, _ in means[-N_WORST:][::-1]]  # najwyższy % = najgorsze
    return best, worst


def run_combo(test, label, edges, seed=FIXED_SEED):
    """Usuwa zestaw krawędzi, symuluje, liczy metrykę i pisze do CSV."""
    seed = str(seed)
    safe = label.replace("-", "neg_").replace("#", "_")
    net_file = f"net_xml/combo_{safe}.net.xml"
    routes_file = f"data/combo_{safe}_seed{seed}.rou.xml"
    output_dir = f"output/combo_{safe}_seed{seed}"

    print(f"\n--- [{test}] {label}: {edges} ---")
    create_network_without_edges(edges, net_file)

    initial = f"data/initial_trips_seed{seed}.xml"
    flow = f"data/flow_trips_seed{seed}.xml"
    if not os.path.exists(initial):
        generate_initial_trips(NET_FILE, initial, seed=seed)
    if not os.path.exists(flow):
        generate_flow_trips(NET_FILE, flow, seed=seed)

    generate_routes_modified(net_file, initial, flow, routes_file, seed=seed)
    run_simulation(net_file, routes_file, output_dir, seed=seed)

    baseline_dir = f"output/baseline_seed{seed}"
    total_trips = count_completed(baseline_dir)
    baseline_metric = compute_metric(baseline_dir, total_trips)
    scenario_metric = compute_metric(output_dir, total_trips)
    diff = scenario_metric - baseline_metric
    pct = (diff / baseline_metric * 100) if baseline_metric else 0.0
    sign = "GORZEJ" if diff > 0 else "LEPIEJ"
    print(f"  vs BASELINE: {diff:+.1f}s ({pct:+.3f}%) {sign}")

    append_csv({
        "test": test, "label": label, "edges": ";".join(edges),
        "n_edges": len(edges), "seed": seed,
        "baseline_metric": f"{baseline_metric:.1f}",
        "scenario_metric": f"{scenario_metric:.1f}",
        "diff": f"{diff:+.1f}", "pct": f"{pct:+.4f}", "verdict": sign,
    })


def unique_random_pairs(pool, n_pairs, rng):
    """Losuje n_pairs UNIKALNYCH par (bez powtórzeń całych par) z puli."""
    seen = set()
    pairs = []
    attempts = 0
    max_attempts = n_pairs * 50
    while len(pairs) < n_pairs and attempts < max_attempts:
        attempts += 1
        pair = tuple(sorted(rng.sample(pool, 2)))
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(list(pair))
    return pairs


def stage_run_best(best):
    print("\n=== TEST: NAJLEPSZE (top2, potem 2 losowe x9) ===")
    rng = random.Random(COMBO_RNG)
    run_combo("best", "best_1", best[:2])          # zestaw 1 = czyste top2
    pool = best[:N_BEST]
    for i, pair in enumerate(unique_random_pairs(pool, 9, rng), 2):
        run_combo("best", f"best_{i}", pair)


def stage_run_worst(worst):
    print("\n=== TEST: NAJGORSZE (top2, potem 2 losowe x9) ===")
    rng = random.Random(COMBO_RNG)
    run_combo("worst", "worst_1", worst[:2])       # zestaw 1 = czyste top2
    pool = worst[:N_WORST]
    for i, pair in enumerate(unique_random_pairs(pool, 9, rng), 2):
        run_combo("worst", f"worst_{i}", pair)


def stage_run_mix(best, worst):
    print("\n=== TEST: MIX (1 lepszy + 1 gorszy) x10 ===")
    rng = random.Random(COMBO_RNG)
    seen = set()
    i = 0
    attempts = 0
    while i < 10 and attempts < 500:
        attempts += 1
        edges = (rng.choice(best), rng.choice(worst))
        if edges in seen:
            continue
        seen.add(edges)
        i += 1
        run_combo("mix", f"mix_{i}", list(edges))


def stage_run_rand3(top30):
    print("\n=== TEST: LOSOWE 3 (z top30) x10 ===")
    rng = random.Random(COMBO_RNG)
    seen = set()
    i = 0
    attempts = 0
    while i < 10 and attempts < 500:
        attempts += 1
        triple = tuple(sorted(rng.sample(top30, 3)))
        if triple in seen:
            continue
        seen.add(triple)
        i += 1
        run_combo("rand3", f"rand3_{i}", list(triple))


if __name__ == "__main__":

    # --- test bazowy (single-edge, multi-seed) ---
    STAGE_BASELINE = False
    STAGE_PICK     = True
    STAGE_RUN      = False

    # --- testy kombinacji (multi-edge, FIXED_SEED) ---
    STAGE_BEST     = True
    STAGE_WORST    = True
    STAGE_MIX      = True
    STAGE_RAND3    = True

    if STAGE_BASELINE:
        stage_baseline()

    candidates = None
    if STAGE_PICK:
        candidates = stage_pick()

    if STAGE_RUN and candidates is not None:
        stage_run(candidates)

    if STAGE_BEST or STAGE_WORST or STAGE_MIX or STAGE_RAND3:
        best, worst = build_ranking()
        top30 = candidates if candidates else (best[:N_BEST] + worst[:N_WORST])
        print(f"\n  Pula best({len(best)}): {best}")
        print(f"  Pula worst({len(worst)}): {worst}")

        if STAGE_BEST:
            stage_run_best(best)
        if STAGE_WORST:
            stage_run_worst(worst)
        if STAGE_MIX:
            stage_run_mix(best, worst)
        if STAGE_RAND3:
            stage_run_rand3(top30)
