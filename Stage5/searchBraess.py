import sumolib
from metrics import print_metrics, compute_metric, get_top_edges, count_completed
from pipeline import *

SUMO_TOOLS    = r"C:\Program Files (x86)\Eclipse\Sumo\tools"
NET_FILE      = "net_xml/big_fragment_krakow_fixed.net.xml"
INITIAL_TRIPS = "data/initial_trips.xml"
FLOW_TRIPS    = "data/flow_trips.xml"
BASELINE_DIR  = "output/baseline"
TOP_N         = 3
SEEDS         = [144, 42, 200, 777, 1337]
TOP_EDGES     = ["475556403#1", "-21046520#1", "19844875#2"]

def find_related_edges(net_file, base_edge_id):
    net = sumolib.net.readNet(net_file, withInternal=False)
    related = []
    for edge in net.getEdges():
        eid = edge.getID()
        # dopasuj ID bazowe (np. 475556403 pasuje do 475556403#0, 475556403#1 itd.)
        base = base_edge_id.split("#")[0].lstrip("-")
        prefix = "-" if base_edge_id.startswith("-") else ""
        if eid == base_edge_id or eid.startswith(f"{prefix}{base}#"):
            related.append(eid)
    return related


def create_network_without_edge(base_edge_id, output_net):
    related = find_related_edges(NET_FILE, base_edge_id)
    edges_to_remove = ",".join(related) if related else base_edge_id
    print(f"  Usuwam krawędzie: {edges_to_remove}")
    subprocess.run([
        "netconvert",
        "--sumo-net-file", NET_FILE,
        "--remove-edges.explicit", edges_to_remove,
        "--output-file", output_net,
    ], check=True)


def search_braess(baseline_dir=BASELINE_DIR, top_n=TOP_N):
    print("=" * 60)
    print("WCZYTYWANIE WYNIKÓW BASELINE")
    print("=" * 60)
    total_trips = count_completed(baseline_dir)
    print_metrics(baseline_dir, total_trips)
    baseline_metric = compute_metric(baseline_dir, total_trips)

    top_edges = get_top_edges(baseline_dir, top_n)
    print(f"\nTop {top_n} kandydatów: {top_edges}")

    results = {}

    for edge_id in top_edges:
        safe_id = edge_id.replace("-", "neg_")
        net_file = f"net_xml/no_{safe_id}.net.xml"
        routes_file = f"data/routes_no_{safe_id}.rou.xml"
        output_dir = f"output/no_{safe_id}"

        print("\n" + "=" * 60)
        print(f"SCENARIUSZ: usunięcie krawędzi {edge_id}")
        print("=" * 60)

        print("Tworzę nową sieć...")
        create_network_without_edge(edge_id, net_file)

        print("Generuję trasy...")
        generate_routes_modified(net_file, INITIAL_TRIPS, FLOW_TRIPS, routes_file)

        print("Uruchamiam symulację...")
        run_simulation(net_file, routes_file, output_dir)

        print_metrics(output_dir, total_trips)
        scenario_metric = compute_metric(output_dir, total_trips)

        if baseline_metric and scenario_metric:
            diff = scenario_metric - baseline_metric
            pct = (diff / baseline_metric) * 100
            sign = "↑ GORZEJ" if diff > 0 else "↓ LEPIEJ"
            print(f"\n  vs BASELINE: {diff:+.1f}s ({pct:+.2f}%) {sign}")
            results[edge_id] = {"metric": scenario_metric, "diff": diff, "pct": pct}

    print("\n" + "=" * 60)
    print("PODSUMOWANIE")
    print("=" * 60)
    print(f"  {'Krawędź':<25} {'Metryka':>15} {'Różnica':>12} {'%':>8}")
    print("  " + "-" * 62)
    print(f"  {'BASELINE':<25} {baseline_metric:>15.1f}")
    for eid, r in results.items():
        print(f"  {eid:<25} {r['metric']:>15.1f} {r['diff']:>+12.1f} {r['pct']:>+7.2f}%")


def compare_results_seeded(seeds=SEEDS, edge_ids=TOP_EDGES):
    """Tylko porównuje gotowe wyniki dla każdego seeda - bez generowania."""
    all_results = {}

    for seed in seeds:
        baseline_dir = f"output/baseline_seed{seed}"
        print("\n" + "=" * 60)
        print(f"SEED: {seed}  —  BASELINE: {baseline_dir}")
        print("=" * 60)

        if not os.path.exists(baseline_dir):
            print(f"  BRAK FOLDERU BASELINE — pomijam seed {seed}")
            continue

        total_trips = count_completed(baseline_dir)
        baseline_metric = compute_metric(baseline_dir, total_trips)
        results = {}

        for edge_id in edge_ids:
            safe_id = edge_id.replace("-", "neg_")
            output_dir = f"output/no_{safe_id}_seed{seed}"

            if not os.path.exists(output_dir):
                print(f"  BRAK: {output_dir} — pomijam")
                continue

            scenario_metric = compute_metric(output_dir, total_trips)

            if baseline_metric and scenario_metric:
                diff = scenario_metric - baseline_metric
                pct = (diff / baseline_metric) * 100
                sign = "↑ GORZEJ" if diff > 0 else "↓ LEPIEJ"
                print(f"  {edge_id:<25} {diff:+.1f}s ({pct:+.2f}%) {sign}")
                results[edge_id] = {"metric": scenario_metric, "diff": diff, "pct": pct}

        all_results[seed] = {"baseline": baseline_metric, "results": results}

    print("\n" + "=" * 60)
    print("ZBIORCZE PODSUMOWANIE")
    print("=" * 60)
    for edge_id in edge_ids:
        diffs = [all_results[s]["results"].get(edge_id, {}).get("pct")
                 for s in seeds if s in all_results]
        diffs = [d for d in diffs if d is not None]
        if not diffs:
            continue
        avg = sum(diffs) / len(diffs)
        consistent = all(d < 0 for d in diffs) or all(d > 0 for d in diffs)
        print(
            f"  {edge_id:<25}  śr: {avg:+.2f}%  min: {min(diffs):+.2f}%  max: {max(diffs):+.2f}%  spójny: {'TAK' if consistent else 'NIE'}")

if __name__ == "__main__":
    compare_results_seeded()