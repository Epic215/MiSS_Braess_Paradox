import xml.etree.ElementTree as ET
import os

SCENARIO_B = "output_A_pelna_siec"
SCENARIO_A = "output_B_bez_krawedzi"
PERIOD     = 900  # interwał edgeData w sekundach

def parse_tripinfo(tripinfo_file):
    if not os.path.exists(tripinfo_file):
        print(f"Brak pliku: {tripinfo_file}")
        return {}

    tree = ET.parse(tripinfo_file)
    root = tree.getroot()

    durations     = []
    waitings      = []
    timelosses    = []
    route_lengths = []

    for trip in root.findall("tripinfo"):
        durations.append(float(trip.get("duration", 0)))
        waitings.append(float(trip.get("waitingTime", 0)))
        timelosses.append(float(trip.get("timeLoss", 0)))
        route_lengths.append(float(trip.get("routeLength", 0)))

    if not durations:
        return {}

    completed = len(durations)
    return {
        "completed_trips":  completed,
        "total_duration":   sum(durations),
        "avg_duration":     sum(durations)     / completed,
        "avg_waiting":      sum(waitings)      / completed,
        "avg_timeloss":     sum(timelosses)    / completed,
        "total_timeloss":   sum(timelosses),
        "total_waiting":    sum(waitings),
        "avg_route_length": sum(route_lengths) / completed,
    }

def parse_summary(summary_file):
    if not os.path.exists(summary_file):
        print(f"Brak pliku: {summary_file}")
        return []

    tree = ET.parse(summary_file)
    root = tree.getroot()

    steps = []
    for step in root.findall("step"):
        steps.append({
            "time":    float(step.get("time", 0)),
            "running": int(step.get("running", 0)),
            "waiting": int(step.get("waiting", 0)),
            "ended":   int(step.get("ended", 0)),
            "speed":   float(step.get("meanSpeed", 0)),
        })
    return steps

def parse_edge_data(edge_data_file, period=PERIOD):
    if not os.path.exists(edge_data_file):
        print(f"Brak pliku: {edge_data_file}")
        return []

    tree = ET.parse(edge_data_file)
    root = tree.getroot()

    edges = []
    for interval in root.findall("interval"):
        begin = float(interval.get("begin", 0))
        end   = float(interval.get("end", 0))
        dur   = end - begin if end > begin else period

        for edge in interval.findall("edge"):
            entered = float(edge.get("entered", 0))
            flow    = entered / (dur / 3600)  # pojazdy/godzinę
            edges.append({
                "id":          edge.get("id"),
                "begin":       begin,
                "end":         end,
                "occupancy":   float(edge.get("occupancy", 0)),
                "density":     float(edge.get("density", 0)),
                "speed":       float(edge.get("speed", 0)),
                "waitingTime": float(edge.get("waitingTime", 0)),
                "entered":     entered,
                "flow_vph":    flow,
            })
    return edges

def analyze_edge_data(edge_data_file, top_n=20):
    edges = parse_edge_data(edge_data_file)
    if not edges:
        return []

    # agreguj po ID (suma po wszystkich interwałach)
    agg = {}
    for e in edges:
        eid = e["id"]
        if eid not in agg:
            agg[eid] = {"occupancy": 0, "density": 0, "speed": [],
                        "waitingTime": 0, "flow_vph": [], "count": 0}
        agg[eid]["occupancy"]   += e["occupancy"]
        agg[eid]["density"]     += e["density"]
        agg[eid]["speed"].append(e["speed"])
        agg[eid]["waitingTime"] += e["waitingTime"]
        agg[eid]["flow_vph"].append(e["flow_vph"])
        agg[eid]["count"]       += 1

    result = []
    for eid, v in agg.items():
        n = v["count"]
        result.append({
            "id":          eid,
            "occupancy":   v["occupancy"]   / n,
            "density":     v["density"]     / n,
            "speed":       sum(v["speed"])  / len(v["speed"]),
            "waitingTime": v["waitingTime"],
            "flow_vph":    sum(v["flow_vph"]) / len(v["flow_vph"]),
        })

    result.sort(key=lambda x: x["occupancy"], reverse=True)

    print(f"\n=== TOP {top_n} NAJBARDZIEJ ZATŁOCZONYCH KRAWĘDZI ===")
    print(f"{'ID':<30} {'Occupancy%':>10} {'Density':>10} {'Speed m/s':>10} {'Flow vph':>10} {'WaitTime':>10}")
    print("-" * 85)
    for e in result[:top_n]:
        print(f"{e['id']:<30} {e['occupancy']:>10.2f} {e['density']:>10.2f} "
              f"{e['speed']:>10.2f} {e['flow_vph']:>10.1f} {e['waitingTime']:>10.1f}")

    return result


def compare_scenarios(dir_b, dir_a):
    print("\n" + "="*60)
    print("PORÓWNANIE SCENARIUSZY")
    print("="*60)

    trip_b = parse_tripinfo(f"{dir_b}/tripinfo.xml")
    trip_a = parse_tripinfo(f"{dir_a}/tripinfo.xml")

    metrics = [
        ("Ukończone przejazdy",     "completed_trips"),
        ("TTT - suma czasów [s]",   "total_duration"),
        ("Śr. czas podróży [s]",    "avg_duration"),
        ("Śr. czas oczekiwania [s]","avg_waiting"),
        ("Śr. strata czasu [s]",    "avg_timeloss"),
        ("Łączna strata czasu [s]", "total_timeloss"),
        ("Łączne oczekiwanie [s]",  "total_waiting"),
        ("Śr. dł. trasy [m]",       "avg_route_length"),
    ]

    print(f"\n{'Metryka':<30} {'Pełna sieć':>15} {'Bez krawędzi':>15} {'Zmiana':>10}")
    print("-" * 75)

    for label, key in metrics:
        val_b = trip_b.get(key, 0)
        val_a = trip_a.get(key, 0)
        change = (val_a - val_b) / val_b * 100 if val_b > 0 else 0
        symbol = "✓" if change < 0 else "✗"
        print(f"{label:<30} {val_b:>15.2f} {val_a:>15.2f} {change:>+9.1f}% {symbol}")

    avg_b = trip_b.get("avg_duration", 0)
    avg_a = trip_a.get("avg_duration", 0)

    if avg_a < avg_b:
        improvement = (avg_b - avg_a) / avg_b * 100
        print(f"  Śr. czas podróży spadł o {improvement:.1f}%")
    else:
        degradation = (avg_a - avg_b) / avg_b * 100
        print(f"✗ Brak paradoksu — śr. czas podróży wzrósł o {degradation:.1f}%")

    # natężenie - top zakorkowane
    print("\n--- PEŁNA SIEĆ ---")
    analyze_edge_data(f"{dir_b}/edge_data.xml")
    print("\n--- BEZ KRAWĘDZI ---")
    analyze_edge_data(f"{dir_a}/edge_data.xml")


if __name__ == "__main__":
    compare_scenarios(SCENARIO_B, SCENARIO_A)