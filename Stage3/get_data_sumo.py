import requests
import subprocess
import os
import sumolib

BBOX = (50.05890, 19.90199, 50.07659, 19.92877)  # (south, west, north, east)
OSM_FILE = "osm/big_fragment_krakow.osm"
NET_FILE        = "net_xml/big_fragment_krakow.net.xml"

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

def fetch_osm(bbox, output_file):
    south, west, north, east = bbox

    query = f"""
[out:xml][timeout:100];
(
  way["highway"]
    ["highway"!="footway"]
    ["highway"!="pedestrian"]
    ["highway"!="path"]
    ["highway"!="cycleway"]
    ["highway"!="steps"]
    ({south},{west},{north},{east});
  node["highway"="traffic_signals"]
    ({south},{west},{north},{east});
)->.roads;
(.roads;>;)->.all;
.all out meta;
"""

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    headers = {"User-Agent": "SUMO-OSM-Fetcher/1.0"}

    for server in OVERPASS_SERVERS:
        print(f"Trying: {server}")
        try:
            response = requests.post(
                server,
                data={"data": query},
                headers=headers,
                timeout=120
            )
            response.raise_for_status()

            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"Saved: {output_file} ({len(response.content) // 1024} KB)")
            return

        except requests.exceptions.HTTPError as e:
            print(f"Failed: {e}")
        except requests.exceptions.Timeout:
            print(f"Timeout on: {server}")

    print("All servers failed.")

def convert_to_sumo(osm_file, net_file):
    os.makedirs(os.path.dirname(net_file), exist_ok=True)

    print("Converting OSM to SUMO network...")
    cmd = [
        "netconvert",
        "--osm-files",             osm_file,
        "--output-file",           net_file,
        "--remove-edges.isolated",
        "--tls.guess-signals",     "true",
        "--tls.join",              "true",
        "--junctions.join",        "true",
        "--no-turnarounds",        "true",
        "--geometry.remove",       "true",
        "--osm.sidewalks",         "false",
        "--osm.crossings",         "false",
        "--keep-edges.by-vclass",  "passenger",
        "--keep-edges.components", "1",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Saved: {net_file}")
        if result.stderr.strip():
            warnings = [l for l in result.stderr.splitlines() if "Warning" in l]
            print(f"  Warnings: {len(warnings)}")
    else:
        print("netconvert error:")
        print(result.stderr)


def analyze_network(net_file):
    net = sumolib.net.readNet(net_file)
    edges = net.getEdges()
    print(f"Łączna liczba krawędzi: {len(edges)}")

    # Znajdź wszystkie komponenty
    edge_map = {e.getID(): e for e in edges}
    visited = set()
    components = []

    for edge in edges:
        if edge.getID() in visited:
            continue
        # BFS od tej krawędzi
        comp = set()
        queue = [edge]
        comp.add(edge.getID())
        while queue:
            e = queue.pop()
            neighbors = list(e.getOutgoing()) + list(e.getIncoming())
            for neighbor in neighbors:
                if neighbor.getID() not in comp:
                    comp.add(neighbor.getID())
                    queue.append(neighbor)
        components.append(comp)
        visited.update(comp)

    components.sort(key=len, reverse=True)
    print(f"Liczba komponentów:       {len(components)}")
    print(f"Największy komponent:     {len(components[0])} krawędzi ({len(components[0])/len(edges)*100:.1f}%)")
    if len(components) > 1:
        print(f"Drugi co do wielkości:   {len(components[1])} krawędzi")
    print(f"Singleton-komponenty:    {sum(1 for c in components if len(c) == 1)}")

def preview_network(net_file):
    print("Opening SUMO network preview...")
    cmd = ["sumo-gui", "--net-file", net_file]
    subprocess.Popen(cmd)

convert_to_sumo(OSM_FILE, NET_FILE)
analyze_network(NET_FILE)