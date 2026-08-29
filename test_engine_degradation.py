"""
Test: czy TIMDR-Core (przeniesiony bez zmian z TIMDR-Earthquake-Core) daje
uzyteczne wczesne ostrzeganie o degradacji silnika turbowentylatorowego na
realnych danych NASA C-MAPSS (FD001, unit 1)?

PRE-REJESTRACJA (spisana PRZED patrzeniem na finalny wynik testu detekcji;
wybor czujnika w kroku 0 byl czysto obiektywny - patrz nizej):

Dane: NASA C-MAPSS FD001, unit 1 - kompletny, realny przebieg run-to-failure
(192 cykle, awaria w cyklu 192). Zrodlo: NASA Prognostics Center of
Excellence / data.nasa.gov, pobrane przez mirror
github.com/mapr-demos/predictive-maintenance (surowy plik
cmapss_fd001_unit1.txt w tym katalogu to DOKLADNA kopia 192 wierszy dla
unit=1 z oryginalnego train_FD001.txt - bez modyfikacji).

Krok 0 (dobor czujnika, obiektywny): sposrod 21 czujnikow wybrano ten o
najwiekszym |przesuniecie(cykle163-192) - przesuniecie(cykle1-30)| w
jednostkach odchylenia standardowego z pierwszych 30 cykli. Wygrał sensor 4
(w standardowej numeracji C-MAPSS to T50 - temperatura na wylocie z LPT).
Ranking pokryl sie 1:1 ze znanym z literatury zbiorem ~14 "informative
sensors" dla FD001 - dobry znak, ze dane sa poprawnie sparsowane.

Metoda A (BASELINE - standardowy przemyslowy control chart, Shewhart/SPC):
  referencja = srednia/std SUROWEJ wartosci czujnika z pierwszych 30 cykli
  (zamrozona). Alarm = pierwszy moment 3 kolejnych cykli z |z|>3.

Metoda B (TIMDR flow - monitorowanie TRENDU zamiast wartosci):
  flow_grad = TIMDR_EarthquakeCore().flow(cykl, czujnik) - lokalny gradient
  LSQ (k_neighbors=8). Ten sam rodzaj alarmu (3 kolejne cykle |z|>3) co
  metoda A, ale liczony na flow_grad zamiast na surowej wartosci.

Metoda C (TIMDR anomalies - odstajace punkty wzgledem TRM-median):
  anomalies() z factor=3.0 (domyslny). Pierwszy wykryty punkt.

Metryka: cykl alarmu, lead time = 192 - cykl_alarmu, falszywy alarm w
cyklach 1-60 (przyjete jako "zdrowy" wczesny okres zycia silnika).

Hipoteza a priori: brak. To pojedynczy realny przypadek (n=1 silnik) -
traktowac jako demonstracje metody, NIE walidacje statystyczna.
"""
import numpy as np
from timdr_core import TIMDR_EarthquakeCore


def first_sustained_alarm(z, run=3, thr=3.0):
    flag = np.abs(z) > thr
    for i in range(len(flag) - run + 1):
        if np.all(flag[i:i + run]):
            return i
    return None


def main():
    data = np.loadtxt("cmapss_fd001_unit1.txt")
    cycle = data[:, 1]
    sensor = data[:, 5 + 3]  # sensor 4 (0-indexed: col5=sensor1)
    end_of_life = int(cycle[-1])

    print(f"NASA C-MAPSS FD001, unit 1: {len(cycle)} cykli, awaria w cyklu {end_of_life}")
    print(f"Czujnik: sensor 4 (T50), dobrany obiektywnie (patrz docstring modulu)\n")

    # --- Metoda A: baseline SPC na surowej wartosci ---
    ref_mean_a, ref_std_a = np.mean(sensor[:30]), np.std(sensor[:30])
    z_a = (sensor - ref_mean_a) / ref_std_a
    idx_a = first_sustained_alarm(z_a)
    fp_a = bool(np.any(np.abs(z_a[:60]) > 3.0))

    print("--- Metoda A: baseline SPC (surowa wartosc czujnika) ---")
    if idx_a is not None:
        print(f"  alarm od cyklu {int(cycle[idx_a])} -> lead time = {end_of_life - int(cycle[idx_a])} cykli")
    else:
        print("  brak alarmu")
    print(f"  falszywy alarm w cyklach 1-60: {fp_a}\n")

    # --- Metoda B: TIMDR flow (lokalny trend) ---
    core = TIMDR_EarthquakeCore(k_neighbors=8)
    flow_grad = core.flow(cycle, sensor)
    ref_mean_b, ref_std_b = np.mean(flow_grad[:30]), np.std(flow_grad[:30])
    z_b = (flow_grad - ref_mean_b) / ref_std_b
    idx_b = first_sustained_alarm(z_b)
    fp_b = bool(np.any(np.abs(z_b[:60]) > 3.0))

    print("--- Metoda B: TIMDR flow (lokalny trend LSQ) ---")
    if idx_b is not None:
        print(f"  alarm od cyklu {int(cycle[idx_b])} -> lead time = {end_of_life - int(cycle[idx_b])} cykli")
    else:
        print("  brak alarmu")
    print(f"  falszywy alarm w cyklach 1-60: {fp_b}\n")

    # --- Metoda C: TIMDR anomalies (odstajace wzgledem TRM-median) ---
    anomaly_points, _residuals, _thr = core.anomalies(cycle, sensor, factor=3.0)
    print("--- Metoda C: TIMDR anomalies (TRM-median residual) ---")
    if len(anomaly_points):
        first = int(cycle[anomaly_points[0]])
        print(f"  {len(anomaly_points)} wykrytych punktow, pierwszy: cykl {first} "
              f"-> lead time = {end_of_life - first} cykli")
        print(f"  wszystkie cykle: {[int(cycle[i]) for i in anomaly_points]}")
        print("  UWAGA: to sa IZOLOWANE punkty odstajace, nie trwaly sygnal trendu -")
        print("  bez negatywnej kontroli (dlugi przebieg 'zdrowy' o tym samym poziomie")
        print("  szumu) nie da sie odroznic prawdziwego wczesnego ostrzezenia od")
        print("  normalnej stopy falszywych alarmow tej metody na tym poziomie szumu.")
    else:
        print("  brak wykrytych anomalii (TRM sledzi powolny dryf, nie flaguje go)")

    print("\n--- Podsumowanie (lead time = ile cykli przed awaria wykryto problem) ---")
    print(f"  A (baseline SPC, surowa wartosc): {end_of_life - int(cycle[idx_a]) if idx_a is not None else 'brak'}")
    print(f"  B (TIMDR flow, trend):            {end_of_life - int(cycle[idx_b]) if idx_b is not None else 'brak'}")
    if len(anomaly_points):
        print(f"  C (TIMDR anomalies, pkt.odstajace, niepotwierdzone): {end_of_life - int(cycle[anomaly_points[0]])}")


if __name__ == "__main__":
    main()
