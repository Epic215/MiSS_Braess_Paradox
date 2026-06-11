"""Stage6 - statystyki i ekstrema z wyników skanu (output/results.csv).

CSV ma kolumny: test, label, edges, n_edges, seed, baseline_metric,
scenario_metric, diff, pct, verdict.
  test = "single"  -> bazowy test single-edge (wiele seedów),
  test = "best"/"worst"/"mix"/"rand3" -> testy kombinacji (FIXED_SEED).

Tutaj:
  - dla "single": agregacja per krawędź (średnia %, ile polepszyło, BRAESS),
  - dla testów kombinacji: średnia % i ekstrema per test,
  - ekstrema: najlepszy (najsilniejszy Braess) i najgorszy wynik,
  - zmiany start/koniec tras (ile pojazdów ma inny start/koniec po reroute),
  - wykresy: scatter (rozrzut per seed) i słupki średnia ± min/max.

EKSTREMA:
  pct < 0 -> usunięcie POPRAWIŁO ruch (kandydat na paradoks Braessa)
  pct > 0 -> usunięcie POGORSZYŁO ruch
"""

import os
import csv
import statistics

from verifyTrips import load_routes, endpoints

RESULTS_CSV = "output/results.csv"
PLOTS_DIR   = "output/plots"

# seedy testu bazowego (do porównania tras start/koniec)
SEEDS = [144, 42, 200, 777, 1337, 2024, 7, 99]


def safe_id(edge_id):
    return edge_id.replace("-", "neg_").replace("#", "_")


def count_endpoint_changes(edge_id, seed):
    """Porównuje trasy baseline vs scenariusz (per pojazd) dla danej krawędzi/seeda.

    Zwraca dict z liczbą pojazdów: ten sam start+koniec, zmieniony start,
    zmieniony koniec, zmienione oba, brak w scenariuszu."""
    base_routes = f"data/routes_seed{seed}.rou.xml"
    scen_routes = f"data/routes_no_{safe_id(edge_id)}_seed{seed}.rou.xml"
    if not (os.path.exists(base_routes) and os.path.exists(scen_routes)):
        return None

    base = load_routes(base_routes)
    scen = load_routes(scen_routes)

    same = start_ch = end_ch = both_ch = missing = 0
    for veh_id, b_edges in base.items():
        s_edges = scen.get(veh_id)
        if s_edges is None:
            missing += 1
            continue
        bs, be = endpoints(b_edges)
        ss, se = endpoints(s_edges)
        if bs == ss and be == se:
            same += 1
        elif bs != ss and be != se:
            both_ch += 1
        elif bs != ss:
            start_ch += 1
        else:
            end_ch += 1
    return {"same": same, "start": start_ch, "end": end_ch,
            "both": both_ch, "missing": missing,
            "total": len(base)}


def load_csv(path):
    """Wczytuje CSV -> lista dictów z wartościami liczbowymi."""
    rows = []
    if not os.path.exists(path):
        print(f"BŁĄD: brak pliku {path}")
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                r["pct"] = float(r["pct"])
                r["diff"] = float(r["diff"])
                r["seed"] = int(r["seed"])
            except (ValueError, KeyError):
                continue
            rows.append(r)
    return rows


def aggregate_single(rows):
    """Agreguje test 'single' per krawędź -> dict {edge, seeds, pcts}."""
    agg = {}
    for r in rows:
        if r["test"] != "single":
            continue
        agg.setdefault(r["edges"], {"seeds": [], "pcts": []})
        agg[r["edges"]]["seeds"].append(r["seed"])
        agg[r["edges"]]["pcts"].append(r["pct"])
    return [{"edge": e, **v} for e, v in agg.items() if v["pcts"]]


def stage_stats(rows):
    print("\n=== STATYSTYKI (single) ===")
    data = aggregate_single(rows)
    if data:
        summary = []
        for d in data:
            n = len(d["pcts"])
            better = sum(1 for p in d["pcts"] if p < 0)
            summary.append({"edge": d["edge"], "avg": statistics.mean(d["pcts"]),
                            "better": better, "n": n})
        summary.sort(key=lambda s: s["avg"])

        print(f"  {'Krawędź':<24} {'śr %':>10} {'polepszyło':>12} {'BRAESS':>8}")
        print("  " + "-" * 56)
        for s in summary:
            braess = "TAK" if s["better"] == s["n"] else "NIE"
            print(f"  {s['edge']:<24} {s['avg']:>+9.3f}% "
                  f"{s['better']:>8}/{s['n']:<3} {braess:>8}")
        print("\n  --- EKSTREMA (single) ---")
        print(f"  NAJLEPSZA (Braess):  {summary[0]['edge']:<24} {summary[0]['avg']:+.3f}%")
        print(f"  NAJGORSZA:           {summary[-1]['edge']:<24} {summary[-1]['avg']:+.3f}%")

    # testy kombinacji
    for test in ("best", "worst", "mix", "rand3"):
        trows = [r for r in rows if r["test"] == test]
        if not trows:
            continue
        pcts = [r["pct"] for r in trows]
        better = sum(1 for p in pcts if p < 0)
        best_r  = min(trows, key=lambda r: r["pct"])
        worst_r = max(trows, key=lambda r: r["pct"])
        print(f"\n=== TEST: {test} ({len(trows)} zestawów) ===")
        print(f"  Średnia zmiana:   {statistics.mean(pcts):+.3f}%")
        print(f"  Polepszyło:       {better}/{len(pcts)}")
        print(f"  NAJLEPSZY zestaw: {best_r['label']:<12} {best_r['pct']:+.3f}%  [{best_r['edges']}]")
        print(f"  NAJGORSZY zestaw: {worst_r['label']:<12} {worst_r['pct']:+.3f}%  [{worst_r['edges']}]")


def stage_route_changes(rows):
    """Dla krawędzi z testu single liczy ile tras zmieniło start/koniec
    (sumarycznie po wszystkich dostępnych seedach)."""
    print("\n=== ZMIANY START/KONIEC TRAS (single) ===")
    edges = sorted({r["edges"] for r in rows if r["test"] == "single"})
    if not edges:
        print("  Brak danych single.")
        return

    print(f"  {'Krawędź':<22} {'sprawdz':>8} {'taki sam':>9} "
          f"{'start':>7} {'koniec':>7} {'oba':>6} {'brak':>7}")
    print("  " + "-" * 70)
    for edge_id in edges:
        agg = {"same": 0, "start": 0, "end": 0, "both": 0,
               "missing": 0, "total": 0, "seeds": 0}
        for seed in SEEDS:
            c = count_endpoint_changes(edge_id, seed)
            if c is None:
                continue
            for k in ("same", "start", "end", "both", "missing", "total"):
                agg[k] += c[k]
            agg["seeds"] += 1
        if agg["seeds"] == 0:
            print(f"  {edge_id:<22}  (brak plików tras)")
            continue
        changed = agg["start"] + agg["end"] + agg["both"]
        print(f"  {edge_id:<22} {agg['total']:>8} {agg['same']:>9} "
              f"{agg['start']:>7} {agg['end']:>7} {agg['both']:>6} "
              f"{agg['missing']:>7}   (zmienione start/koniec: {changed})")


def stage_plots(rows):
    print("\n=== WYKRESY ===")
    data = aggregate_single(rows)
    if not data:
        print("  Brak danych single do wykresów.")
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib niedostępny - pomijam wykresy.")
        return

    os.makedirs(PLOTS_DIR, exist_ok=True)

    # posortowane wg średniej (oś X = krawędzie, kategoryczna)
    items = sorted(data, key=lambda d: statistics.mean(d["pcts"]))
    edges = [d["edge"] for d in items]
    means = [statistics.mean(d["pcts"]) for d in items]
    mins  = [min(d["pcts"]) for d in items]
    maxs  = [max(d["pcts"]) for d in items]
    x = range(len(edges))

    best_i, worst_i = 0, len(edges) - 1   # po sortowaniu: skraj = ekstrema

    # --- 1. scatter: punkty per seed + średnia (bez łączenia linią) ---
    plt.figure(figsize=(9, 5))
    for i, d in enumerate(items):
        plt.scatter([i] * len(d["pcts"]), d["pcts"], color="gray", alpha=0.6, s=25)
    plt.scatter(x, means, color="black", marker="D", zorder=3, label="średnia")
    plt.scatter([best_i], [means[best_i]], color="green", marker="D", s=90,
                zorder=4, label="NAJLEPSZA (Braess)")
    plt.scatter([worst_i], [means[worst_i]], color="red", marker="D", s=90,
                zorder=4, label="NAJGORSZA")
    plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
    plt.xticks(list(x), edges, rotation=45, ha="right", fontsize=8)
    plt.ylabel("Zmiana metryki [%]")
    plt.title("Rozrzut per seed + średnia (ekstrema oznaczone)")
    plt.legend(fontsize=8)
    p1 = f"{PLOTS_DIR}/scatter_mean.png"
    plt.savefig(p1, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {p1}")

    # --- 2. słupki średniej z error barami (min-max po seedach) ---
    colors = ["green" if m < 0 else "tomato" for m in means]
    yerr = [[m - lo for m, lo in zip(means, mins)],
            [hi - m for m, hi in zip(means, maxs)]]
    plt.figure(figsize=(9, 5))
    plt.bar(x, means, yerr=yerr, capsize=4, color=colors, edgecolor="black")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.xticks(list(x), edges, rotation=45, ha="right", fontsize=8)
    plt.ylabel("Średnia zmiana metryki [%]")
    plt.title("Średnia ± min/max po seedach (zielone = Braess)")
    p2 = f"{PLOTS_DIR}/bars_mean_err.png"
    plt.savefig(p2, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {p2}")


if __name__ == "__main__":
    STAGE_STATS         = True
    STAGE_ROUTE_CHANGES = True
    STAGE_PLOTS         = True

    rows = load_csv(RESULTS_CSV)

    if STAGE_STATS:
        stage_stats(rows)
    if STAGE_ROUTE_CHANGES:
        stage_route_changes(rows)
    if STAGE_PLOTS:
        stage_plots(rows)
