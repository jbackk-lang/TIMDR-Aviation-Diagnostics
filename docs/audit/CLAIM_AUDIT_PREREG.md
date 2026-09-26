# Audyt twierdzeń README — TIMDR-Aviation-Diagnostics — pre-rejestracja

Status: ZAMROŻONE i zacommitowane PRZED pierwszym uruchomieniem `recompute_av.py` i audytu. Silnik: `tools/claim_audit.py`
(TIMDR-AI-Core `claim_audit` v0.2), reguły ogólne R1–R7 jak w `TIMDR-AI-Core/CLAIM_AUDIT.md`. Audytor przeczytał README,
`analysis.py`, `timdr_core.py` i testy przed napisaniem kart; wyników metod nie przeliczał.

## Zakres
README.md: „## Co jest tu realne” (z „Metodologią” i „Wynikiem”) do „## Jak zrobić to porządnie”; „### Auto-wybór czujnika”
do „## Pliki”; „## Pliki” do końca. Sekcje o dashboardzie i źródłach danych (poza auto-wyborem) — poza zakresem.

## Dane referencyjne
`train_FD001.txt` pobrany 2026-09-26 z mirrora wskazanego w README
(`raw.githubusercontent.com/mapr-demos/predictive-maintenance/master/notebooks/jupyter/Dataset/CMAPSSData/train_FD001.txt`),
sha256 963b5e22825b34d8b21c69e1aeb4af3e647050eb672ee8834ba4b5d91d2de0f8, zapisany w `../DATA/train_FD001.txt`.
Zestaw „informative sensors” FD001 z literatury (powszechnie używany: czujniki 1, 5, 6, 10, 16, 18, 19 odrzucane jako stałe
lub prawie stałe): {2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15, 17, 20, 21}.

## Poziomy dowodu
NIEZALEŻNE (własna implementacja w `recompute_av.py`), KOD REPO (wywołanie `analysis.py`/`timdr_core.py` — metody pod testem),
REFERENCJA (porównanie z `train_FD001.txt`), DOKUMENT/HISTORIA (nieweryfikowalne z plików — NIEROZSTRZYGNIĘTE).

## Reguły dodatkowe
- R8 Przyczynowość (lead time). „Lead time” to twierdzenie o wczesnym ostrzeżeniu, więc liczy się przy odtwarzaniu online:
  dla każdego cyklu c metoda dostaje tylko cykle 1..c (`_analyze_series` z repo na obciętym szeregu); moment alarmu = pierwsze c,
  w którym A/B ma ≥ 3 kolejne |z| > 3 kończące się w c, a C — anomalię w ostatnim punkcie c. Lead time przyczynowy = 192 − c.
  POTWIERDZONE, gdy lead przyczynowy ≥ lead z README − 2 (A/B: reguła 3 kolejnych cykli potrzebuje 2 cykli na potwierdzenie)
  albo ≥ lead z README (C, pojedynczy punkt); inaczej SPRZECZNE.
- R9 „prawie liniowy dryf”: czujnik 4, cykle 31–192, OLS liniowy vs kwadratowy. SPRZECZNE, gdy ΔBIC(lin − kwadr) > 10,
  krzywizna dodatnia i nachylenie w ostatniej trzeciej części ≥ 2× nachylenie w pierwszej trzeciej części; inaczej POTWIERDZONE.
- R10 „1:1 z literaturą”: 14 najwyżej ocenionych czujników (z-score przesunięcia średniej) = zestaw z literatury.
- R11 „kopia bez zmian logiki”: AST funkcji używanych przez metody (`__init__`, `_safe_k`, `_validate`, `_nearest_k_bounds`,
  `flow`, `trm` (ścieżka method="median" jest w jej ciele), `anomalies`) bez docstringów identyczne z
  `TIMDR-Earthquake-Core/core/timdr_core_earthquake.py`.
- R12 „wszystkie 21 wyników”: liczba wpisów `sensor_scores` z `select_informative_sensor` na unit 1 musi wynosić 21.
- R6 kotwica: `test_engine_degradation.py` (reguły „pre-rejestrowane w kodzie”) vs `README.md` (wynik).
- R13 Selekcja na wyniku: czujnik wybrany z użyciem ostatnich 30 cykli (koniec życia) TEGO SAMEGO silnika, na którym potem
  mierzy się czas wczesnego ostrzeżenia, korzysta z informacji z przyszłości. Twierdzenie „dobrano obiektywnie” dostaje
  DO ZŁAGODZENIA, jeśli README nie mówi, że wybór użył danych z końca życia tego przebiegu.
- R14 Fałszywe alarmy metody C: liczone z listy anomalii (cykle ≤ 60), bo pole `false_positive_1_60` metody C jest w kodzie
  ustawiane na False bez obliczeń — raportowane w uwagach.
