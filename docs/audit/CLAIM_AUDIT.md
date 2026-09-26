# Audyt twierdzeń: README → dane, metodologia, wynik, auto-wybór czujnika, pliki (TIMDR-Aviation-Diagnostics)

Silnik: claim_audit v0.2 (TIMDR-AI-Core).

Drugi przebieg, po poprawkach README i kodu (`CLAIM_AUDIT_ADDENDUM_1.md`). Pierwszy przebieg z analizą: `CLAIM_AUDIT_v1.md`. Karty zmieniono po pierwszym przebiegu — ten raport sprawdza zgodność poprawionego README z plikami, nie jest niezależnym testem.

Wygenerowano: 2026-09-26 12:21 UTC; reguły: `docs/audit/CLAIM_AUDIT_PREREG.md` (sha256 a771af74b0fb), karty: `claims_av.py` (sha256 bd8b29896d8f), README sha256 91c4eba857aa.

Werdykty kart: NIEROZSTRZYGNIĘTE 1, POTWIERDZONE 32.

## Twierdzenia

| # | Twierdzenie (cytat z README) | Werdykt | Przeliczenie | Uwagi |
| --- | --- | --- | --- | --- |
| V1 | wszystkie zwracają `403 blocked-by-allowlist` na poziomie bash | NIEROZSTRZYGNIĘTE | - | historia środowiska, w którym powstało repo - nieweryfikowalna z plików |
| V2 | (FD001, unit 1, kompletny przebieg run-to-failure — 192 cykle, 21 czujników, awaria w cyklu 192) | POTWIERDZONE | unit [1], cykle 1–192 bez luk, 21 czujników; w train_FD001 unit 1 kończy się na cyklu 192 | poziom REFERENCJA (zbiór treningowy C-MAPSS: przebiegi do awarii) |
| V3 | Plik `cmapss_fd001_unit1.txt` w tym repo to dokładna kopia tych 192 wierszy z oryginalnego `train_FD001.txt` | POTWIERDZONE | 192 wiersze identyczne liczbowo z unit 1 w train_FD001.txt z mirrora mapr-demos | poziom REFERENCJA |
| V4 | **To jest test na n=1 (jeden silnik)** | POTWIERDZONE | jedna jednostka w pliku |  |
| V5 | (do tego potrzeba pełnego zbioru 100 silników | POTWIERDZONE | train_FD001.txt: 100 silników | poziom REFERENCJA |
| V6 | Czujnik do testu (sensor 4, T50 — temperatura na wylocie z LPT) dobrano **algorytmicznie**: spośród 21 czujników wybrano ten o największym przesunięciu średniej między ostatnimi 30 a pierwszymi 30 cyklami | POTWIERDZONE | największy z-score: czujnik 4 (z = 7,7) | R13: selekcja na wyniku opisana w README |
| V7 | 14 czujników o niezerowej zmienności to dokładnie znany z literatury zbiór ok. 14 "informative sensors" dla FD001 (pozostałe 7 jest stałych) | POTWIERDZONE | niestałe: [2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15, 17, 20, 21]; stałe: [1, 5, 6, 10, 16, 18, 19] | R10 |
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
| V18 | metoda A) dał lepszy, pewniejszy wynik niż przeniesiony bez zmian mechanizm `flow` (metoda B) | POTWIERDZONE | wstecznie lead A 47 vs B 18; online odsetek cykli z alarmem po pierwszym: A 0,93, B 0,08, C 0,05 | „pewniejszy” = trwały alarm online |
| V19 | przy dryfie degradacyjnym, który jest prawie płaski przez większość życia i przyspiesza pod koniec (nachylenie w ostatniej trzeciej części ok. 27× większe niż w pierwszej) | POTWIERDZONE | ΔBIC 56,9, nachylenie ostatniej/pierwszej trzeciej 26,6× | R9 |
| V20 | `anomalies()` dał najwcześniejszy sygnał | POTWIERDZONE | lead przyczynowy: A 45, B 105, C 105 | oceniane przyczynowo (R8) |
| V21 | Przy odtwarzaniu na bieżąco (metoda widzi tylko cykle do bieżącego) A alarmuje trwale od cyklu 147 (lead 45), a B i C dają pojedyncze, rozproszone alarmy już od cyklu 87 (B w 8 cyklach, C w 5) | POTWIERDZONE | A od 147 (43 cykli); B [87, 141, 142, 156, 177, 178, 179, 187]; C [87, 96, 126, 152, 165] | odtwarzanie online (aneks 1) |
| V22 | metody B i C korzystają przy tym z przyszłych cykli (B: gradient z k=8 najbliższych cykli z obu stron; C: mediana z obu stron i próg MAD z całego przebiegu) | POTWIERDZONE | flow/trm: okno k najbliższych po obu stronach; anomalies: MAD z reszt całego szeregu |  |
| A1 | ### Auto-wybór czujnika dla wgranego pliku (2026-09-22) | POTWIERDZONE | funkcja dodana w commicie z 2026-09-22 |  |
| A2 | `compute_engine_run()` (jedyne realne dane, unit=1) zawsze używa sensora 4 | POTWIERDZONE | compute_engine_run: kolumna SENSOR4_COL (czujnik 4) |  |
| A3 | sensor 4 nie ma tam żadnego uprzywilejowanego statusu | POTWIERDZONE | upload: sensor=None -> auto-wybór |  |
| A4 | liczy dla wszystkich 21 czujników ten sam z-score przesunięcia średniej (ostatnie 30 cykli względem pierwszych 30, znormalizowane odchyleniem standardowym okna referencyjnego), którym pierwotnie RĘCZNIE znaleziono sensor 4 dla unit=1 | POTWIERDZONE | repo i niezależne przeliczenie: najlepszy czujnik 4; ocenionych 21 z 21 | czujniki o stałej wartości w oknie referencyjnym są pomijane |
| A5 | na danych unit=1 auto-wybór odtwarza dokładnie sensor 4 (patrz `test_select_informative_sensor_reproduces_sensor4_on_real_unit1` w `test_analysis_extra.py`) | POTWIERDZONE | best = 4; pytest: ['14 passed in 1.66s'] |  |
| A6 | (wszystkie 21 wyników z-score, żeby wybór był audytowalny, nie czarną skrzynką) | POTWIERDZONE | sensor_scores ma 21 wpisów | R12 |
| A7 | `sensor_scores` jest `null`, gdy `sensor` podano ręcznie | POTWIERDZONE | sensor=4 podany ręcznie -> sensor_scores = None |  |
| P1 | `cmapss_fd001_unit1.txt` — realne dane NASA C-MAPSS FD001, unit 1 (192 cykle × 26 kolumn: unit, cycle, 3×operational setting, 21×sensor) | POTWIERDZONE | 192 × 26 | poziom REFERENCJA |
| P2 | `timdr_core.py` — kopia 1:1 `timdr_core_earthquake.py` z `TIMDR-Earthquake-Core` (bez zmian logiki) | POTWIERDZONE | funkcje metod identyczne (AST bez docstringów) | R11; poza nimi różni się obsługa importu scipy (leniwy import), tak jak w źródle po późniejszej poprawce |
| P3 | używany zarówno przez `test_engine_degradation.py`, jak i `webapp/app.py` | POTWIERDZONE | import analysis w obu |  |
| P4 | `test_analysis_extra.py` — testy funkcji obliczeniowych dla 4 źródeł danych (regresja unit=1, demo syntetyczne, upload, próbki z urządzenia, ekstrakcja dominującej częstotliwości z audio) | POTWIERDZONE | testy obecne dla 5 grup; pytest: ['14 passed in 1.66s'] |  |

## Reguły całego fragmentu

| Reguła | Wynik | Szczegóły |
| --- | --- | --- |
| R4 świeżość | POTWIERDZONE | 1 plikow zgodnych z zamrozonymi hashami |
| R6 kotwica | UJAWNIONE | test_engine_degradation.py i README.md w tym samym commicie (d3a6ddf / d3a6ddf); README opisuje to ograniczenie |
