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


class EngineRun(TypedDict):
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


def compute_run_from_upload(raw_bytes: bytes, unit: int | None = None) -> EngineRun:
    """Wlasny plik uzytkownika w TYM SAMYM formacie co cmapss_fd001_unit1.txt
    (C-MAPSS: unit, cycle, 3x nastawa operacyjna, 21x czujnik, wartosci
    rozdzielone spacjami/tabulatorami, min. 26 kolumn). Jesli plik zawiera
    dokladnie jedna jednostke (unit), parametr `unit` mozna pominac -- w
    przeciwnym razie jest WYMAGANY (nie zgadujemy, ktory silnik user
    chcial), inaczej jawny blad z lista dostepnych jednostek."""
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
    sensor = rows[:, SENSOR4_COL]
    return _analyze_series(
        cycle, sensor, unit=unit,
        sensor_name="sensor 4 (T50) — z pliku uzytkownika (zaklada format C-MAPSS)",
        source="upload",
    )


def compute_run_from_device_samples(values: list[float], port_label: str | None = None) -> EngineRun:
    """Live odczyt z urzadzenia zewnetrznego (np. port szeregowy, patrz
    webapp/app.py /api/serial/read) -- JEDNA wartosc czujnika na probke
    (nie pelny format C-MAPSS), cykl = kolejny numer probki (1..N). Uzywa
    DOKLADNIE tego samego rdzenia A/B/C co reszta zrodel.

    UWAGA O ZAKRESIE WERYFIKACJI: ta funkcja sama (parsowanie listy
    liczb -> A/B/C) jest przetestowana. Kod OBSLUGUJACY faktyczny port
    szeregowy (w webapp/app.py) zostal napisany wedlug tego samego wzorca
    co reszta ekosystemu, ale NIE mogl zostac przetestowany na prawdziwym
    urzadzeniu w tym srodowisku (sandbox bez portow szeregowych) --
    przetestuj ostroznie na wlasnym sprzecie."""
    if len(values) < MIN_SAMPLES:
        raise ValueError(
            f"za malo probek z urzadzenia ({len(values)}) -- potrzeba co "
            f"najmniej {MIN_SAMPLES} do okna referencyjnego."
        )
    cycle = np.arange(1, len(values) + 1, dtype=float)
    sensor = np.asarray(values, dtype=float)
    label = (
        f"czujnik zywy (urzadzenie: {port_label})" if port_label
        else "czujnik zywy (urzadzenie zewnetrzne)"
    )
    return _analyze_series(cycle, sensor, unit="DEVICE", sensor_name=label, source="device_live")
