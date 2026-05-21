# Paradoks Braessa – Etap 5
 
Etap 5 wprowadza pełną powtarzalność eksperymentów, automatyczne wykrywanie kandydatów i weryfikację statystyczną na wielu seedach.
 
---
 
## Różne testy konfiguracji
 
### 1. Gridlock na skrzyżowaniach
 
Pojazdy blokowały skrzyżowania wjeżdżając mimo braku miejsca po drugiej stronie. Testowano kolejno:
- `--ignore-junction-blocker` – parametr istnieje ale znany bug w SUMO powoduje że nie działa przy sygnalizacji świetlnej
- `jmIgnoreKeepClearTime="0"` w `config/vtype.add.xml` – miało zatrzymywać pojazdy przed skrzyżowaniem, brak efektu
- `--no-internal-links` – fizycznie usuwa przestrzeń wewnątrz skrzyżowania, pojazdy teleportują się przez nie co jest nierealistyczne
- `--time-to-teleport 30` – ostateczny kompromis, pojazdy które utknęły zbyt długo są teleportowane i liczone w metryce
- `--no-internal-links` przy generacji sieci przez `netconvert` – usuwa wewnętrzną geometrię skrzyżowań, pojazdy przechodzą przez nie płynnie bez możliwości blokowania; wynikiem jest plik `net_xml/big_fragment_krakow_fixed.net.xml` używany we wszystkich eksperymentach

Zastosowane rozwiązania pozwoliły ograniczyć wpływ gridlocku na wyniki symulacji, eliminując nierealistyczne korki i skupiając pomiar na rzeczywistym czasie przejazdu.
### 2. Nierównomierny ruch i dobór natężenia
 
Początkowo użyto `--insertion-density 10` (pojazdy/h/km drogi) żeby automatycznie dostosować ruch do rozmiaru sieci. W praktyce generowało zmienną liczbę pojazdów między uruchomieniami co utrudniało porównanie. Powrócono do `--period 0.5` z ustaloną liczbą pojazdów startowych `--flows 2000` co daje ~16400 pojazdów i stabilne wyniki między seedami.
 
### 3. Powtarzalność tras i --repair
 
Kluczowym wymogiem było używanie tych samych par źródło-cel dla baseline i scenariusza z usuniętą krawędzią. `randomTrips.py` generuje pary raz z danym seedem i te same pliki tripów trafiają do obu wywołań `duarouter`. Gdy krawędź jest usunięta z sieci, `duarouter` z `--repair` automatycznie szuka objazdu między tymi samymi punktami A i B — trasa jest inna ale para źródło-cel ta sama. Pojazdy których trasy nie da się naprawić są odrzucane i otrzymują karę w metryce.
 
---
 
## Struktura i uruchomienie
 
1. **[`pipeline.py`](pipeline.py)** – generuje tripy startowe i flow przez `randomTrips.py`, wyznacza trasy przez `duarouter`, uruchamia symulację SUMO. Funkcje przyjmują seed jako parametr co zapewnia pełną powtarzalność na każdym etapie.
2. **[`metrics.py`](metrics.py)** – parsuje `tripinfo.xml`, `summary.xml`, `edge_data.xml` i wypisuje metryki; wybiera top N krawędzi po occupancy jako kandydatów. Metryka główna to suma czasów przejazdu ukończonych podróży plus kara 3600s za każdy pojazd który nie dotarł do celu w czasie symulacji.
3. **[`searchBraess.py`](searchBraess.py)** – wczytuje wyniki baseline, automatycznie wybiera top 3 krawędzie, dla każdej tworzy nową sieć przez `netconvert` z uwzględnieniem wszystkich segmentów danej krawędzi, generuje trasy z `--repair` i porównuje metryki z baseline.
4. **[`runDifferentSeeds.py`](runDifferentSeeds.py)** – odpala pełny pipeline dla każdego seeda z listy, zbiera wyniki i wypisuje zbiorcze podsumowanie ze średnią zmianą i spójnością kierunku między seedami.
Wyniki zapisywane do [`output/`](output/) w podfolderach `baseline_seedXXX` i `no_<edge>_seedXXX`.
 
---
 
## Wyniki i wnioski
 
Eksperymenty przeprowadzono dla 5 seedów (144, 42, 200, 777, 1337), każdorazowo ~16400 pojazdów na symulację 7200s. Top 3 kandydaci wybrani z baseline po occupancy:
 
| Krawędź | Śr. zmiana | Min | Max | Weryfikacja między seedami |
|---|---|---|---|----------------------------|
| `475556403#1` | **-2.06%** | -2.99% | -0.39% | + monotonicznie ujemna     |
| `-21046520#1` | +1.62% | -1.76% | +3.95% | - niejednoznaczna          |
| `19844875#2` | -0.28% | -2.37% | +1.65% | - niejednoznaczna          |
 
Krawędź `475556403#1` jako jedyna wykazuje spójny kierunek poprawy we wszystkich seedach ze średnią -2.06% — jest najsilniejszym kandydatem na paradoks Braessa w tej sieci. Pozostałe dwie krawędzie wykazują niespójne wyniki między seedami co wskazuje na szum symulacji a nie rzeczywisty efekt Braessa.
 
---
 
## Cele na ostatni etap
 
- Dłuższa symulacja z różnym natężeniem ruchu żeby sprawdzić przy jakim poziomie zatłoczenia efekt jest najsilniejszy
- Zwiększenie liczby seedów dla silniejszej weryfikacji statystycznej
- Eksperymenty z parametrami generowania ruchu w celu zwiększenia realizmu symulacji miejskiej