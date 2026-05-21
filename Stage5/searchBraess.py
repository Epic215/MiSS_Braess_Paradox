import sumolib
from metrics import print_metrics, compute_metric, get_top_edges
from pipeline import *

SUMO_TOOLS    = r"C:\Program Files (x86)\Eclipse\Sumo\tools"
NET_FILE      = "net_xml/big_fragment_krakow_fixed.net.xml"
INITIAL_TRIPS = "data/initial_trips.xml"
FLOW_TRIPS    = "data/flow_trips.xml"
BASELINE_DIR  = "output/baseline"
TOP_N         = 3

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
    print_metrics(baseline_dir)
    baseline_metric = compute_metric(baseline_dir)

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

        print_metrics(output_dir)
        scenario_metric = compute_metric(output_dir)

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

if __name__ == "__main__":
    search_braess()