"""
test_analysis_extra.py — testy nowych funkcji analysis.py (2026-09-17,
dashboard z 4 zrodlami danych): compute_synthetic_run, compute_run_from_upload,
compute_run_from_device_samples, dominant_frequency_series.

Zakres: to sa testy FUNKCJI OBLICZENIOWYCH (czysty numpy, zero I/O
sprzetowego) -- NIE testuja faktycznego odczytu z portu szeregowego ani
mikrofonu (webapp/app.py /api/serial/*, /api/audio/*), bo to wymaga
prawdziwego sprzetu, ktorego nie ma w srodowisku, w ktorym te testy
powstaly. Patrz README, sekcja "Cztery zrodla danych".
"""
import numpy as np
import pytest

from analysis import (
    DEFAULT_DATA_PATH,
    N_SENSORS,
    compute_engine_run,
    compute_run_from_device_samples,
    compute_run_from_upload,
    compute_synthetic_run,
    dominant_frequency_series,
    select_informative_sensor,
)


def test_compute_engine_run_unit1_unchanged():
    """Regresja: refaktoryzacja (_analyze_series) nie zmienila wyniku dla
    jedynych realnych danych w tym repo (unit=1). Liczby zamrozone z
    wyniku SPRZED refaktoryzacji (patrz test_engine_degradation.py)."""
    r = compute_engine_run()
    assert r["unit"] == 1
    assert r["end_of_life"] == 192
    assert r["method_a"]["alarm_cycle"] == 145
    assert r["method_a"]["lead_time"] == 47
    assert r["method_b"]["alarm_cycle"] == 174
    assert r["method_b"]["lead_time"] == 18
    assert r["method_c"]["anomaly_cycles"] == [96, 126, 165]


def test_compute_engine_run_rejects_other_units():
    with pytest.raises(ValueError, match="niewspierane"):
        compute_engine_run(unit=2)


def test_select_informative_sensor_reproduces_sensor4_on_real_unit1():
    """2026-09-22 ('tu tez'): select_informative_sensor jest przeniesieniem
    JUZ ISTNIEJACEJ recznej metodologii (README, sekcja 'Metodologia') do
    wielokrotnie uzywalnego kodu, nie nowym odkryciem -- musi odtworzyc
    dokladnie ten sam wybor (sensor 4), ktory README opisuje jako znaleziony
    recznie i potwierdzony literatura (~14 'informative sensors')."""
    data = np.loadtxt(DEFAULT_DATA_PATH)
    cycle = data[:, 1]
    all_sensors = data[:, 5:5 + N_SENSORS]
    best, scores = select_informative_sensor(cycle, all_sensors)
    assert best == 4
    assert len(scores) == N_SENSORS
    assert scores[4] == max(scores.values())


def test_upload_auto_selects_most_informative_sensor(tmp_path):
    """Gdy `sensor` nie jest podany, compute_run_from_upload wybiera go
    automatycznie (nie zawsze sensor 4) -- tu jawnie wstrzykujemy silny
    dryft na sensorze 10, zeby sprawdzic, ze auto-wybor faktycznie zalezy
    od DANYCH pliku, nie jest cicho zignorowany na rzecz sztywnej stalej."""
    rng = np.random.default_rng(0)
    n = 40
    rows = []
    for cyc in range(1, n + 1):
        vals = [1.0] * 3
        sensors = list(rng.normal(600, 1.0, size=21))
        if cyc > 25:
            sensors[9] += 50.0  # silny skok na sensorze 10 (index 9, 0-indexed)
        rows.append(f"1 {cyc} " + " ".join(map(str, vals)) + " " + " ".join(map(str, sensors)))
    p = tmp_path / "drift_sensor10.txt"
    p.write_text("\n".join(rows), encoding="utf-8")

    r = compute_run_from_upload(p.read_bytes())
    assert r["sensor_number"] == 10
    assert r["sensor_scores"] is not None
    assert "auto-wybrany" in r["sensor_name"]


def test_upload_explicit_sensor_overrides_auto_select(tmp_path):
    rng = np.random.default_rng(0)
    rows = []
    for cyc in range(1, 41):
        vals = [1.0] * 3
        sensors = list(rng.normal(600, 1.0, size=21))
        rows.append(f"1 {cyc} " + " ".join(map(str, vals)) + " " + " ".join(map(str, sensors)))
    p = tmp_path / "one_unit_explicit.txt"
    p.write_text("\n".join(rows), encoding="utf-8")

    r = compute_run_from_upload(p.read_bytes(), sensor=7)
    assert r["sensor_number"] == 7
    assert r["sensor_scores"] is None
    assert "wybrany recznie" in r["sensor_name"]


def test_synthetic_run_is_labeled_and_deterministic():
    r1 = compute_synthetic_run(seed=1)
    r2 = compute_synthetic_run(seed=1)
    r3 = compute_synthetic_run(seed=2)
    assert r1["is_synthetic"] is True
    assert r1["source"] == "synthetic"
    assert r1["sensor_raw"] == r2["sensor_raw"]  # deterministyczne (ten sam seed)
    assert r1["sensor_raw"] != r3["sensor_raw"]  # inny seed -> inne dane


def test_upload_single_unit_autodetect(tmp_path):
    p = tmp_path / "one_unit.txt"
    rows = []
    rng = np.random.default_rng(0)
    for cyc in range(1, 41):
        vals = [1.0] * 3
        sensors = list(rng.normal(600, 1.0, size=21))
        rows.append(f"1 {cyc} " + " ".join(map(str, vals)) + " " + " ".join(map(str, sensors)))
    p.write_text("\n".join(rows), encoding="utf-8")

    r = compute_run_from_upload(p.read_bytes())
    assert r["unit"] == 1
    assert r["source"] == "upload"
    assert len(r["cycle"]) == 40


def test_upload_multi_unit_requires_param(tmp_path):
    p = tmp_path / "two_units.txt"
    rng = np.random.default_rng(0)
    rows = []
    for unit in (1, 2):
        for cyc in range(1, 35):
            vals = [1.0] * 3
            sensors = list(rng.normal(600, 1.0, size=21))
            rows.append(f"{unit} {cyc} " + " ".join(map(str, vals)) + " " + " ".join(map(str, sensors)))
    p.write_text("\n".join(rows), encoding="utf-8")
    raw = p.read_bytes()

    with pytest.raises(ValueError, match="roznych jednostek"):
        compute_run_from_upload(raw)

    r = compute_run_from_upload(raw, unit=2)
    assert r["unit"] == 2


def test_device_samples_needs_min_30():
    with pytest.raises(ValueError, match="za malo probek"):
        compute_run_from_device_samples([1.0] * 10)


def test_device_samples_label_and_kind():
    vals = [640.0 + 0.05 * i for i in range(35)]
    r = compute_run_from_device_samples(vals, port_label="COM7")
    assert r["source"] == "device_live"
    assert "COM7" in r["sensor_name"]

    r2 = compute_run_from_device_samples(vals, port_label="Mikrofon USB", device_kind="mikrofon")
    assert "mikrofon" in r2["sensor_name"]
    assert "Mikrofon USB" in r2["sensor_name"]


def test_dominant_frequency_series_detects_known_tone():
    """Rdzen weryfikacji sciezki audio: syntetyczna sinusoida o znanej
    czestotliwosci (440 Hz) musi zostac wykryta z bledem mniejszym niz
    rozdzielczosc FFT dla danego okna."""
    sr = 8000
    window_s = 0.5
    duration = 5.0
    t = np.arange(int(duration * sr)) / sr
    rng = np.random.default_rng(0)
    audio = 0.8 * np.sin(2 * np.pi * 440.0 * t) + 0.05 * rng.normal(size=len(t))

    freqs = dominant_frequency_series(audio, sr, window_s=window_s)
    fft_resolution = 1.0 / window_s  # Hz na "kubelek" FFT
    assert len(freqs) == int(duration / window_s)
    assert all(abs(f - 440.0) <= fft_resolution for f in freqs)


def test_dominant_frequency_series_tracks_drift():
    """Czestotliwosc dryfujaca w czasie (440 -> 460 Hz) powinna zostac
    odzwierciedlona jako rosnaca seria, nie plaska linia."""
    sr = 8000
    duration = 20.0
    n = int(duration * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(0)
    freq_t = 440 + 20 * (t / duration)
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    audio = 0.8 * np.sin(phase) + 0.1 * rng.normal(size=n)

    freqs = dominant_frequency_series(audio, sr, window_s=0.5)
    assert freqs[0] < freqs[-1]
    assert min(freqs) >= 430 and max(freqs) <= 470


def test_dominant_frequency_series_feeds_full_pipeline():
    sr = 8000
    duration = 20.0
    n = int(duration * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(0)
    freq_t = 440 + 20 * (t / duration)
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    audio = 0.8 * np.sin(phase) + 0.1 * rng.normal(size=n)

    freqs = dominant_frequency_series(audio, sr, window_s=0.5)
    r = compute_run_from_device_samples(freqs, port_label="Test Mic", device_kind="mikrofon")
    assert r["source"] == "device_live"
    assert len(r["cycle"]) == len(freqs)
