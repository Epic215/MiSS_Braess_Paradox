import subprocess
import xml.etree.ElementTree as ET
import os
import sumolib

from Stage3.generate_trips import generate_trips, run_duarouter, ROAD_WEIGHTS

def run_scenario(scenario_name, net_file, routes_file, additional_file, remove_edge=None):
    output_dir = f"output_{scenario_name}"
    os.makedirs(output_dir, exist_ok=True)

    edge_data_file = f"{output_dir}/edge_data.xml"
    sumocfg_file   = f"{output_dir}/sim.sumocfg"
    additional_file_out = f"{output_dir}/edge_collector.add.xml"

    # zapisz plik kolektora
    with open(additional_file_out, "w") as f:
        f.write(f"""<additional>
    <edgeData id="edge_stats"
              file="{os.path.abspath(edge_data_file)}"
              begin="1800"
              end="60800"
              excludeEmpty="true"/>
</additional>""")

    # zapisz sumocfg
    with open(sumocfg_file, "w") as f:
        f.write(f"""<configuration>
    <input>
        <net-file value="{os.path.abspath(net_file)}"/>
        <route-files value="{os.path.abspath(routes_file)}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="60800"/>
    </time>
</configuration>""")

    cmd = [
        "sumo",
        "-c", sumocfg_file,
        "--additional-files", additional_file_out,
        "--tripinfo-output", f"{output_dir}/tripinfo.xml",
        "--summary-output", f"{output_dir}/summary.xml",
        "--duration-log.statistics", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "300"
    ]

    print(f"\n{'='*50}")
    print(f"Scenariusz: {scenario_name} {'(bez krawędzi: ' + remove_edge + ')' if remove_edge else '(pełna sieć)'}")
    print(f"{'='*50}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    # wyciągnij statystyki z logu
    stats = {}
    for line in (result.stdout + result.stderr).splitlines():
        if "Duration:" in line:
            stats["duration"] = line.strip()
        if "TimeLoss:" in line:
            stats["timeloss"] = line.strip()
        if "WaitingTime:" in line:
            stats["waitingtime"] = line.strip()
        if "Duration:" in line: stats["duration"] = line.strip()
        if "TimeLoss:" in line: stats["timeloss"] = line.strip()
        if "WaitingTime:" in line: stats["waitingtime"] = line.strip()
        if "Inserted:" in line: stats["inserted"] = line.strip()  # ile wjechało
        if "Arrived:" in line: stats["arrived"] = line.strip()  # ile dojechało
        if "Running:" in line: stats["running"] = line.strip()  # ile jeszcze jedzie

    for k, v in stats.items():
        print(f"  {v}")

    return edge_data_file, stats

def run_simulation(sumocfg, additional_file, output_file):
    print("Running SUMO simulation...")
    result = subprocess.run([
        "sumo",
        "-c", sumocfg,
        "--additional-files", additional_file,
        "--duration-log.statistics", "true",
        "--no-warnings", "true",
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("SUMO error:")
        print(result.stderr)
        return

    # wyciągnij średni czas podróży z logu
    for line in result.stderr.splitlines() + result.stdout.splitlines():
        if "Duration" in line or "WaitingTime" in line or "TimeLoss" in line:
            print(line.strip())

    print(f"Dane zapisane w: {output_file}")


def analyze_edge_data(edge_data_file, top_n=20):
    tree = ET.parse(edge_data_file)
    root = tree.getroot()

    edges = []
    for interval in root.findall("interval"):
        for edge in interval.findall("edge"):
            eid        = edge.get("id")
            density    = float(edge.get("density", 0))       # pojazdy/km
            occupancy  = float(edge.get("occupancy", 0))     # % czasu zajęta
            speed      = float(edge.get("speed", -1))        # średnia prędkość m/s
            volume     = float(edge.get("departed", 0)) + float(edge.get("arrived", 0))
            waittime   = float(edge.get("waitingTime", 0))   # czas oczekiwania

            edges.append({
                "id":        eid,
                "density":   density,
                "occupancy": occupancy,
                "speed_ms":  speed,
                "waittime":  waittime,
            })

    # posortuj po occupancy (najlepszy wskaźnik zatłoczenia)
    edges.sort(key=lambda x: x["occupancy"], reverse=True)

    print(f"\n=== TOP {top_n} NAJBARDZIEJ ZATŁOCZONYCH KRAWĘDZI ===")
    print(f"{'ID':<30} {'Occupancy%':>10} {'Density':>10} {'Speed m/s':>10} {'WaitTime':>10}")
    print("-" * 75)
    for e in edges[:top_n]:
        print(f"{e['id']:<30} {e['occupancy']:>10.2f} {e['density']:>10.2f} {e['speed_ms']:>10.2f} {e['waittime']:>10.2f}")

    return edges


def remove_edge_from_net(net_file, edge_id, output_file):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    print(f"Tworzę sieć bez krawędzi {edge_id}...")
    result = subprocess.run([
        "netconvert",
        "--sumo-net-file", net_file,
        "--output-file", output_file,
        "--remove-edges.explicit", edge_id,
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Saved: {output_file}")
    else:
        print(result.stderr)

NET_FILE    = "net_xml/big_fragment_krakow.net.xml"
ROUTES_FILE = "net_xml/big_fragment_krakow.rou.xml"
REMOVE_EDGE = "21931182#0"

if __name__ == "__main__":
    NET_FILE_A = "net_xml/big_fragment_krakow_without_edge.net.xml"
    TRIPS_FILE_A = "net_xml/big_fragment_krakow_without_edge.trips.xml"
    ROUTES_FILE_A = "net_xml/big_fragment_krakow_without_edge.rou.xml"

    remove_edge_from_net(NET_FILE, REMOVE_EDGE, NET_FILE_A)
    generate_trips(NET_FILE_A, TRIPS_FILE_A, ROAD_WEIGHTS, num_trips=8000)
    run_duarouter(NET_FILE_A, TRIPS_FILE_A, ROUTES_FILE_A)

    edge_file_b, _ = run_scenario("A_pelna_siec", NET_FILE, ROUTES_FILE, None)
    edge_file_a, _ = run_scenario("B_bez_krawedzi", NET_FILE_A, ROUTES_FILE_A, None)

    # Analiza
    analyze_edge_data(edge_file_b)
    analyze_edge_data(edge_file_a)