import subprocess
import os


def generate_initial_trips(net_file, trips_file, seed=144,flows="2000"):
    os.makedirs(os.path.dirname(trips_file), exist_ok=True)
    subprocess.run([
        "python", r"C:\Program Files (x86)\Eclipse\Sumo\tools\randomTrips.py",
        "-n", net_file,
        "-o", trips_file,
        "--edge-type-file", "config/types_weights.txt",
        "--trip-attributes", "departLane=\"best\"",
        "--begin", "0",
        "--end", "1",
        "--flows", flows,
        "--prefix", "start_",
        "--seed", seed,
        "--min-distance", "1500",
    ], check=True)

def generate_flow_trips(net_file, trips_file, seed="144"):
    os.makedirs(os.path.dirname(trips_file), exist_ok=True)
    subprocess.run([
        "python", r"C:\Program Files (x86)\Eclipse\Sumo\tools\randomTrips.py",
        "-n", net_file,
        "-o", trips_file,
        "--edge-type-file", "config/types_weights.txt",
        "--trip-attributes", "departLane=\"best\"",
        "--begin", "0",
        "--end", "7200",
        "--period", "0.5",
        "--prefix", "flow_",
        "--seed", seed,
        "--min-distance", "1500",
    ], check=True)

def generate_routes(net_file, initial_trips, flow_trips, routes_file, seed="144"):
    os.makedirs(os.path.dirname(routes_file), exist_ok=True)
    subprocess.run([
        "duarouter",
        "-n", net_file,
        "--route-files", f"{initial_trips},{flow_trips}",
        "-o", routes_file,
        "--ignore-errors",
        "--weights.random-factor", "4",
        "--seed", seed,
        "--remove-loops"
    ], check=True)

def generate_routes_modified(net_file, initial_trips, flow_trips, routes_file, seed="144"):
    os.makedirs(os.path.dirname(routes_file), exist_ok=True)
    subprocess.run([
        "duarouter",
        "-n", net_file,
        "--route-files", f"{initial_trips},{flow_trips}",
        "-o", routes_file,
        "--ignore-errors",
        "--repair", "true",
        "--repair.from", "true",
        "--repair.to", "true",
        "--weights.random-factor", "4",
        "--seed", seed,
        "--remove-loops",
    ], check=True)

def generate_routes2(net_file, initial_trips, flow_trips, routes_file):
    os.makedirs(os.path.dirname(routes_file), exist_ok=True)
    subprocess.run([
        "python", r"C:\Program Files (x86)\Eclipse\Sumo\tools\assign\duaIterate.py",
        "-n", net_file,
        "-t", f"{initial_trips},{flow_trips}",
        "-l", "10"
    ], check=True)

def run_simulation(net_file, routes_file, output_dir, seed="144"):
    os.makedirs(output_dir, exist_ok=True)
    subprocess.run([
        "sumo",
        "-n", net_file,
        "-r", routes_file,
        "--seed", seed,
        "--time-to-teleport", "30",
        "--additional-files", "config/vtype.add.xml",
        "--tripinfo-output", f"{output_dir}/tripinfo.xml",
        "--summary-output", f"{output_dir}/summary.xml",
        "--edgedata-output", f"{output_dir}/edge_data.xml",
        "--no-step-log",
        "--no-warnings",
    ], check=True)

if __name__ == "__main__":
    net_file      = "net_xml/big_fragment_krakow_fixed.net.xml"
    initial_trips = "data/initial_trips.xml"
    flow_trips    = "data/flow_trips.xml"
    routes_file   = "data/routes.rou.xml"
    output_dir    = "output/baseline"

    print("Generowanie tripów startowych...")
    generate_initial_trips(net_file, initial_trips)

    print("Generowanie tripów flow...")
    generate_flow_trips(net_file, flow_trips)

    print("Generowanie tras (duarouter)...")
    generate_routes(net_file, initial_trips, flow_trips, routes_file)

    print("Uruchamianie symulacji...")
    run_simulation(net_file, routes_file, output_dir)

    print("Gotowe! Wyniki w:", output_dir)