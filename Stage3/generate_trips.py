import os
import random
import subprocess
import sumolib

NET_FILE    = "net_xml/big_fragment_krakow.net.xml"
TRIPS_FILE  = "net_xml/big_fragment_krakow.trips.xml"
ROUTES_FILE = "net_xml/big_fragment_krakow.rou.xml"

ROAD_WEIGHTS = {
    "highway.track":          1.0,
    "highway.primary":        50.0,
    "highway.primary_link":   40.0,
    "highway.secondary":      20.0,
    "highway.secondary_link": 15.0,
    "highway.tertiary":       10.0,
    "highway.tertiary_link":  10.0,
    "highway.service":         8.0,
    "highway.service|psv":     8.0,
    "highway.unclassified":    3.0,
    "highway.residential":     2.0,
    "highway.living_street":   1.0,
}

def analyze_network(net_file):
    net = sumolib.net.readNet(net_file)
    types = set(edge.getType() for edge in net.getEdges())
    print("--- Road types found in network ---")
    for t in sorted(types):
        print(f"  {t}")
    print("-----------------------------------\n")

def generate_trips(net_file, output_file, weights, num_trips=8000, duration=14400):
    random.seed(42)
    net = sumolib.net.readNet(net_file)

    weighted_edges = []
    edge_weights = []

    for edge in net.getEdges():
        w = weights.get(edge.getType(), 0.5)
        if edge.is_fringe():
            w *= 5.0
        weighted_edges.append(edge.getID())
        edge_weights.append(w)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    print(f"Generating {num_trips} trips...")
    with open(output_file, "w") as f:
        f.write("<trips>\n")
        i = 0
        attempts = 0
        while i < num_trips and attempts < num_trips * 5:
            src = random.choices(weighted_edges, weights=edge_weights)[0]
            dst = random.choices(weighted_edges, weights=edge_weights)[0]
            if src != dst:
                depart = round(random.uniform(0, duration), 1)
                f.write(f'    <trip id="veh{i}" depart="{depart}" from="{src}" to="{dst}"/>\n')
                i += 1
            attempts += 1
        f.write("</trips>\n")
    print(f"Saved: {output_file} ({i} trips)")

def run_duarouter(net_file, trips_file, routes_file):
    print("Running duarouter...")
    result = subprocess.run([
        "duarouter",
        "--net-file",    net_file,
        "--route-files", trips_file,
        "--output-file", routes_file,
        "--ignore-errors", "true",
        "--no-warnings",  "true",
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("duarouter error:")
        print(result.stderr)
        return

    # zlicz pominięte pojazdy z logu
    skipped = 0
    for line in result.stderr.splitlines():
        if "no connection" in line.lower() or \
           "unreachable" in line.lower() or \
           "disconnected" in line.lower() or \
           "no route found" in line.lower():
            skipped += 1

    # policz ile tras faktycznie wygenerowano
    try:
        with open(routes_file, "r") as f:
            content = f.read()
        generated = content.count("<vehicle ")
    except FileNotFoundError:
        generated = 0

    trips_total = sum(1 for _ in open(trips_file) if "<trip " in _)

    print(f"Saved: {routes_file}")
    print(f"  Total trips:     {trips_total}")
    print(f"  Routes generated: {generated}")
    print(f"  Skipped (no route / unreachable): {trips_total - generated}")

if __name__ == "__main__":
    analyze_network(NET_FILE)
    generate_trips(NET_FILE, TRIPS_FILE, ROAD_WEIGHTS)
    run_duarouter(NET_FILE, TRIPS_FILE, ROUTES_FILE)