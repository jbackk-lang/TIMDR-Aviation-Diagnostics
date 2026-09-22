"""
analysis.py — wspolny rdzen obliczeniowy dla test_engine_degradation.py
(skrypt konsolowy) i webapp/app.py (dashboard).

WYDZIELONE z test_engine_degradation.py (2026-09-17), zeby dashboard i
skrypt konsolowy liczyly DOKLADNIE to samo, jednym kodem -- zamiast
kopiowac logike metod A/B/C do dwoch miejsc, co prowadziloby do
dokladnie tego samego ryzyka rozjazdu, jakie juz raz naprawiono w tym
ekosystemie (np. timdr_security_trigger.py w TIMDR-Security-Module,
gdzie dostarczona wersja liczyla sie inaczej niz prawdziwe API modulow,
ktore opakowywala). Zero zmian w matematyce wzgledem oryginalnego
test_engine_degradation.py dla sciezki unit=1 -- to czyste przeniesienie,
weryfikowane identycznym wynikiem.

ROZSZERZENIE (2026-09-17, druga runda): rdzen metod A/B/C wydzielony
dalej do `_analyze_series()`, tak by DOKLADNIE ten sam kod liczyl 4
rozne zrodla danych:
  - compute_engine_run()            -- realne dane, unit=1 (bez zmian)
  - compute_synthetic_run()         -- SYNTETYCZNY drugi przebieg, jawnie
                                        oznaczony, do demonstracji UI
  - compute_run_from_upload()       -- plik uzytkownika w formacie C-MAPSS
  - compute_run_from_device_samples() -- pojedyncze probki z urzadzenia
                                        (np. port szeregowy, patrz
                                        webapp/app.py /api/serial/*)
Weryfikacja ograniczona: sciezka unit=1 zweryfikowana identycznym wynikiem
przed/po (patrz commit). Trzy nowe sciezki (synthetic/upload/device) NIE
maja realnych danych referencyjnych do porownania -- zweryfikowano tylko,
ze kod dziala i daje spojny, sensowny ksztalt wyniku (patrz testy), nie
ze "wykrywa cos prawdziwego" (dla syntetycznych danych to pytanie nie ma
sensu, dla upload/device zalezy od tego, co user faktycznie wgra/podlaczy).
"""
from __future__ import annotations

import io
import os
from typing import TypedDict

import numpy as np

from timdr_core import TIMDR_EarthquakeCore

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(_THIS_DIR, "cmapss_fd001_unit1.txt")

SENSOR4_COL = 5 + 3  # sensor 4 (0-indexed w formacie C-MAPSS: col5=sensor1)
MIN_SAMPLES = 30     # dlugosc okna referencyjnego (cykle 1-30) -- ten sam
                      # wymog dla wszystkich zrodel danych
N_SENSORS = 21        # C-MAPSS: sensory 1..21, kolumny SENSOR_COL(1)..SENSOR_COL(21)


def _sensor_col(sensor_number: int) -> int:
    """Kolumna (0-indexed) danego numeru czujnika C-MAPSS (1..21). sensor 4
    -> SENSOR4_COL, jw."""
    return 5 + (sensor_number - 1)


def select_informative_sensor(
    cycle: np.ndarray, all_sensors: np.ndarray, reference_window: int = MIN_SAMPLES
) -> tuple[int, dict[int, float]]:
    """Automatyczny wybor NAJBARDZIEJ INFORMATYWNEGO czujnika (2026-09-22,
    "tu tez" -- ten sam duch co auto-wybor pasma rezonansu w
    TIMDR-Industrial-Predict: zastapienie recznie dobranej stalej [tu:
    SENSOR4_COL, sensor 4] czyms wyliczanym z danych referencyjnych).

    Metoda IDENTYCZNA z ta opisana w README ("Metodologia") jako sposob, w
    jaki oryginalnie wybrano sensor 4 dla unit=1 -- tu PRZENIESIONA z
    jednorazowej recznej analizy do wielokrotnie uzywalnego kodu: dla
    kazdego z 21 czujnikow, z-score przesuniecia sredniej miedzy OSTATNIM a
    PIERWSZYM oknem `reference_window` cykli, wzgledem odchylenia
    standardowego w oknie poczatkowym --
        z_i = |mean(s_i[-w:]) - mean(s_i[:w])| / std(s_i[:w])
    (std~0 w oknie poczatkowym -> ten czujnik pomijany, dzielenie przez ~0
    jest niesensowne/niestabilne, nie automatycznie "najbardziej
    informatywny"). Zwraca (numer_najlepszego_czujnika, wszystkie_z_score) -
    PELNY slownik wszystkich 21 wynikow jest zwracany celowo (nie tylko
    zwyciezca), zeby wybor byl audytowalny, nie czarna skrzynka.

    UCZCIWE ZASTRZEZENIE: ten sam algorytm zastosowany do danych unit=1
    (jedyne realne dane w tym repo) MUSI zwrocic sensor=4, bo to jest
    dokladnie ta metoda, ktora go tam znalazla recznie (patrz
    test_select_informative_sensor_reproduces_sensor4_on_real_unit1 w
    test_analysis_extra.py) - to jest odtworzenie znanego wyniku, nie nowe
    odkrycie. Wartosc tej funkcji jest w tym, ze dziala TEZ na danych, ktore
    NIE sa unit=1 (upload uzytkownika z innym silnikiem/jednostka), gdzie
    "sensor 4" nie ma zadnej gwarancji bycia najbardziej informatywnym."""
    n = all_sensors.shape[0]
    w = min(reference_window, n)
    if w < 2:
        raise ValueError(f"za malo probek ({n}) do wyboru czujnika (potrzeba >= 2)")

    scores: dict[int, float] = {}
    for sensor_num in range(1, N_SENSORS + 1):
        col = _sensor_col(sensor_num) - 5  # all_sensors ma TYLKO kolumny czujnikow, 0-indexed od sensor1
        series = all_sensors[:, col]
        first = series[:w]
        last = series[-w:]
        std_first = np.std(first)
        if std_first <= 1e-12:
            scores[sensor_num] = 0.0
            continue
        scores[sensor_num] = float(abs(np.mean(last) - np.mean(first)) / std_first)

    best_sensor = max(scores, key=lambda k: scores[k])
    return best_sensor, scores


def first_sustained_alarm(z: np.ndarray, run: int = 3, thr: float = 3.0) -> int | None:
    flag = np.abs(z) > thr
    for i in range(len(flag) - run + 1):
        if np.all(flag[i:i + run]):
            return i
    return None


class MethodResult(TypedDict):
    name: str
    series: list[float]          # z_a / z_b (z-score); residuals dla C
    alarm_index: int | None      # indeks w tablicy cycle, None = brak alarmu
    alarm_cycle: int | None
    lead_time: int | None        # end_of_life - alarm_cycle
    false_positive_1_60: bool
    anomaly_cycles: list[int]    # tylko metoda C -- wszystkie wykryte cykle


class EngineRun(TypedDict, total=False):
    unit: int | str
    cycle: list[int]
    sensor_raw: list[float]      # surowe wartosci czujnika
    end_of_life: int
    sensor_name: str
    source: str                  # "cmapss_real" | "synthetic" | "upload" | "device_live"
    is_synthetic: bool
    method_a: MethodResult
    method_b: MethodResult
    method_c: MethodResult
    sensor_number: int           # tylko source="upload" - numer czujnika (1..21) faktycznie uzyty
    sensor_scores: dict[int, float] | None  # tylko source="upload" z auto-wyborem - patrz select_informative_sensor


def _analyze_series(
    cycle: np.ndarray,
    sensor: np.ndarray,
    unit: int | str,
    sensor_name: str,
    source: str,
    is_synthetic: bool = False,
) -> EngineRun:
    """Rdzen metod A/B/C -- WSPOLNY dla wszystkich zrodel danych. Zero
    zmian w matematyce wzgledem oryginalnej (przed-refaktoryzacja) wersji
    dla przypadku, ktory ona obslugiwala (std referencyjne != 0) -- dwa
    dodane nizej warunki (std==0) to czysta obsluga bledow dla NOWYCH
    zrodel (plik/urzadzenie), ktore moga dostarczyc zdegenerowany sygnal;
    dla unit=1 nigdy sie nie uruchamiaja (zweryfikowano)."""
    if len(sensor) < MIN_SAMPLES:
        raise ValueError(
            f"za malo probek ({len(sensor)}) -- potrzeba co najmniej "
            f"{MIN_SAMPLES} (okno referencyjne dla metod A/B)."
        )
    end_of_life = int(cycle[-1])

    # --- Metoda A: baseline SPC na surowej wartosci ---
    ref_mean_a, ref_std_a = np.mean(sensor[:MIN_SAMPLES]), np.std(sensor[:MIN_SAMPLES])
    if ref_std_a == 0:
        raise ValueError(
            "odchylenie standardowe pierwszych 30 probek = 0 -- sygnal bez "
            "zadnej zmiennosci w oknie referencyjnym, metody SPC (A/B) nie "
            "da sie policzyc dla tych danych."
        )
    z_a = (sensor - ref_mean_a) / ref_std_a
    idx_a = first_sustained_alarm(z_a)
    fp_a = bool(np.any(np.abs(z_a[:60]) > 3.0))

    # --- Metoda B: TIMDR flow (lokalny trend) ---
    core = TIMDR_EarthquakeCore(k_neighbors=8)
    flow_grad = core.flow(cycle, sensor)
    ref_mean_b, ref_std_b = np.mean(flow_grad[:MIN_SAMPLES]), np.std(flow_grad[:MIN_SAMPLES])
    if ref_std_b == 0:
        z_b = np.zeros_like(flow_grad)
        idx_b = None
        fp_b = False
    else:
        z_b = (flow_grad - ref_mean_b) / ref_std_b
        idx_b = first_sustained_alarm(z_b)
        fp_b = bool(np.any(np.abs(z_b[:60]) > 3.0))

    # --- Metoda C: TIMDR anomalies (odstajace wzgledem TRM-median) ---
    anomaly_points, residuals, _thr = core.anomalies(cycle, sensor, factor=3.0)
    anomaly_points = [int(i) for i in anomaly_points]

    def _method_result(name, series, idx) -> MethodResult:
        alarm_cycle = int(cycle[idx]) if idx is not None else None
        return {
            "name": name,
            "series": [float(x) for x in series],
            "alarm_index": idx,
            "alarm_cycle": alarm_cycle,
            "lead_time": (end_of_life - alarm_cycle) if alarm_cycle is not None else None,
            "false_positive_1_60": None,  # wypelniane nizej per metoda
            "anomaly_cycles": [],
        }

    method_a = _method_result("A — baseline SPC (surowa wartosc)", z_a, idx_a)
    method_a["false_positive_1_60"] = fp_a

    method_b = _method_result("B — TIMDR flow (lokalny trend)", z_b, idx_b)
    method_b["false_positive_1_60"] = fp_b

    method_c = _method_result(
        "C — TIMDR anomalies (odstajace, NIEPOTWIERDZONE)",
        residuals,
        anomaly_points[0] if anomaly_points else None,
    )
    method_c["false_positive_1_60"] = False  # brak formalnej kontroli, patrz README
    method_c["anomaly_cycles"] = [int(cycle[i]) for i in anomaly_points]

    return {
        "unit": unit,
        "cycle": [int(c) for c in cycle],
        "sensor_raw": [float(s) for s in sensor],
        "end_of_life": end_of_life,
        "sensor_name": sensor_name,
        "source": source,
        "is_synthetic": is_synthetic,
        "method_a": method_a,
        "method_b": method_b,
        "method_c": method_c,
    }


def compute_engine_run(csv_path: str = DEFAULT_DATA_PATH, unit: int = 1) -> EngineRun:
    """Liczy metody A/B/C na jednym przebiegu silnika (domyslnie unit 1,
    JEDYNE realne dane dostepne w tym repo -- patrz README, sekcja "Co
    jest tu realne"). Parametr `unit` zostawiony na przyszlosc (patrz
    README "Jak zrobic to porzadnie", krok 1: pelny train_FD001.txt ze
    100 silnikami) -- na razie wspiera WYLACZNIE unit=1, inne wartosci
    rzuca jawny blad zamiast cicho zwrocic zle dane."""
    if unit != 1:
        raise ValueError(
            f"unit={unit} niewspierane -- to repo ma dane WYLACZNIE dla unit=1 "
            f"(patrz README, sekcja 'Co jest tu realne, a co ograniczone "
            f"przez srodowisko')."
        )

    data = np.loadtxt(csv_path)
    cycle = data[:, 1]
    sensor = data[:, SENSOR4_COL]
    return _analyze_series(
        cycle, sensor, unit=unit,
        sensor_name="sensor 4 (T50 — temperatura na wylocie z LPT)",
        source="cmapss_real",
    )


def compute_synthetic_run(seed: int = 42, n_cycles: int = 180) -> EngineRun:
    """SYNTETYCZNY drugi przebieg -- NIE realne dane silnika, wygenerowany
    proceduralnie do demonstracji UI (drugie demo obok realnego unit=1).
    Model: staly poziom bazowy + szum gaussowski + kwadratowo narastajacy
    dryft w drugiej polowie przebiegu (przypomina ksztaltem typowa
    krzywa degradacji, w tym unit=1 -- ale to CELOWE podobienstwo
    wizualne do demo, nie twierdzenie o realnym zachowaniu silnika).
    Parametry (poziom bazowy, amplituda szumu, moment/sila dryftu) sa
    zamrozone w kodzie na sztywno, nie dostrajane pod zaden wynik."""
    rng = np.random.default_rng(seed)
    cycle = np.arange(1, n_cycles + 1, dtype=float)
    baseline = 643.0  # rzedu wielkosci sensor 4 (T50) w realnych danych unit=1
    noise = rng.normal(0.0, 0.45, size=n_cycles)
    drift_start = int(n_cycles * 0.55)
    drift = np.zeros(n_cycles)
    t = np.arange(n_cycles - drift_start, dtype=float)
    drift[drift_start:] = 0.0025 * t ** 2
    sensor = baseline + noise + drift
    return _analyze_series(
        cycle, sensor, unit="SYNTH-1",
        sensor_name="SYNTETYCZNY czujnik demonstracyjny (NIE realne dane — szum + narastajacy dryft)",
        source="synthetic",
        is_synthetic=True,
    )


def compute_run_from_upload(
    raw_bytes: bytes, unit: int | None = None, sensor: int | None = None
) -> EngineRun:
    """Wlasny plik uzytkownika w TYM SAMYM formacie co cmapss_fd001_unit1.txt
    (C-MAPSS: unit, cycle, 3x nastawa operacyjna, 21x czujnik, wartosci
    rozdzielone spacjami/tabulatorami, min. 26 kolumn). Jesli plik zawiera
    dokladnie jedna jednostke (unit), parametr `unit` mozna pominac -- w
    przeciwnym razie jest WYMAGANY (nie zgadujemy, ktory silnik user
    chcial), inaczej jawny blad z lista dostepnych jednostek.

    `sensor` (2026-09-22, "tu tez"): numer czujnika 1..21 do analizy. Gdy
    `None` (domyslnie), czujnik jest wybierany AUTOMATYCZNIE przez
    `select_informative_sensor()` (ten sam z-score przesuniecia sredniej,
    ktorym pierwotnie recznie znaleziono sensor 4 dla unit=1 -- patrz
    docstring tamtej funkcji). W ODROZNIENIU od compute_engine_run()
    (ktora zawsze uzywa SENSOR4_COL, bo to jest jedyne realne, juz
    zweryfikowane referencyjne demo tego repo, patrz README), tu NIE MA
    zadnej gwarancji, ze wgrany plik pochodzi z tego samego typu silnika co
    unit=1 -- sensor 4 nie ma tu zadnego uprzywilejowanego statusu, wiec
    domyslne zachowanie to auto-wybor, nie sztywna stala."""
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"nie da sie odczytac pliku jako tekst UTF-8: {e}")

    try:
        data = np.loadtxt(io.StringIO(text))
    except Exception as e:
        raise ValueError(
            f"nie da sie sparsowac pliku jako macierzy liczb rozdzielonych "
            f"spacjami/tabulatorami (oczekiwany format C-MAPSS): {e}"
        )

    if data.ndim != 2 or data.shape[1] < SENSOR4_COL + 1:
        got_cols = data.shape[1] if data.ndim == 2 else data.ndim
        raise ValueError(
            f"plik ma {got_cols} kolumn -- oczekiwano co najmniej "
            f"{SENSOR4_COL + 1} (format C-MAPSS: unit, cycle, 3x nastawa, "
            f"21x czujnik)."
        )

    units_in_file = sorted(int(u) for u in np.unique(data[:, 0]))
    if unit is None:
        if len(units_in_file) != 1:
            raise ValueError(
                f"plik zawiera {len(units_in_file)} roznych jednostek "
                f"{units_in_file} -- podaj parametr unit, ktora wziac."
            )
        unit = units_in_file[0]
    elif unit not in units_in_file:
        raise ValueError(f"unit={unit} nie wystepuje w pliku (dostepne: {units_in_file}).")

    rows = data[data[:, 0] == unit]
    rows = rows[np.argsort(rows[:, 1])]
    cycle = rows[:, 1]

    sensor_scores: dict[int, float] | None = None
    if sensor is None:
        all_sensor_cols = rows[:, 5:5 + N_SENSORS]
        sensor, sensor_scores = select_informative_sensor(cycle, all_sensor_cols)
        name_suffix = f"auto-wybrany, z-score={sensor_scores[sensor]:.2f}"
    else:
        if not (1 <= sensor <= N_SENSORS):
            raise ValueError(f"sensor={sensor} poza zakresem 1..{N_SENSORS}")
        name_suffix = "wybrany recznie"

    sensor_series = rows[:, _sensor_col(sensor)]
    result = _analyze_series(
        cycle, sensor_series, unit=unit,
        sensor_name=f"sensor {sensor} ({name_suffix}) — z pliku uzytkownika (zaklada format C-MAPSS)",
        source="upload",
    )
    result["sensor_number"] = sensor
    result["sensor_scores"] = sensor_scores
    return result


def compute_run_from_device_samples(
    values: list[float],
    port_label: str | None = None,
    device_kind: str = "urzadzenie",
) -> EngineRun:
    """Live odczyt z urzadzenia zewnetrznego -- JEDNA wartosc czujnika na
    probke (nie pelny format C-MAPSS), cykl = kolejny numer probki (1..N).
    Uzywa DOKLADNIE tego samego rdzenia A/B/C co reszta zrodel. Dwa
    faktyczne zrodla probek w webapp/app.py: port szeregowy
    (/api/serial/read, wartosc = surowy odczyt czujnika) i mikrofon audio
    (/api/audio/record, wartosc = dominujaca czestotliwosc na okno, patrz
    dominant_frequency_series() nizej) -- `device_kind` opisuje, ktore.

    UWAGA O ZAKRESIE WERYFIKACJI: ta funkcja sama (parsowanie listy
    liczb -> A/B/C) jest przetestowana, tak samo jak ekstrakcja cechy
    audio (dominant_frequency_series(), syntetycznie). Kod OBSLUGUJACY
    faktyczny port szeregowy / mikrofon (w webapp/app.py) zostal napisany
    wedlug tego samego wzorca co reszta ekosystemu, ale NIE mogl zostac
    przetestowany na prawdziwym urzadzeniu w tym srodowisku (sandbox bez
    portow szeregowych ani sprzetu audio) -- przetestuj ostroznie na
    wlasnym sprzecie."""
    if len(values) < MIN_SAMPLES:
        raise ValueError(
            f"za malo probek z urzadzenia ({len(values)}) -- potrzeba co "
            f"najmniej {MIN_SAMPLES} do okna referencyjnego."
        )
    cycle = np.arange(1, len(values) + 1, dtype=float)
    sensor = np.asarray(values, dtype=float)
    label = (
        f"czujnik zywy ({device_kind}: {port_label})" if port_label
        else f"czujnik zywy ({device_kind})"
    )
    return _analyze_series(cycle, sensor, unit="DEVICE", sensor_name=label, source="device_live")


def _dominant_frequency(chunk: np.ndarray, samplerate: int, fmin: float = 50.0) -> float:
    """Czestotliwosc (Hz) o najwiekszej amplitudzie widma FFT pojedynczego
    okna audio, pomijajac czestotliwosci ponizej `fmin` (DC/bardzo wolny
    dryft mikrofonu). Okno Hanninga przed FFT (standardowe wygladzenie
    przeciekow widma)."""
    n = len(chunk)
    if n < 4:
        return 0.0
    windowed = chunk * np.hanning(n)
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(n, d=1.0 / samplerate)
    mask = freqs >= fmin
    if not np.any(mask):
        return 0.0
    idx = np.argmax(spectrum[mask])
    return float(freqs[mask][idx])


def dominant_frequency_series(
    audio: np.ndarray, samplerate: int, window_s: float = 0.5, fmin: float = 50.0
) -> list[float]:
    """Dzieli nagranie audio na kolejne, nienachodzace na siebie okna
    dlugosci `window_s` i dla kazdego zwraca dominujaca czestotliwosc
    (patrz _dominant_frequency) -- jedna liczba na okno, ktora jest dalej
    podawana do compute_run_from_device_samples() jako seria "probek
    czujnika". Czysta funkcja numpy, BEZ zaleznosci od sprzetu audio --
    w pelni testowalna syntetycznie (wygeneruj sinusoide o znanej
    czestotliwosci, sprawdz ze wynik jest bliski tej czestotliwosci;
    patrz testy)."""
    win_len = max(1, int(round(window_s * samplerate)))
    n_windows = len(audio) // win_len
    return [
        _dominant_frequency(audio[i * win_len:(i + 1) * win_len], samplerate, fmin=fmin)
        for i in range(n_windows)
    ]
