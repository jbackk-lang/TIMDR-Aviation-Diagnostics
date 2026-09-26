# Aneks 1 do CLAIM_AUDIT_PREREG.md (zapisany PRZED drugim uruchomieniem audytu)

Pierwszy przebieg: commit ab9f56b, raport `CLAIM_AUDIT_v1.md` z analizą post hoc. Po nim:

1. README poprawione: ujawniona wspólna kotwica reguł i wyniku (d3a6ddf); „obiektywnie” → „algorytmicznie” z opisem
   selekcji na wyniku; zgodność z literaturą opisana jako potwierdzenie parsowania, nie rankingu; dryf opisany jako płaski
   i przyspieszający (~27×) zamiast „prawie liniowego”; nowy akapit o analizie wstecznej vs odtwarzaniu na bieżąco.
2. Kod: `analysis._analyze_series` liczy `false_positive_1_60` metody C z listy anomalii (wcześniej False na sztywno);
   nowy test `test_method_c_false_positive_flag_is_computed`. Wynik unit 1 bez zmian (False).
3. `recompute_av.py` v1.1: dodana sekcja `online` (wzorzec alarmów przy odtwarzaniu na bieżąco, post hoc). Pozostałe sekcje
   `RECOMPUTE_AV.json` przeliczone ponownie — identyczne z przebiegiem 1 (pytest: 14 testów zamiast 13).
4. Karty v1.1 (`claims_av.py`, lista w nagłówku). Zmienione PO zobaczeniu wyników przebiegu 1 — drugi przebieg sprawdza
   zgodność poprawionego README z plikami, nie jest niezależnym testem.
