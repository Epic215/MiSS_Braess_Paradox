import subprocess
import os

def create_network_without_edge(input_net, output_net, edge_id):
    import subprocess
    os.makedirs(os.path.dirname(output_net), exist_ok=True)
    subprocess.run([
        "netconvert",
        "--sumo-net-file", input_net,
        "--output-file", output_net,
        "--remove-edges.explicit", edge_id
    ], check=True)
    print(f"Zapisano: {output_net}")

def generate_trips(net_file, trips_file):
    subprocess.run([
        "python", r"C:\Program Files (x86)\Eclipse\Sumo\tools\randomTrips.py",
        "-n", net_file,
        "-o", trips_file,
        "--edge-type-file", "config/types_weights.txt",
        "--fringe-factor", "3",
        "--period", "1",
        "--begin", "0",
        "--end", "7200",
        "--seed", "42",
        "--allow-fringe",
    ], check=True)

def generate_routes(net_file, trips_file, routes_file):
    os.makedirs(os.path.dirname(routes_file), exist_ok=True)
    subprocess.run([
        "duarouter",
        "-n", net_file,
        "--route-files", trips_file,
        "-o", routes_file,
        "--ignore-errors",
        "--weights.random-factor", "1",
        "--seed", "42",
        "--remove-loops"
    ], check=True)

def run_sumo(net_file, routes_file, output_dir, edge_data_add):
    subprocess.run([
        "sumo",
        "-n", net_file,
        "-r", routes_file,
        "--begin", "0",
        "--end", "86400",
        "--quit-on-end",
        "--ignore-route-errors",
        "--max-depart-delay", "120",
        "--time-to-teleport", "120",
        "--step-length", "0.5",
        "--tripinfo-output", f"{output_dir}/tripinfo.xml",
        "--tripinfo-output.write-unfinished",
        "--summary-output", f"{output_dir}/summary.xml",
        "--statistic-output", f"{output_dir}/statistics.xml",
        "--additional-files", edge_data_add,
        "--no-step-log",
        "--vehroute-output", f"{output_dir}/vehroutes.xml",
        "--vehroute-output.incomplete"
    ], check=True)

if __name__ == "__main__":
    net_file      = "net_xml/big_fragment_krakow_without_edge.net.xml"
    trips_file    = "output/trips_fixed.trips.xml"
    output_dir    = "output/krakow_sim_without_edge"
    routes_file   = f"{output_dir}/routes.rou.xml"
    edge_data_add = "config/edge_data_37830025#0.add.xml"

    print("[1/3] Generowanie tras...")
    generate_trips(net_file, trips_file)
    print("[2/3] Routing...")
    generate_routes(net_file, trips_file, routes_file)
    print("[3/3] Symulacja...")
    run_sumo(net_file, routes_file, output_dir, edge_data_add)
    print("Gotowe.")
    # create_network_without_edge("net_xml/big_fragment_krakow.net.xml", "net_xml/big_fragment_krakow_without_edge.net.xml", "37830025#0")

