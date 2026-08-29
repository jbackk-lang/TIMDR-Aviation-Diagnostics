# TIMDR-Aviation-Diagnostics

Test transferu TIMDR-Core (kod 1:1 z `TIMDR-Earthquake-Core`) do domeny
diagnostyki lotniczej/silnikowej. Pytanie wyjściowe: czy `flow`/`twist`/
`anomalies` — pierwotnie zbudowane do sejsmologii — dają coś użytecznego
na realnych danych degradacji silnika turbowentylatorowego?

## Co jest tu realne, a co ograniczone przez środowisko

To repo powstało w środowisku (sandbox) z **zablokowanym dostępem
sieciowym do większości hostów z danymi publicznymi** (data.nasa.gov,
Kaggle, CWRU Bearing Data Center, NASA IMS/PCoE — wszystkie zwracają
`403 blocked-by-allowlist` na poziomie bash). Udało się:

- Pobrać **prawdziwe** dane NASA C-MAPSS (FD001, unit 1, kompletny
  przebieg run-to-failure — 192 cykle, 21 czujników, awaria w cyklu 192)
  przez narzędzie do pobierania stron (inny kanał sieciowy niż bash,
  akurat nieblokowany) z mirrora `github.com/mapr-demos/predictive-
  maintenance`. Plik `cmapss_fd001_unit1.txt` w tym repo to dokładna
  kopia tych 192 wierszy z oryginalnego `train_FD001.txt`.
- **NIE udało się** pobrać CWRU bearing dataset ani NASA IMS bearing
  run-to-failure — oba są dystrybuowane jako pliki binarne `.mat` z
  serwerów zablokowanych w tym środowisku, a narzędzie do pobierania
  stron nie potrafi sensownie odczytać treści binarnej.

**To jest test na n=1 (jeden silnik)** — potraktuj to jako demonstrację
metody i dowód, że dane są realne i poprawnie odczytane, NIE jako
walidację statystyczną (do tego potrzeba pełnego zbioru 100 silników,
patrz "Jak zrobić to porządnie" niżej).

## Metodologia (pre-rejestrowana w kodzie, patrz `test_engine_degradation.py`)

Czujnik do testu (sensor 4, T50 — temperatura na wylocie z LPT) dobrano
**obiektywnie**: spośród 21 czujników wybrano ten o największym przesunięciu
średniej między ostatnimi 30 a pierwszymi 30 cyklami (w jednostkach
odchylenia standardowego z początku życia). Ranking pokrył się 1:1 ze
znanym z literatury zbiorem ok. 14 "informative sensors" dla FD001 — dobry
sygnał, że dane są poprawnie sparsowane, nie artefakt.

Trzy metody, ten sam sygnał:

| Metoda | Co monitoruje | Reguła alarmu |
|---|---|---|
| A — baseline SPC | surowa wartość czujnika | 3 kolejne cykle z \|z\|>3 względem pierwszych 30 cykli |
| B — TIMDR `flow` | lokalny trend (gradient LSQ, k=8) | ta sama reguła, na `flow_grad` |
| C — TIMDR `anomalies` | odstępstwo od TRM-median | domyślny próg factor=3.0×MAD |

## Wynik (jeden przebieg, dane rzeczywiste)

| Metoda | Cykl alarmu | Lead time (cykli przed awarią) | Fałszywy alarm w cyklach 1-60 |
|---|---|---|---|
| A — baseline SPC (wartość) | 145 | **47** | nie |
| B — TIMDR flow (trend) | 174 | **18** | nie |
| C — TIMDR anomalies | 96 (izolowany) | **96*** | nie (ale niepotwierdzone, patrz niżej) |

\* Metoda C zgłasza 3 pojedyncze, izolowane punkty (cykle 96, 126, 165), nie
sygnał ciągły. Bez negatywnej kontroli (drugi długi przebieg "zdrowy" o tym
samym poziomie szumu czujnika) nie da się odróżnić prawdziwego wczesnego
ostrzeżenia od zwykłej stopy fałszywych alarmów tej metody przy tym
poziomie szumu — **traktuj cykl 96 jako obiecujący trop, nie potwierdzony
wynik**.

**Uczciwa interpretacja:** prosty przemysłowy control chart na surowej
wartości czujnika (metoda A) dał lepszy, pewniejszy wynik niż przeniesiony
bez zmian mechanizm `flow` (metoda B) — dokładnie ten sam wzorzec co przy
teście operatora torsji w sejsmologii: monitorowanie POCHODNEJ (trendu)
zamiast wartości traci czułość, bo przy powolnym, prawie liniowym dryfie
degradacyjnym lokalny gradient zmienia się niewiele aż do bardzo późnej
fazy życia silnika. `anomalies()` dał najwcześniejszy sygnał, ale jego
mechanizm (odstające punkty względem wygładzonej mediany) nie jest z
natury dopasowany do wykrywania POCZĄTKU trendu, więc wynik wymaga
potwierdzenia na kontroli negatywnej, zanim cokolwiek się z niego wywnioskuje.

## Jak zrobić to porządnie (następny krok, wymaga maszyny bez blokady sieci)

1. Pobrać pełny `train_FD001.txt` (100 silników) — publicznie dostępny,
   np. `github.com/mapr-demos/predictive-maintenance` albo Kaggle
   `behrad3d/nasa-cmaps`. Ten sam test co tutaj, ale na 100 silnikach:
   rozkład lead time dla każdej metody, prawdziwa stopa fałszywych alarmów
   metody C (nie tylko "brak w jednym przebiegu").
2. Rozszerzyć o FD002/FD003/FD004 (inne warunki pracy / inne tryby awarii)
   — sprawdzić, czy wniosek ("baseline > flow-trend") utrzymuje się przy
   innym mechanizmie degradacji.
3. CWRU bearing dataset i NASA IMS (łożyska) — wymagają pobrania plików
   `.mat` z `engineering.case.edu/bearingdatacenter` i repozytorium NASA
   PCoE; w tym środowisku zablokowane, do zrobienia na maszynie
   użytkownika.

## Pliki

- `cmapss_fd001_unit1.txt` — realne dane NASA C-MAPSS FD001, unit 1 (192
  cykle × 26 kolumn: unit, cycle, 3×operational setting, 21×sensor).
- `timdr_core.py` — kopia 1:1 `timdr_core_earthquake.py` z
  `TIMDR-Earthquake-Core` (bez zmian logiki).
- `test_engine_degradation.py` — test opisany wyżej, uruchamialny wprost:
  `python3 test_engine_degradation.py`.
