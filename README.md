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

Reguły metod i wynik trafiły do gita w tym samym commicie (d3a6ddf), więc
„pre-rejestrowana” znaczy tu „zapisana w kodzie”, a nie potwierdzona kolejnością w historii.

Czujnik do testu (sensor 4, T50 — temperatura na wylocie z LPT) dobrano **algorytmicznie**: spośród 21 czujników wybrano ten o największym
przesunięciu średniej między ostatnimi 30 a pierwszymi 30 cyklami (w jednostkach
odchylenia standardowego z początku życia). Uwaga: wybór korzysta z końca życia tego
samego silnika, na którym potem mierzy się czas ostrzeżenia (selekcja na wyniku) —
sprzyja to wszystkim trzem metodom. 14 czujników o niezerowej zmienności to dokładnie znany z literatury zbiór ok. 14
"informative sensors" dla FD001 (pozostałe 7 jest stałych) — to potwierdza poprawne
sparsowanie kolumn, ale nie sam ranking (każdy ranking dałby tę samą czternastkę).

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
zamiast wartości traci czułość, bo przy dryfie degradacyjnym, który jest prawie płaski przez większość życia i przyspiesza
pod koniec (nachylenie w ostatniej trzeciej części ok. 27× większe niż w pierwszej),
lokalny gradient zmienia się niewiele aż do bardzo późnej fazy życia silnika. `anomalies()` dał najwcześniejszy sygnał, ale jego
mechanizm (odstające punkty względem wygładzonej mediany) nie jest z
natury dopasowany do wykrywania POCZĄTKU trendu, więc wynik wymaga
potwierdzenia na kontroli negatywnej, zanim cokolwiek się z niego wywnioskuje.

**Analiza wsteczna, nie monitoring na bieżąco.** Tabela wyżej liczy metody na całym
przebiegu, a metody B i C korzystają przy tym z przyszłych cykli (B: gradient z k=8
najbliższych cykli z obu stron; C: mediana z obu stron i próg MAD z całego przebiegu).
Przy odtwarzaniu na bieżąco (metoda widzi tylko cykle do bieżącego) A alarmuje trwale
od cyklu 147 (lead 45), a B i C dają pojedyncze, rozproszone alarmy już od cyklu 87
(B w 8 cyklach, C w 5) — nie ciągły sygnał. Wniosek, że A jest pewniejsza, się
utrzymuje; lead time B i C z tabeli nie jest tym, co dałby monitoring na bieżąco.
Szczegóły: `docs/audit/`.

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

## Dashboard (2026-09-17)

Lokalna appka FastAPI + dashboard www, ten sam wzorzec architektoniczny co
Synoptyk-v3/SYNOPTYK-ARCTIC (serwer lokalny, endpoint `/api/*`, ciemny
motyw wspólny dla całego ekosystemu) — pokazuje wynik opisany wyżej
("Wynik (jeden przebieg, dane rzeczywiste)") jako trzy wykresy zamiast
tabeli w README:

- Metoda A (surowa wartość czujnika) z pasmem bazowym ±3σ i zaznaczonym
  cyklem alarmu.
- Metoda B (`flow`, lokalny trend) analogicznie.
- Metoda C (`anomalies`) z zaznaczonymi punktami odstającymi — panel
  jawnie powtarza zastrzeżenie o braku kontroli negatywnej (patrz wyżej),
  nie tylko w README, żeby ktoś patrzący WYŁĄCZNIE na dashboard też je
  zobaczył.

Obliczenia (`analysis.py`) są WYDZIELONE i dzielone 1:1 między
`test_engine_degradation.py` (skrypt konsolowy) a `webapp/app.py`
(dashboard) — zero duplikacji logiki, zweryfikowane identycznym wynikiem
po refaktoryzacji (te same cykle alarmów/lead time/punkty anomalii co
przed wydzieleniem).

**Uruchomienie:** `run.bat` (Windows, instaluje `requirements.txt` i
otwiera `http://127.0.0.1:8010` w przeglądarce) albo ręcznie:

```
pip install -r requirements.txt
python -m uvicorn webapp.app:app --host 127.0.0.1 --port 8010
```

Dane są statyczne (jeden plik lokalny) — dashboard NIE wymaga połączenia
z internetem, w odróżnieniu od Synoptyk-v3/SYNOPTYK-ARCTIC.

**Ograniczenie, jawnie**: dashboard pokazuje TYLKO unit 1 (jedyne realne
dane w tym repo — patrz "Co jest tu realne" wyżej). `/api/engine_run`
przyjmuje parametr `?unit=`, ale każda wartość poza `1` zwraca czytelny
HTTP 400, nie cichy/zmyślony wynik — gotowe pod przyszłe rozszerzenie na
100 silników (patrz "Jak zrobić to porządnie"), nie obietnica, że już
działa.

## Cztery źródła danych w dashboardzie (2026-09-17)

Dashboard liczy DOKŁADNIE tym samym rdzeniem (`analysis.py`, metody A/B/C)
na czterech różnych źródłach sygnału, wybieranych zakładkami w interfejsie:

| Źródło | Endpoint | Co to jest |
|---|---|---|
| Demo (unit 1) | `GET /api/engine_run` | jedyne realne dane w tym repo (opisane wyżej) |
| Demo syntetyczne | `GET /api/synthetic_run` | wygenerowany proceduralnie (szum + narastający dryft), jawnie oznaczony jako NIE realne dane — drugi przebieg do sprawdzenia interfejsu na innym kształcie sygnału |
| Wczytaj plik | `POST /api/upload` | własny plik użytkownika w formacie C-MAPSS (jak `cmapss_fd001_unit1.txt`) — czujnik do analizy wybierany AUTOMATYCZNIE (patrz niżej), albo podaj `?sensor=N` (1..21) żeby wymusić konkretny |
| Z urządzenia — port szeregowy | `GET /api/serial/ports`, `POST /api/serial/read` | odczyt N próbek (jedna liczba/linia) z portu szeregowego, wymaga `pyserial` |
| Z urządzenia — mikrofon (Bluetooth audio) | `GET /api/audio/devices`, `POST /api/audio/record` | nagrywa audio z wybranego urządzenia wejściowego (w tym sparowany zestaw Bluetooth widoczny w systemie jako mikrofon) i liczy dominującą częstotliwość (FFT) w kolejnych oknach czasowych jako serię próbek; wymaga `sounddevice` |

**Zastrzeżenie o ścieżce urządzenia**: kod czytający port szeregowy i
mikrofon (`webapp/app.py`, `/api/serial/*` i `/api/audio/*`) powstał w
środowisku bez dostępu do portów szeregowych ani sprzętu audio (sandbox).
Co JEST przetestowane: parsowanie próbek na wynik A/B/C
(`analysis.compute_run_from_device_samples`) i ekstrakcja cechy audio
(`analysis.dominant_frequency_series` — sprawdzona syntetyczną sinusoidą
o znanej częstotliwości, w tym z dryfem częstotliwości w czasie, patrz
`test_analysis_extra.py`). Co NIE jest przetestowane: sam odczyt z
prawdziwego portu szeregowego ani prawdziwego mikrofonu/Bluetooth.
Przetestuj ostrożnie na własnym sprzęcie (np. Arduino wysyłający
`Serial.println(wartość)` dla portu szeregowego; dowolny mikrofon lub
sparowany zestaw Bluetooth widoczny w ustawieniach dźwięku Windows dla
audio).

### Auto-wybór czujnika dla wgranego pliku (2026-09-22)

`compute_engine_run()` (jedyne realne dane, unit=1) zawsze używa sensora 4
— to zamrożony, już zweryfikowany wynik (patrz "Metodologia" wyżej), nie
zmieniamy go. Ale `POST /api/upload` przyjmuje PLIK OD UŻYTKOWNIKA, który
może pochodzić z zupełnie innego silnika/jednostki — sensor 4 nie ma tam
żadnego uprzywilejowanego statusu. Dlatego domyślnie (bez `?sensor=N`)
czujnik do analizy jest wybierany automatycznie: `analysis.select_informative_sensor()`
liczy dla wszystkich 21 czujników ten sam z-score przesunięcia średniej
(ostatnie 30 cykli względem pierwszych 30, znormalizowane odchyleniem
standardowym okna referencyjnego), którym pierwotnie RĘCZNIE znaleziono
sensor 4 dla unit=1 — teraz to ta sama metoda, tylko przeniesiona do
kodu i uruchamiana na każdym wgranym pliku z osobna. Zweryfikowane: na
danych unit=1 auto-wybór odtwarza dokładnie sensor 4 (patrz
`test_select_informative_sensor_reproduces_sensor4_on_real_unit1` w
`test_analysis_extra.py`) — to potwierdzenie zgodności z już znanym
wynikiem, nie nowe odkrycie. Odpowiedź `/api/upload` zawiera
`sensor_number` (który czujnik faktycznie użyto) i `sensor_scores`
(wszystkie 21 wyników z-score, żeby wybór był audytowalny, nie czarną
skrzynką) — `sensor_scores` jest `null`, gdy `sensor` podano ręcznie.

## Pliki

- `cmapss_fd001_unit1.txt` — realne dane NASA C-MAPSS FD001, unit 1 (192
  cykle × 26 kolumn: unit, cycle, 3×operational setting, 21×sensor).
- `timdr_core.py` — kopia 1:1 `timdr_core_earthquake.py` z
  `TIMDR-Earthquake-Core` (bez zmian logiki).
- `analysis.py` — wspólny rdzeń obliczeniowy metod A/B/C (patrz
  "Dashboard" wyżej), używany zarówno przez `test_engine_degradation.py`,
  jak i `webapp/app.py`.
- `test_engine_degradation.py` — skrypt opisany wyżej, uruchamialny wprost:
  `python3 test_engine_degradation.py`.
- `webapp/app.py`, `webapp/static/index.html` — dashboard (patrz wyżej,
  sekcja "Cztery źródła danych").
- `test_analysis_extra.py` — testy funkcji obliczeniowych dla 4 źródeł
  danych (regresja unit=1, demo syntetyczne, upload, próbki z urządzenia,
  ekstrakcja dominującej częstotliwości z audio).
- `run.bat`, `requirements.txt` — uruchomienie dashboardu na Windows.
