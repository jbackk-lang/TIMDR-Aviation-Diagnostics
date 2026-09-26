# Audyt twierdzeń: README → dane, metodologia, wynik, auto-wybór czujnika, pliki (TIMDR-Aviation-Diagnostics)

Silnik: claim_audit v0.2 (TIMDR-AI-Core).

Wygenerowano: 2026-09-26 12:19 UTC; reguły: `docs/audit/CLAIM_AUDIT_PREREG.md` (sha256 a771af74b0fb), karty: `claims_av.py` (sha256 21734eb126fa), README sha256 17e2e6740314.

Werdykty kart: DO ZŁAGODZENIA 1, NIEROZSTRZYGNIĘTE 1, POTWIERDZONE 27, SPRZECZNE 2.

## Twierdzenia

| # | Twierdzenie (cytat z README) | Werdykt | Przeliczenie | Uwagi |
| --- | --- | --- | --- | --- |
| V1 | wszystkie zwracają `403 blocked-by-allowlist` na poziomie bash | NIEROZSTRZYGNIĘTE | - | historia środowiska, w którym powstało repo - nieweryfikowalna z plików |
| V2 | (FD001, unit 1, kompletny przebieg run-to-failure — 192 cykle, 21 czujników, awaria w cyklu 192) | POTWIERDZONE | unit [1], cykle 1–192 bez luk, 21 czujników; w train_FD001 unit 1 kończy się na cyklu 192 | poziom REFERENCJA (zbiór treningowy C-MAPSS: przebiegi do awarii) |
| V3 | Plik `cmapss_fd001_unit1.txt` w tym repo to dokładna kopia tych 192 wierszy z oryginalnego `train_FD001.txt` | POTWIERDZONE | 192 wiersze identyczne liczbowo z unit 1 w train_FD001.txt z mirrora mapr-demos | poziom REFERENCJA |
| V4 | **To jest test na n=1 (jeden silnik)** | POTWIERDZONE | jedna jednostka w pliku |  |
| V5 | (do tego potrzeba pełnego zbioru 100 silników | POTWIERDZONE | train_FD001.txt: 100 silników | poziom REFERENCJA |
| V6 | Czujnik do testu (sensor 4, T50 — temperatura na wylocie z LPT) dobrano **obiektywnie**: spośród 21 czujników wybrano ten o największym przesunięciu średniej między ostatnimi 30 a pierwszymi 30 cyklami | DO ZŁAGODZENIA | największy z-score: czujnik 4 (z = 7,7) | R13: wybór jest algorytmiczny, ale używa ostatnich 30 cykli (koniec życia) tego samego silnika, na którym mierzy się czas ostrzeżenia - README tego nie mówi; nazwa T50 wg dokumentacji C-MAPSS (nie z pliku) |
| V7 | Ranking pokrył się 1:1 ze znanym z literatury zbiorem ok. 14 "informative sensors" dla FD001 | POTWIERDZONE | top-14: [2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15, 17, 20, 21]; czujniki stałe: [1, 5, 6, 10, 16, 18, 19] | R10 |
| V8 | 3 kolejne cykle z \|z\|>3 względem pierwszych 30 cykli | POTWIERDZONE | first_sustained_alarm(run=3, thr=3.0), okno referencyjne 30 |  |
| V9 | lokalny trend (gradient LSQ, k=8) | POTWIERDZONE | k_neighbors=8, gradient z lstsq | okno k najbliższych cykli z obu stron (także przyszłych) - patrz R8 |
| V10 | domyślny próg factor=3.0×MAD | POTWIERDZONE | factor=3.0, MAD ×1,4826 | próg MAD liczony z całego przebiegu (także przyszłych cykli) - patrz R8 |
| V11 | Fałszywy alarm w cyklach 1-60 | POTWIERDZONE | A False, B False, C False | R14 |
| V12 | | A — baseline SPC (wartość) | 145 | **47** | nie | | POTWIERDZONE | alarm 145, lead 47, fałszywy alarm 1-60: False | poziom KOD REPO + NIEZALEŻNE (metoda A przeliczona własnym kodem) |
| V13 | | B — TIMDR flow (trend) | 174 | **18** | nie | | POTWIERDZONE | alarm 174, lead 18, fałszywy alarm 1-60: False | poziom KOD REPO |
| V14 | | C — TIMDR anomalies | 96 (izolowany) | **96*** | nie (ale niepotwierdzone, patrz niżej) | | POTWIERDZONE | pierwsza anomalia 96, lead 96, anomalie ≤ 60: False | R14: pole false_positive_1_60 dla C jest w kodzie ustawione na False bez obliczeń; tu policzone z listy |
| V15 | Lead time (cykli przed awarią) | POTWIERDZONE | A: README 47, przyczynowo 45; B: README 18, przyczynowo 105; C: README 96, przyczynowo 105 | R8: metoda dostaje tylko cykle 1..c |
| V16 | Metoda C zgłasza 3 pojedyncze, izolowane punkty (cykle 96, 126, 165), nie sygnał ciągły | POTWIERDZONE | anomalie: [96, 126, 165] |  |
| V17 | traktuj cykl 96 jako obiecujący trop, nie potwierdzony wynik | POTWIERDZONE | pierwsza anomalia 96 |  |
| V18 | metoda A) dał lepszy, pewniejszy wynik niż przeniesiony bez zmian mechanizm `flow` (metoda B) | SPRZECZNE | lead A 47 vs B 18 (przyczynowo 45 vs 105) |  |
| V19 | przy powolnym, prawie liniowym dryfie degradacyjnym lokalny gradient zmienia się niewiele aż do bardzo późnej fazy życia silnika | SPRZECZNE | ΔBIC lin−kwadr 56,9, krzywizna 1,35e-03, nachylenie ostatniej/pierwszej trzeciej 26,6× | R9, czujnik 4, cykle 31–192 |
| V20 | `anomalies()` dał najwcześniejszy sygnał | POTWIERDZONE | lead przyczynowy: A 45, B 105, C 105 | oceniane przyczynowo (R8) |
| A1 | ### Auto-wybór czujnika dla wgranego pliku (2026-09-22) | POTWIERDZONE | funkcja dodana w commicie z 2026-09-22 |  |
| A2 | `compute_engine_run()` (jedyne realne dane, unit=1) zawsze używa sensora 4 | POTWIERDZONE | compute_engine_run: kolumna SENSOR4_COL (czujnik 4) |  |
| A3 | sensor 4 nie ma tam żadnego uprzywilejowanego statusu | POTWIERDZONE | upload: sensor=None -> auto-wybór |  |
| A4 | liczy dla wszystkich 21 czujników ten sam z-score przesunięcia średniej (ostatnie 30 cykli względem pierwszych 30, znormalizowane odchyleniem standardowym okna referencyjnego), którym pierwotnie RĘCZNIE znaleziono sensor 4 dla unit=1 | POTWIERDZONE | repo i niezależne przeliczenie: najlepszy czujnik 4; ocenionych 21 z 21 | czujniki o stałej wartości w oknie referencyjnym są pomijane |
| A5 | na danych unit=1 auto-wybór odtwarza dokładnie sensor 4 (patrz `test_select_informative_sensor_reproduces_sensor4_on_real_unit1` w `test_analysis_extra.py`) | POTWIERDZONE | best = 4; pytest: ['13 passed in 1.66s'] |  |
| A6 | (wszystkie 21 wyników z-score, żeby wybór był audytowalny, nie czarną skrzynką) | POTWIERDZONE | sensor_scores ma 21 wpisów | R12 |
| A7 | `sensor_scores` jest `null`, gdy `sensor` podano ręcznie | POTWIERDZONE | sensor=4 podany ręcznie -> sensor_scores = None |  |
| P1 | `cmapss_fd001_unit1.txt` — realne dane NASA C-MAPSS FD001, unit 1 (192 cykle × 26 kolumn: unit, cycle, 3×operational setting, 21×sensor) | POTWIERDZONE | 192 × 26 | poziom REFERENCJA |
| P2 | `timdr_core.py` — kopia 1:1 `timdr_core_earthquake.py` z `TIMDR-Earthquake-Core` (bez zmian logiki) | POTWIERDZONE | funkcje metod identyczne (AST bez docstringów) | R11; poza nimi różni się obsługa importu scipy (leniwy import), tak jak w źródle po późniejszej poprawce |
| P3 | używany zarówno przez `test_engine_degradation.py`, jak i `webapp/app.py` | POTWIERDZONE | import analysis w obu |  |
| P4 | `test_analysis_extra.py` — testy funkcji obliczeniowych dla 4 źródeł danych (regresja unit=1, demo syntetyczne, upload, próbki z urządzenia, ekstrakcja dominującej częstotliwości z audio) | POTWIERDZONE | testy obecne dla 5 grup; pytest: ['13 passed in 1.66s'] |  |

## Reguły całego fragmentu

| Reguła | Wynik | Szczegóły |
| --- | --- | --- |
| R4 świeżość | POTWIERDZONE | 1 plikow zgodnych z zamrozonymi hashami |
| R6 kotwica | NIEROZSTRZYGNIĘTE | test_engine_degradation.py i README.md w tym samym lub pozniejszym commicie (d3a6ddf / d3a6ddf) - zamrozenie tylko deklarowane |
| R7b sformułowanie | DO ZŁAGODZENIA | „zawsze”: słowo bezwzględne |

## Analiza (po uruchomieniu, post hoc — karty i reguły NIE zostały zmienione)

**Dane i kod się zgadzają.** Plik unit 1 jest liczbowo identyczny z 192 wierszami unit 1 w `train_FD001.txt` pobranym z
mirrora wskazanego w README (100 silników). Tabela wyników (145/47, 174/18, 96/96, anomalie 96, 126, 165) odtwarza się
z kodu, a metoda A — także z niezależnej implementacji. Funkcje metod w `timdr_core.py` są identyczne z
TIMDR-Earthquake-Core. 13/13 testów przechodzi.

**V19 — dryf nie jest „prawie liniowy”.** Czujnik 4 w cyklach 31–192: model kwadratowy lepszy o ΔBIC 57, krzywizna
dodatnia, nachylenie w ostatniej trzeciej części ~27× większe niż w pierwszej. Dryf jest płaski przez większość życia
i przyspiesza pod koniec — to właśnie dlatego gradient (metoda B) rośnie dopiero późno. Obserwacja z README jest trafna,
wyjaśnienie („prawie liniowy”) — odwrotne.

**V15/V18/V20 — tabela to analiza wsteczna.** Metody B i C korzystają z przyszłych cykli: `flow` liczy gradient z k = 8
najbliższych cykli z obu stron, `anomalies` — medianę z obu stron i próg MAD z całego przebiegu. Odtwarzanie online
(metoda widzi tylko cykle 1..c) daje inny obraz: A alarmuje trwale od cyklu 147 (43 z 46 kolejnych cykli), B i C dają
pojedyncze, rozproszone alarmy już od cyklu 87 (B: 87, 141, 142, 156, 177–179, 187; C: 87, 96, 126, 152, 165). Reguła R8
przeszła (alarmy online nie są późniejsze niż w tabeli), ale V18 wyszło SPRZECZNE, bo online B alarmuje wcześniej niż A.
Wcześniej nie znaczy lepiej: alarmy B/C online to izolowane punkty na brzegu okna, nie ciągły sygnał — wniosek README
„A pewniejsza niż B” broni się, tylko nie liczbami lead time z tabeli.

**V7 — zgodność z literaturą jest trywialna.** W unit 1 dokładnie 7 czujników jest stałych w oknie referencyjnym
(1, 5, 6, 10, 16, 18, 19); pozostałe 14 to właśnie zestaw „informative sensors” z literatury. Każdy ranking dałby tę samą
czternastkę, więc zgodność potwierdza poprawne parsowanie kolumn, ale nic nie mówi o samym rankingu.

**V6 — selekcja na wyniku (R13).** Czujnik 4 wybrano, porównując ostatnie 30 cykli (koniec życia) z pierwszymi 30 w tym
samym przebiegu, na którym potem mierzy się czas ostrzeżenia. README nazywa to „obiektywnie” i tego nie ujawnia.

**R14 — kod.** `analysis._analyze_series` ustawia `false_positive_1_60` metody C na False bez obliczeń. Dla unit 1 wynik
jest prawdziwy (brak anomalii ≤ 60), ale dla danych z pliku/urządzenia dashboard zawsze pokaże „brak fałszywych alarmów” C.

**R6** — reguły metod i wynik w tym samym commicie d3a6ddf. **R7b „zawsze”** — fałszywy alarm (kod rzeczywiście zawsze
używa czujnika 4 dla unit 1).
