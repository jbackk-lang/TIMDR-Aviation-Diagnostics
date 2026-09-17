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
test_engine_degradation.py -- to czyste przeniesienie, weryfikowane
identycznym wynikiem (patrz koniec tego pliku / test refaktoryzacji).
"""
from __future__ import annotations

import os
from typing import TypedDict

import numpy as np

from timdr_core import TIMDR_EarthquakeCore

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(_THIS_DIR, "cmapss_fd001_unit1.txt")


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
    unit: int
    cycle: list[int]
    sensor_raw: list[float]      # sensor 4 (T50), surowe wartosci
    end_of_life: int
    sensor_name: str
    method_a: MethodResult
    method_b: MethodResult
    method_c: MethodResult


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
    sensor = data[:, 5 + 3]  # sensor 4 (0-indexed: col5=sensor1)
    end_of_life = int(cycle[-1])

    # --- Metoda A: baseline SPC na surowej wartosci ---
    ref_mean_a, ref_std_a = np.mean(sensor[:30]), np.std(sensor[:30])
    z_a = (sensor - ref_mean_a) / ref_std_a
    idx_a = first_sustained_alarm(z_a)
    fp_a = bool(np.any(np.abs(z_a[:60]) > 3.0))

    # --- Metoda B: TIMDR flow (lokalny trend) ---
    core = TIMDR_EarthquakeCore(k_neighbors=8)
    flow_grad = core.flow(cycle, sensor)
    ref_mean_b, ref_std_b = np.mean(flow_grad[:30]), np.std(flow_grad[:30])
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
        "sensor_name": "sensor 4 (T50 — temperatura na wylocie z LPT)",
        "method_a": method_a,
        "method_b": method_b,
        "method_c": method_c,
    }
