import os
import subprocess
from pipeline import generate_initial_trips, generate_flow_trips, generate_routes, generate_routes_modified, \
    run_simulation
from metrics import compute_metric, print_metrics
from searchBraess import create_network_without_edge

NET_FILE = "net_xml/big_fragment_krakow_fixed.net.xml"

SEEDS = [144, 42, 200, 777, 1337]
TOP_EDGES = ["475556403#1", "-21046520#1", "19844875#2"]


def run_experiment(seed):
    print("\n" + "=" * 60)
    print(f"SEED: {seed}")
    print("=" * 60)

    initial_trips = f"data/initial_trips_seed{seed}.xml"
    flow_trips = f"data/flow_trips_seed{seed}.xml"
    routes_file = f"data/routes_seed{seed}.rou.xml"
    baseline_dir = f"output/baseline_seed{seed}"

    print("Generowanie tripów startowych...")
    generate_initial_trips(NET_FILE, initial_trips, seed = str(seed))

    print("Generowanie tripów flow...")
    generate_flow_trips(NET_FILE, flow_trips, seed = str(seed))

    print("Generowanie tras (baseline)...")
    generate_routes(NET_FILE, initial_trips, flow_trips, routes_file, seed = str(seed))

    print("Symulacja baseline...")
    run_simulation(NET_FILE, routes_file, baseline_dir, seed = str(seed))

    print_metrics(baseline_dir)
    baseline_metric = compute_metric(baseline_dir)

    results = {}

    for edge_id in TOP_EDGES:
        safe_id = edge_id.replace("-", "neg_")
        net_file = f"net_xml/no_{safe_id}.net.xml"
        routes_mod = f"data/routes_no_{safe_id}_seed{seed}.rou.xml"
        output_dir = f"output/no_{safe_id}_seed{seed}"

        print(f"\n--- Krawędź: {edge_id} ---")

        if not os.path.exists(net_file):
            print("Tworzę nową sieć...")
            create_network_without_edge(edge_id, net_file)

        print("Generuję trasy...")
        generate_routes_modified(net_file, initial_trips, flow_trips, routes_mod, seed = str(seed))

        print("Uruchamiam symulację...")
        run_simulation(net_file, routes_mod, output_dir, seed = str(seed))

        scenario_metric = compute_metric(output_dir)

        if baseline_metric and scenario_metric:
            diff = scenario_metric - baseline_metric
            pct = (diff / baseline_metric) * 100
            sign = "↑ GORZEJ" if diff > 0 else "↓ LEPIEJ"
            print(f"  vs BASELINE: {diff:+.1f}s ({pct:+.2f}%) {sign}")
            results[edge_id] = {"metric": scenario_metric, "diff": diff, "pct": pct}

    print(f"\n--- PODSUMOWANIE seed={seed} ---")
    print(f"  {'Krawędź':<25} {'Metryka':>15} {'Różnica':>12} {'%':>8}")
    print("  " + "-" * 62)
    print(f"  {'BASELINE':<25} {baseline_metric:>15.1f}")
    for eid, r in results.items():
        print(f"  {eid:<25} {r['metric']:>15.1f} {r['diff']:>+12.1f} {r['pct']:>+7.2f}%")

    return baseline_metric, results


if __name__ == "__main__":
    all_results = {}
    for seed in SEEDS:
        baseline, results = run_experiment(seed)
        all_results[seed] = {"baseline": baseline, "results": results}

    print("\n" + "=" * 60)
    print("ZBIORCZE PODSUMOWANIE WSZYSTKICH SEEDÓW")
    print("=" * 60)
    for edge_id in TOP_EDGES:
        print(f"\nKrawędź: {edge_id}")
        diffs = [all_results[s]["results"].get(edge_id, {}).get("pct") for s in SEEDS]
        diffs = [d for d in diffs if d is not None]
        if diffs:
            avg = sum(diffs) / len(diffs)
            print(f"  Średnia zmiana: {avg:+.2f}%")
            print(f"  Min: {min(diffs):+.2f}%  Max: {max(diffs):+.2f}%")
            consistent = all(d < 0 for d in diffs) or all(d > 0 for d in diffs)
            print(f"  Spójny kierunek: {'TAK' if consistent else 'NIE'}")