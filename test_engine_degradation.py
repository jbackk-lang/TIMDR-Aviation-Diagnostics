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

AKTUALIZACJA (2026-09-17): obliczenia przeniesione do analysis.py (dzielone
z dashboardem webapp/app.py) -- ten plik jest teraz cienkim wywolaniem +
wypisaniem raportu, zero zmian w matematyce (zweryfikowano identycznosc
wyniku po refaktoryzacji, patrz commit)."""
from analysis import compute_engine_run


def main():
    run = compute_engine_run()
    cycle = run["cycle"]
    end_of_life = run["end_of_life"]

    print(f"NASA C-MAPSS FD001, unit {run['unit']}: {len(cycle)} cykli, awaria w cyklu {end_of_life}")
    print(f"Czujnik: {run['sensor_name']}, dobrany obiektywnie (patrz docstring modulu)\n")

    a, b, c = run["method_a"], run["method_b"], run["method_c"]

    print(f"--- Metoda {a['name']} ---")
    if a["alarm_cycle"] is not None:
        print(f"  alarm od cyklu {a['alarm_cycle']} -> lead time = {a['lead_time']} cykli")
    else:
        print("  brak alarmu")
    print(f"  falszywy alarm w cyklach 1-60: {a['false_positive_1_60']}\n")

    print(f"--- Metoda {b['name']} ---")
    if b["alarm_cycle"] is not None:
        print(f"  alarm od cyklu {b['alarm_cycle']} -> lead time = {b['lead_time']} cykli")
    else:
        print("  brak alarmu")
    print(f"  falszywy alarm w cyklach 1-60: {b['false_positive_1_60']}\n")

    print(f"--- Metoda {c['name']} ---")
    if c["anomaly_cycles"]:
        print(f"  {len(c['anomaly_cycles'])} wykrytych punktow, pierwszy: cykl {c['alarm_cycle']} "
              f"-> lead time = {c['lead_time']} cykli")
        print(f"  wszystkie cykle: {c['anomaly_cycles']}")
        print("  UWAGA: to sa IZOLOWANE punkty odstajace, nie trwaly sygnal trendu -")
        print("  bez negatywnej kontroli (dlugi przebieg 'zdrowy' o tym samym poziomie")
        print("  szumu) nie da sie odroznic prawdziwego wczesnego ostrzezenia od")
        print("  normalnej stopy falszywych alarmow tej metody na tym poziomie szumu.")
    else:
        print("  brak wykrytych anomalii (TRM sledzi powolny dryf, nie flaguje go)")

    print("\n--- Podsumowanie (lead time = ile cykli przed awaria wykryto problem) ---")
    print(f"  A (baseline SPC, surowa wartosc): {a['lead_time'] if a['lead_time'] is not None else 'brak'}")
    print(f"  B (TIMDR flow, trend):            {b['lead_time'] if b['lead_time'] is not None else 'brak'}")
    if c["anomaly_cycles"]:
        print(f"  C (TIMDR anomalies, pkt.odstajace, niepotwierdzone): {c['lead_time']}")


if __name__ == "__main__":
    main()
