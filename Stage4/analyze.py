import xml.etree.ElementTree as ET
import os
import sys

PENALTY = 3600
PERIOD  = 900

def compute_metric(directory):
    tripinfo_file = f"{directory}/tripinfo.xml"
    summary_file  = f"{directory}/summary.xml"

    if not os.path.exists(tripinfo_file):
        print(f"Brak pliku: {tripinfo_file}")
        return None

    tree          = ET.parse(tripinfo_file)
    total_time    = 0
    completed     = 0
    not_completed = 0

    for trip in tree.getroot().findall("tripinfo"):
        arrival  = float(trip.get("arrival", "-1"))
        duration = float(trip.get("duration", 0))
        if arrival >= 0:
            total_time += duration
            completed  += 1
        else:
            total_time    += PENALTY
            not_completed += 1

    if os.path.exists(summary_file):
        steps     = parse_summary(summary_file)
        discarded = steps[-1]["discarded"] if steps else 0
        if discarded > 0:
            not_completed += discarded
            total_time    += discarded * PENALTY
            print(f"Odrzucone (max-depart-delay): {discarded}")

    print(f"Ukończone:    {completed}")
    print(f"Nieukończone: {not_completed} (kara: {PENALTY}s każdy)")
    print(f"METRYKA:      {total_time:.1f}s")
    return total_time


def parse_tripinfo(tripinfo_file):
    if not os.path.exists(tripinfo_file):
        print(f"Brak pliku: {tripinfo_file}")
        return {}

    tree  = ET.parse(tripinfo_file)
    trips = tree.getroot().findall("tripinfo")
    if not trips:
        return {}

    durations     = [float(t.get("duration",    0)) for t in trips]
    waitings      = [float(t.get("waitingTime",  0)) for t in trips]
    timelosses    = [float(t.get("timeLoss",      0)) for t in trips]
    route_lengths = [float(t.get("routeLength",  0)) for t in trips]
    n = len(durations)

    return {
        "completed_trips":  n,
        "avg_duration":     sum(durations)     / n,
        "avg_waiting":      sum(waitings)      / n,
        "avg_timeloss":     sum(timelosses)    / n,
        "total_timeloss":   sum(timelosses),
        "avg_route_length": sum(route_lengths) / n,
    }


def parse_summary(summary_file):
    if not os.path.exists(summary_file):
        print(f"Brak pliku: {summary_file}")
        return []

    tree  = ET.parse(summary_file)
    steps = []
    for step in tree.getroot().findall("step"):
        steps.append({
            "time":      float(step.get("time",      0)),
            "running":   int(step.get("running",     0)),
            "waiting":   int(step.get("waiting",     0)),
            "ended":     int(step.get("ended",       0)),
            "speed":     float(step.get("meanSpeed", 0)),
            "discarded": int(step.get("discarded",   0)),
        })
    return steps


def analyze_edge_data(edge_data_file, top_n=10):
    if not os.path.exists(edge_data_file):
        print(f"Brak pliku: {edge_data_file}")
        return

    tree = ET.parse(edge_data_file)
    agg  = {}

    for interval in tree.getroot().findall("interval"):
        begin = float(interval.get("begin", 0))
        end   = float(interval.get("end",   0))
        dur   = (end - begin) if end > begin else PERIOD
        for edge in interval.findall("edge"):
            eid     = edge.get("id")
            entered = float(edge.get("entered", 0))
            if eid not in agg:
                agg[eid] = {"occupancy": [], "speed": [], "waitingTime": 0, "flow_vph": []}
            agg[eid]["occupancy"].append(float(edge.get("occupancy", 0)))
            agg[eid]["speed"].append(float(edge.get("speed",     0)))
            agg[eid]["waitingTime"] += float(edge.get("waitingTime", 0))
            agg[eid]["flow_vph"].append(entered / (dur / 3600))

    result = [{
        "id":          eid,
        "occupancy":   sum(v["occupancy"]) / len(v["occupancy"]),
        "speed":       sum(v["speed"])     / len(v["speed"]),
        "waitingTime": v["waitingTime"],
        "flow_vph":    sum(v["flow_vph"])  / len(v["flow_vph"]),
    } for eid, v in agg.items()]

    result.sort(key=lambda x: x["occupancy"], reverse=True)

    print(f"\n  TOP {top_n} KANDYDATÓW DO USUNIĘCIA (najbardziej zatłoczone):")
    print(f"  {'ID':<30} {'Occupancy%':>10} {'Speed m/s':>10} {'Flow vph':>10} {'WaitTime':>10}")
    print("  " + "-" * 65)
    for e in result[:top_n]:
        print(f"  {e['id']:<30} {e['occupancy']:>10.2f} {e['speed']:>10.2f} "
              f"{e['flow_vph']:>10.1f} {e['waitingTime']:>10.1f}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "output/krakow_sim_without_edge"

    print("=" * 60)
    print(f"SCENARIUSZ: {directory}")
    print("=" * 60)

    print("\n--- METRYKA GŁÓWNA ---")
    compute_metric(directory)

    print("\n--- SZCZEGÓŁY ---")
    trip = parse_tripinfo(f"{directory}/tripinfo.xml")
    metrics = [
        ("Ukończone przejazdy",      "completed_trips"),
        ("Śr. czas podróży [s]",     "avg_duration"),
        ("Śr. czas oczekiwania [s]", "avg_waiting"),
        ("Śr. strata czasu [s]",     "avg_timeloss"),
        ("Łączna strata czasu [s]",  "total_timeloss"),
        ("Śr. dł. trasy [m]",        "avg_route_length"),
    ]
    for label, key in metrics:
        print(f"  {label:<30} {trip.get(key, 0):>15.2f}")

    print("\n--- SUMMARY ---")
    steps = parse_summary(f"{directory}/summary.xml")
    if steps:
        valid_speeds = [s["speed"] for s in steps if s["speed"] >= 0]
        avg_speed    = sum(valid_speeds) / len(valid_speeds) if valid_speeds else 0
        print(f"  Maks. pojazdów na sieci:    {max(s['running'] for s in steps)}")
        print(f"  Maks. oczekujących:         {max(s['waiting'] for s in steps)}")
        print(f"  Śr. prędkość [m/s]:         {avg_speed:.2f}")
        print(f"  Łącznie ukończonych:        {steps[-1]['ended']}")
        print(f"  Odrzucone:                  {steps[-1]['discarded']}")

    print("\n--- EDGE DATA ---")
    analyze_edge_data(f"{directory}/edge_data.xml")