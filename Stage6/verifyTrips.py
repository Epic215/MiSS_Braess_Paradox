import os
import xml.etree.ElementTree as ET


def load_routes(routes_file):
    """Zwraca {vehicle_id: [lista krawędzi trasy]} czytając strumieniowo.

    Gdy plik jest uszkodzony/ucięty (ParseError), zwraca to co udało się
    wczytać i wypisuje ostrzeżenie zamiast przerywać działanie."""
    routes = {}
    try:
        for _, elem in ET.iterparse(routes_file, events=("end",)):
            if elem.tag == "vehicle":
                veh_id = elem.get("id")
                route = elem.find("route")
                edges_attr = route.get("edges") if route is not None else None
                if veh_id is not None and edges_attr:
                    routes[veh_id] = edges_attr.split()
            if elem.tag in ("vehicle", "trip", "flow"):
                elem.clear()
    except ET.ParseError as e:
        print(f"  UWAGA: uszkodzony plik tras {routes_file} ({e}); "
              f"wczytano {len(routes)} tras")
    return routes


def endpoints(edges):
    """Para (start, koniec) z listy krawędzi."""
    return (edges[0], edges[-1])


def is_removed(edge, removed_edges):
    base = edge.split("#")[0].lstrip("-")
    for r in removed_edges:
        r_base = r.split("#")[0].lstrip("-")
        if base == r_base:
            return True
    return False


def verify(baseline_routes, scenario_routes, removed_edges=()):
    print("=" * 60)
    print("PORÓWNANIE TRAS (start, koniec)")
    print(f"  baseline:   {baseline_routes}")
    print(f"  scenariusz: {scenario_routes}")
    print(f"  usunięte:   {list(removed_edges) if removed_edges else '(brak)'}")
    print("=" * 60)

    if not os.path.exists(baseline_routes):
        print(f"BŁĄD: brak pliku baseline ({baseline_routes})")
        return False
    if not os.path.exists(scenario_routes):
        print(f"BŁĄD: brak pliku scenariusza ({scenario_routes})")
        return False

    base = load_routes(baseline_routes)
    scen = load_routes(scenario_routes)

    base_pairs = {endpoints(e) for e in base.values()}

    missing = []   # pary (start, koniec) ze scenariusza, których nie ma w baseline
    rerouted = 0   # ta sama para w obu, ale inny środek trasy

    base_full = {endpoints(e): e for e in base.values()}

    for veh_id, edges in scen.items():
        pair = endpoints(edges)
        if pair not in base_pairs:
            missing.append((veh_id, pair))
        else:
            if base_full.get(pair) != edges:
                rerouted += 1

    # ile tras w baseline ma start LUB koniec na usuniętej krawędzi -
    # te wiadomo, że repair (--repair.from / --repair.to) musiał przesunąć,
    # więc odejmujemy je od "spoza baseline"
    affected = 0
    if removed_edges:
        for edges in base.values():
            s, e = endpoints(edges)
            if is_removed(s, removed_edges) or is_removed(e, removed_edges):
                affected += 1

    missing_corrected = len(missing) - affected

    print("\n--- PODSUMOWANIE ---")
    print(f"  Tras w baseline:                      {len(base)}")
    print(f"  Tras w scenariuszu:                   {len(scen)}")
    print(f"  Unikalnych par (start,koniec) base:   {len(base_pairs)}")
    print(f"  Reroute (ta sama para, inny środek):  {rerouted}  [info]")
    print(f"  Pary ze scenariusza spoza baseline:   {len(missing)}")
    print(f"  Baseline ze start/koniec na usun.:    {affected}  [info]")
    print(f"  Spoza baseline po korekcie:           {missing_corrected}")

    if missing:
        print("\n--- TRASY SPOZA BASELINE (do 20) ---")
        print(f"  {'vehicle':<20} {'start':<22} {'koniec':<22}")
        for veh_id, (s, e) in missing[:20]:
            print(f"  {veh_id:<20} {s:<22} {e:<22}")
        if len(missing) > 20:
            print(f"  ... i {len(missing) - 20} więcej")

    ok = missing_corrected <= 0
    print("\nWYNIK:", "True (OK)" if ok else "False (NOK)")
    return ok


if __name__ == "__main__":
    BASELINE_ROUTES = "data/routes.rou.xml"
    SCENARIO_ROUTES = "data/routes_no_923392674.rou.xml"
    REMOVED_EDGES   = ["475556403"]

    verify(BASELINE_ROUTES, SCENARIO_ROUTES, REMOVED_EDGES)
